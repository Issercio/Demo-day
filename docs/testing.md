# Testing strategy and evidence

FloraShop is a small Flask shop. The suite is **API / integration tests** with an in-memory SQLite database (`DATABASE_URL=sqlite://`). There is no separate frontend test runner yet.

## Strategy

| Layer | Tool | When |
| --- | --- | --- |
| Unit / service | `unittest` calling `checkout_service` indirectly via HTTP | Every PR |
| API / integration | Flask `test_client` | Every PR |
| Auth & roles | Same, with JWT from `/auth/login` | Every PR |
| Database operations | SQLAlchemy on SQLite, orders persisted | Every PR |
| Manual / UI | Table below (browser) | Before Demo Day |
| E2E (Cypress/Playwright) | — | **Not set up yet** |
| Stripe live network | — | **Not covered** (keys left empty in tests) |

Run:

```bash
./run-tests.sh
```

or:

```bash
cd Demoday
source .venv/bin/activate
python3 -m coverage run --source=app -m unittest discover -s tests -v
python3 -m coverage report -m
```

Proof of the last captured run: [test-evidence/unittest-output.txt](test-evidence/unittest-output.txt), [test-evidence/coverage-report.txt](test-evidence/coverage-report.txt).

Postman collection for live API clicks: [postman/FloraShop.postman_collection.json](postman/FloraShop.postman_collection.json).

## What the automated tests cover

| File | Critical path |
| --- | --- |
| `tests/test_accounts.py` | Demo client seed (Marie Dupont, Léa Martin, Camille Pivoine), seven-category flower catalog with photos, register hashes + hides password, plaintext login rejected, legacy bcrypt login, unusable Marie hash reset, public `GET /themes`, admin-only vitrine `PUT`, event theme POST/DELETE with `theme_products` FKs, shop payload follows Automne, season/theme combo `printemps,mariage` |
| `tests/test_admin_guard.py` | Client cannot create categories, anonymous 401, admin 201, user list 403 for client, user detail without password, public catalog GET, Admin-Token rejected, forged JWT `is_admin` ignored, POST/PUT cannot mint admin, register cannot mint admin, client cannot read/delete another user, placeholder SECRET_KEY cannot impersonate admin, debug categories gone, admin product photo upload, client cannot upload, non-image rejected, admin order cards (`renderOrderCard`, unit price, acompte, à préparer, Enlever) |
| `tests/test_checkout.py` | Payment config in test mode, paid order + total, client cannot override price, declined / insufficient funds / unknown Luhn card, invalid PAN, subscription line, PayPal, saved card, 30 % deposit, admin prep PATCH / settle deposit, admin DELETE order (client/anonymous 403/401), empty cart, unknown product, invalid JWT, client cannot list orders, admin can, Decimal `10.10 × 3 = 30.30`, order IDOR (401/200/403/404), spoofed checkout email ignored, admin order item unit price, customer `GET /payments/my-orders` (own orders only, guest-by-email after login), `/commandes.html` tracking page |

## What is not covered yet

- Browser end-to-end (add to cart → checkout UI)
- Real Stripe PaymentIntent / webhook
- Forgot-password email
- Reviews endpoints (not mounted)
- CSRF / XSS fuzzing
- PostgreSQL-specific SQL
- Performance and accessibility

## Bugs found during testing

| Bug | Found how | Resolution |
| --- | --- | --- |
| Empty cart on `/checkout.html` | Manual path panier → payment | **Fixed** (load `api.js` + snapshot) |
| Marie login rejected | Manual login + screenshot | **Fixed** (bcrypt + demo rehash) |
| Shared cart between users | Manual two-account check | **Fixed** (per-user keys) |
| `float` money drift risk | Code audit | **Fixed** (`Numeric` / `Decimal`) |
| Checkout `build_order_lines` body merged into `money()` during that refactor | Unit tests would fail | **Fixed** before this evidence run |
| Forgot-password does not send mail | Manual page visit | **Open** |
| Reviews API 404 | Code review (`create_app` comment) | **Open** |
| Forged JWT `is_admin` / leaked example SECRET_KEY | Code audit | **Fixed** (roles from DB, placeholders ignored) |
| Unknown Luhn card accepted as paid | Code audit | **Fixed** (only documented test cards) |
| GET order without auth (IDOR) | Code audit | **Fixed** (owner or admin) |
| Season picker on `/accueil.html` | Product review | **Fixed** (admin **Vitrine du shop**, public `GET /themes`) |
| Admin orders as a one-line table | Demo walkthrough | **Fixed** (order cards with line prices and payment metadata) |

## Manual testing table

Use demo users from the README. Mark the result when you walk the jury scenario.

| # | Area | Steps | Expected | Result |
| --- | --- | --- | --- | --- |
| M1 | Login | `/account.html` as `marie@test.com` / `marie123` | JWT stored, profile email shown | See automated `test_accounts` + Demo Day walkthrough |
| M2 | Roles | Login as Marie, POST `/api/v1/categories` | 403 | Automated `test_admin_guard` |
| M3 | Shop form | `/shop.html` filter min/max price | List updates, no layout jump from a fixed nav | Manual |
| M4 | Cart isolation | Add item as guest, login as Marie, login as client | Carts do not mix | Manual (regression of a fixed bug) |
| M5 | Checkout | Snapshot cart → `/checkout.html` → 4242 card | Paid order, non-empty lines | Automated `test_checkout` |
| M6 | Decline | Card `4000000000000002` | 402, order `failed` | Automated |
| M7 | Admin | `admin@florashop.com` lists `/api/v1/payments/orders` | 200 | Automated |
| M8 | Vitrine | Admin applies Automne, then Printemps + Mariage; open `/shop.html` as a customer | Shop banner and catalog follow the applied vitrine; combo is a union | Automated `test_accounts` + Demo Day walkthrough |
| M9 | Orders | Admin **Commandes et paiements** after Marie’s paid or deposit order | Payment badge + prep select; settle remaining on a deposit | Automated `test_admin_guard` / `test_checkout` + Demo Day walkthrough |
| M10 | Tracking | Marie opens **Mes commandes** (`/commandes.html`) and clicks **Voir le détail** | Own order with photos, last four digits, line totals; Léa 403 on Marie’s id | Automated `test_checkout` + Demo Day walkthrough |

## Coverage notes

Latest captured run: **78 tests, OK**.

`coverage` is measured on the `app` package (templates and static JS are excluded):

| Module | Cover | Why it matters |
| --- | --- | --- |
| `app/models/order.py` | 100% | Money columns, payment/prep labels, order JSON |
| `app/services/demo_accounts.py` | 89% | Demo logins + flower catalog |
| `app/models/user.py` | 97% | Hash / bcrypt (plaintext refused) |
| `app/services/checkout_service.py` | 79% | Totals, Luhn, test cards, 30 % deposit |
| `app/api/v1/auth.py` | 79% | Login / register |
| Whole `app` package | 51% | Unused leftovers (`prices`, `reviews_restx`, Stripe live, old repositories) pull the average down |

Those leftovers are listed under Known Issues in the README.

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
| `tests/test_accounts.py` | Demo client seed, register hashes + hides password, plaintext then rehash, legacy bcrypt login, unusable Marie hash reset |
| `tests/test_admin_guard.py` | Client cannot create categories, anonymous 401, admin 201, user list 403 for client, user detail without password, public catalog GET |
| `tests/test_checkout.py` | Payment config in test mode, paid order + total, client cannot override price, declined / insufficient funds, invalid PAN, subscription line, PayPal, client cannot list orders, admin can, Decimal `10.10 × 3 = 30.30` |

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

## Coverage notes

Latest captured run: **23 tests, OK** (`test-evidence/unittest-output.txt`).

`coverage` is measured on the `app` package (templates and static JS are excluded):

| Module | Cover | Why it matters |
| --- | --- | --- |
| `app/models/order.py` | 100% | Money columns + order JSON |
| `app/services/demo_accounts.py` | 100% | Demo logins |
| `app/models/user.py` | 97% | Hash / bcrypt / plaintext |
| `app/services/checkout_service.py` | 76% | Totals, Luhn, test cards |
| `app/api/v1/auth.py` | 79% | Login / register |
| Whole `app` package | 36% | Unused leftovers (`prices`, `reviews_restx`, Stripe live, old repositories) pull the average down |

Those leftovers are listed under Known Issues in the README.

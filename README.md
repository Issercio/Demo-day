# Pivoine & Lilas

Online boutique for a florist in Sciez (Léman, Haute-Savoie). Customers browse bouquets, subscribe to seasonal flowers, and pay online. The florist manages the catalog and sees paid orders from a protected back-office.

The previous site was a Wix brochure that was no longer maintained. This application is the working shop: accounts, catalog, cart, server-side checkout, subscriptions, and administration.

Source: [github.com/Issercio/Demo-day](https://github.com/Issercio/Demo-day)

---

## Team

| Name | Role | Responsibilities |
| --- | --- | --- |
| Issercio | Full-stack developer | Flask API, SQLAlchemy models, authentication, checkout, tests, security, documentation |
| Matthieu | Front-end & product | Storefront (Jinja, CSS, JavaScript), user stories, live demonstration, presentation |

---

## Getting started

Python 3.10+ is required. PostgreSQL is optional; SQLite is the default.

```bash
git clone https://github.com/Issercio/Demo-day.git
cd Demo-day
chmod +x setup.sh run.sh run-tests.sh
./setup.sh
./run.sh
```

`setup.sh` creates `Demoday/.venv`, installs `Demoday/requirements.txt`, copies `.env.example` to `Demoday/.env` if needed, and seeds demo users plus a small flower catalog.

Manual equivalent:

```bash
cd Demoday
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
python3 init_db.py
python3 run.py
```

| Page | URL |
| --- | --- |
| Home | http://localhost:5000/accueil.html |
| Shop | http://localhost:5000/shop.html |
| Cart | http://localhost:5000/panier.html |
| Checkout | http://localhost:5000/checkout.html |
| Admin | http://localhost:5000/admin.html |
| API (Swagger) | http://localhost:5000/api/v1 |

```bash
./run-tests.sh
```

If a hosted URL is unavailable, run the local SQLite demo with the accounts below. Test output is in [`docs/testing.md`](docs/testing.md) and [`docs/test-evidence/`](docs/test-evidence/).

### Environment

Copy [`.env.example`](.env.example) to `Demoday/.env`. Never commit `.env`. Secrets are listed in `.gitignore`.

| Variable | Example | Role |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///florashop.db` | SQLAlchemy URI |
| `SECRET_KEY` | long random string | Flask and JWT signing |
| `JWT_SECRET_KEY` | long random string | Reserved JWT secret |
| `STRIPE_SECRET_KEY` | empty | Leave empty to use test cards |
| `STRIPE_PUBLISHABLE_KEY` | empty | Leave empty for the classroom demo |

### Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Customer | `marie@test.com` | `marie123` |
| Customer | `client@test.com` | `client123` |
| Florist (admin) | `admin@florashop.com` | `admin123` |

Successful payment: `4242 4242 4242 4242`, any future expiry, CVC `123`.  
Declined: `4000 0000 0000 0002`. Insufficient funds: `4000 0000 0000 9995`.

---

## Implemented user stories

| Role | Story | Priority |
| --- | --- | --- |
| Customer | Create an account and log in to place orders | Must have |
| Customer | Browse products by category | Must have |
| Customer | Order flowers online and pay | Must have |
| Customer | Keep a cart that does not leak to another account | Must have |
| Customer | Subscribe to a floral plan (monthly, semester, yearly) | Should have |
| Customer | Filter the catalog by minimum and maximum price | Shop filter |
| Florist | Add, update and delete products and categories | Must have |
| Florist | Review paid orders | Must have |
| Florist | Keep the back-office for administrators only | Must have |

Evidence: `/account.html`, `/shop.html`, `/checkout.html`, `/subscription.html`, `/admin.html`, and the REST routes under `/api/v1`.

---

## Missing user stories

These were in the original specification and are not in this release.

| Role | Story | Priority | Current state |
| --- | --- | --- | --- |
| Customer | Click-and-collect time slot | Must have | The order is paid; there is no pickup window |
| Customer | Delivery limited to configured zones | Must have | No postcode or zone table |
| Customer | Email alerts for events and sales | Could have | Password-reset pages are interface only |
| Florist | Edit homepage images and seasonal copy | Must have | Home is a template, not a CMS |
| Florist | Configure delivery areas | Must have | Not modelled |
| Florist | Enforce minimum and maximum catalog prices as rules | Must have | Admin sets a price; min/max in the shop is a filter |
| Florist | Publish blog posts and workshops | Should have | `/evenementiel.html` is static |
| Customer | Write product reviews | Specified | `reviews` model exists; endpoints are not mounted |

---

## Known bugs and limitations

Resolved:

- Empty cart on the payment page after per-account cart keys — checkout loads the shared cart script and a snapshot
- `marie@test.com` rejected on legacy bcrypt hashes — login accepts bcrypt and the demo seed repairs unusable hashes
- Cart shared between accounts — keys are `cart:user:<id>` and `cart:guest`
- Checkout trusted prices sent by the browser — totals come from the database
- Money stored as binary `float` — columns are `Numeric(10, 2)`, totals use `Decimal`
- Fixed navigation covering content — sticky header in document flow
- Profile / logout menu stretching the navbar — compact overlay under the account icon
- Empty shop on a fresh database — demo bouquets and compositions are seeded on startup
- Virtualenv and a Stripe publishable key in Git — removed

Open, none of them block a purchase:

- Forgot-password and verify-code pages do not send email
- Reviews API is not registered
- The cart lives in `localStorage`, not in a server table
- The `prices` table is unused (`products.price` is the source of truth)
- Duplicate CSS and leftover debug prints
- No production host in this repository (local demo)
- CORS allow-list is localhost
- Package coverage is pulled down by unused modules; checkout and authentication paths are covered

---

## Architecture

```mermaid
flowchart LR
  subgraph Browser
    Pages[Jinja pages]
    JS[api.js / FloraCart]
  end
  subgraph Flask
    Restx["REST API /api/v1"]
    Pay[Checkout service]
    Auth[JWT]
  end
  DB[(SQLite or PostgreSQL)]
  Pages --> JS
  JS -->|JSON + Bearer| Restx
  JS -->|POST checkout| Pay
  Restx --> Auth
  Restx --> DB
  Pay --> DB
```

The browser renders server templates and calls `/api/v1`. Checkout never uses a price from the client: `checkout_service.build_order_lines` loads `Product.price` from the database and totals with `Decimal`.

**Frontend.** Templates in `Demoday/app/templates/` (home, shop, cart, checkout, account, admin, subscription). Shared CSS in `static/css/style.css`. Cart and session in `static/js/api.js`. Vanilla JavaScript and Jinja — no React.

**Backend.** `create_app()` in `app/__init__.py` wires CORS, SQLAlchemy, Flask-RESTX namespaces (`auth`, `products`, `categories`, `users`) and the payments blueprint. Domain logic lives in `app/services/` (`checkout_service.py`, `demo_accounts.py`, `stripe_service.py`).

---

## Database

Money columns use `Numeric(10, 2)`. JSON still exposes numbers at the HTTP boundary; storage and totals are decimals.

```mermaid
erDiagram
  users ||--o{ orders : places
  users ||--o{ reviews : writes
  categories ||--o{ products : contains
  products ||--o{ order_items : appears_in
  orders ||--o{ order_items : contains
  products ||--o{ prices : optional_history

  users {
    int id PK
    string username
    string email
    string password_hash
    bool is_admin
  }
  categories {
    int id PK
    string name
  }
  products {
    int id PK
    string name
    numeric price
    int category_id FK
    bool is_on_sale
  }
  orders {
    int id PK
    int user_id FK
    string email
    numeric total_amount
    string status
  }
  order_items {
    int id PK
    int order_id FK
    int product_id FK
    int quantity
    numeric price
  }
```

`reviews` and `prices` exist as models but are not on the purchase path.

### UML

```mermaid
classDiagram
  class User {
    +int id
    +str username
    +str email
    +str password
    +bool is_admin
    +set_password()
    +check_password()
    +to_dict()
  }
  class Product {
    +int id
    +str name
    +Decimal price
    +int category_id
    +bool is_on_sale
  }
  class Category {
    +int id
    +str name
  }
  class Order {
    +int id
    +int user_id
    +str email
    +Decimal total_amount
    +str status
  }
  class OrderItem {
    +int quantity
    +Decimal price
  }
  User "1" --> "*" Order
  Category "1" --> "*" Product
  Order "1" --> "*" OrderItem
  Product "1" --> "*" OrderItem
```

---

## API

Interactive documentation: http://localhost:5000/api/v1  
Postman: [`docs/postman/FloraShop.postman_collection.json`](docs/postman/FloraShop.postman_collection.json)

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | public | Create user, return JWT |
| POST | `/api/v1/auth/login` | public | Sign in |
| GET | `/api/v1/products` | public | List catalog |
| POST | `/api/v1/products` | admin JWT | Create product |
| PUT / DELETE | `/api/v1/products/<id>` | admin JWT | Update or delete product |
| GET | `/api/v1/categories` | public | List categories |
| POST / PUT / DELETE | `/api/v1/categories`… | admin JWT | Mutate categories |
| GET | `/api/v1/users` | admin JWT | List users (no password field) |
| GET | `/api/v1/payments/config` | public | `test` or `stripe` mode |
| POST | `/api/v1/payments/checkout` | optional JWT | Create a paid or failed order |
| GET | `/api/v1/payments/orders` | admin JWT | List orders |

---

## Authentication and security

- Passwords are hashed with Werkzeug. Legacy bcrypt and leftover plaintext are verified, then upgraded.
- Login and register return a JWT (HS256) stored in `localStorage` and sent as `Authorization: Bearer`.
- Claims: `sub`, `email`, `is_admin`, `exp`.
- The admin page is hidden in the browser **and** every mutation is checked on the server. A customer token cannot create categories or list all orders.
- User JSON never includes `password`.
- Checkout totals come from the database.
- Card numbers are not stored; at most `card_last4`.
- Stripe keys live only in the environment. Empty keys use documented test cards. No live charge in the default demo.
- CORS is limited to localhost.
- `.env` is gitignored; only `.env.example` is committed.

Remaining risks: JWT in `localStorage` (XSS), no CSRF on cookie-less Bearer, no login rate limit, leftover `ADMIN_TOKEN` header.

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | HTML5, CSS3, vanilla JavaScript, Jinja2 |
| Backend | Python 3.10+, Flask 3, Flask-RESTX, Flask-Migrate |
| Auth | PyJWT (HS256), Werkzeug hashes, bcrypt for legacy rows |
| Database | SQLite locally, PostgreSQL when `DATABASE_URL` points to it |
| ORM | SQLAlchemy 2, `Numeric(10, 2)` for money |
| Payments | Built-in test processor, optional Stripe |
| Tests | `unittest`, `coverage` |
| Config | python-dotenv, Flask-CORS, Alembic |

Flask and Jinja keep pages and API in one process. RESTX provides Swagger. SQLite keeps a classroom machine free of PostgreSQL. Decimal types are the correct way to store euros. Test cards make the demonstration work without secrets.

**Decisions.** Server-side checkout. Per-user carts after a shared-cart bug. Sticky navigation instead of a floating bar. Profile menu as an overlay under the account icon. Demo users and bouquets re-seeded so `marie@test.com` / `marie123` and `/shop.html` always work.

---

## Testing

Strategy and evidence: [`docs/testing.md`](docs/testing.md). Last captured run: **23 tests OK** in [`docs/test-evidence/`](docs/test-evidence/).

Covered: registration and login hashing, demo seed (accounts and flower catalog), admin versus customer permissions, public catalog, checkout (success, decline, insufficient funds, invalid PAN, PayPal, subscription line, server-side prices, decimal cents, admin order list).

Not covered yet: live Stripe calls, email, browser end-to-end tests, reviews, load tests.

---

## Challenges and how they were solved

| Challenge | Kind | Resolution |
| --- | --- | --- |
| Front-end and API disagreed on cart identity | Technical | One `FloraCart` helper, per-account keys, checkout snapshot |
| Mixed password hashes in `users.password` | Technical | `check_password` accepts Werkzeug, bcrypt and plaintext; demo seed repairs Marie |
| Stripe keys missing in the classroom | Technical | Documented test cards when environment keys are empty |
| Money rounding | Technical | `Decimal` and `Numeric(10, 2)` |
| Logout menu stretched the navbar | Technical | Dropdown overlay under the account icon; leftover fixed-header padding removed |
| Empty shop after a clean SQLite start | Technical | Seed Fleurs Fraîches and Compositions on startup |
| Rebuilding every Wix page versus a working shop | Product | Cut CMS, geo and email; keep the purchase path |
| Presentation time including the live demo | Organisation | Timed story; skip the declined card if the clock runs out |

Difficult moments in code: empty checkout after cart keys became user-scoped; Marie locked out by bcrypt; binary floats; a committed virtualenv and a leftover Stripe key; the profile panel opening a gap under the header.

---

## Collaboration

Work lives on [Issercio/Demo-day](https://github.com/Issercio/Demo-day), branch `main`. Feature work is tested with `./run-tests.sh` before merge.

To show how the project is organised:

- GitHub history and this README
- [`docs/test-evidence/unittest-output.txt`](docs/test-evidence/unittest-output.txt)
- Swagger at `/api/v1` and the Postman collection
- Storefront captures in [`docs/screenshots/`](docs/screenshots/) (home, shop, account, checkout)

Issercio and Matthieu share this repository. Cadence for a demonstration: one local server, credentials written above, a fallback of tests plus this file if a deploy is down.

---

## What we would improve

- Store the cart on the server
- Click-and-collect slots and delivery zones
- Real email for receipts and password reset
- Seasonal editing of the homepage
- Playwright end-to-end tests
- PostgreSQL in CI
- A hosted instance and a recorded walkthrough as backup
- Remove or test leftover modules (`prices`, unmounted reviews) so coverage reflects the live code

---

## What we learned

**Technical.** Never trust a price from the browser. Store money as decimals. Support legacy password hashes or the demo account locks. An empty Stripe key must not crash checkout. Secrets do not belong in Git. A dropdown must overlay the page, not stretch the header.

**Non-technical.** A demonstration needs a story, not a click tour. Features that were specified and not built must be listed, or they look like defects. Twenty minutes including the demo forces cuts. Documentation is part of the product.

---

## Live demonstration

Marie forgot her mother’s birthday. The boutique in Sciez is closed. She opens Pivoine & Lilas.

1. Home — the boutique is open online.
2. Shop — filter a category, add one bouquet (demo catalog: Bouquet Pivoine, Bouquet Lilas, Roses jardin).
3. Sign in as `marie@test.com` / `marie123`. The cart is hers. Open the account icon: email and **Déconnexion** sit under the icon, the navbar does not grow.
4. Pay with `4242 4242 4242 4242`. The server recalculates the total. Status `paid`.
5. Optionally add *Éclat Mensuel* (€19.99).
6. Optionally show a declined card (`4000 0000 0000 0002`).
7. Sign in as `admin@florashop.com` / `admin123`, create a product, open **Commandes et paiements**, show Marie’s order.

If the interface fails: Swagger at `/api/v1` and `./run-tests.sh` still show checkout, authentication and admin guards.

The spoken presentation, including this walkthrough, stays inside **20 minutes**.

---

## Conclusion

Pivoine & Lilas is a florist shop that takes a real order: a customer can sign in, buy a bouquet, pay, subscribe, and the florist can manage the catalog and see the payment. The server owns the price. What is not built (click-and-collect, CMS, delivery zones, email) is listed here. The next work is operations, not another visual pass.

Screenshots: [home](docs/screenshots/accueil.png) · [shop](docs/screenshots/shop.png) · [account](docs/screenshots/account.png) · [checkout](docs/screenshots/checkout.png)

---

## Authors

- **Issercio** — [github.com/Issercio](https://github.com/Issercio)
- **Matthieu**

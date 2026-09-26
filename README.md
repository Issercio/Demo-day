# FloraShop

Boutique florale en ligne : le client choisit un bouquet, paie, et suit sa commande. Le fleuriste gère le catalogue, la vitrine et l’atelier depuis un back-office protégé.

![Accueil](docs/screenshots/accueil.png)

## Ce que fait le shop

**Côté client**
- Compte (inscription, vérification, mot de passe) ou achat en invité
- Catalogue photo : 7 univers (fleurs fraîches, compositions, séchées, plantes, mariage, deuil, cadeaux)
- Filtres par catégorie, couleur et prix
- Panier serveur, fusionné au compte à la connexion
- Paiement en ligne (cartes de test, ou Stripe.js + webhook si les clés Dashboard sont renseignées)
- Acompte 30 % (solde en boutique, par le client, ou marqué payé par le fleuriste)
- Date de retrait ou de livraison au paiement
- Abonnements : contrat atelier (prochaine livraison), sans Stripe Billing
- Suivi de commande (compte, ou invité avec email + n°)
- Facture PDF (HT / TVA / TTC), mail de commande, téléchargement client
- Formulaire Contact et devis évènementiel (inbox atelier)
- N° de suivi transporteur
- Livraison en France : tarif et délai métropole / DOM, transporteur saisi en admin, ou retrait atelier
- Code promo au paiement
- Prix soldés si le fleuriste les active

**Côté fleuriste**
- Catalogue : créer, modifier, supprimer, photo produit, stock
- Vitrine du shop : une saison, un thème, ou les deux
- Tableau du jour : à préparer, stock bas / rupture, prochains retraits
- Demandes contact : nouveau → lu → traité, réponse au client
- Identité légale sur une page à part (SIREN / adresse saisis par l’exploitant, jamais inventés), livraison et codes promo dans l’atelier
- Commandes : statut de paiement, préparation (`À préparer` → `Remise`), facture imprimable / PDF, remboursement, n° de suivi
- Accès admin réservé : un client ne peut pas ouvrir le back-office

![Boutique](docs/screenshots/shop.jpg)

![Paiement](docs/screenshots/checkout.png)

![Atelier](docs/screenshots/admin-today.png)

![Commandes](docs/screenshots/admin-orders.png)

## Lancer le projet

Python 3.10+. SQLite par défaut, PostgreSQL si `DATABASE_URL` le demande.

```bash
git clone https://github.com/Issercio/Demo-day.git
cd Demo-day
chmod +x setup.sh run.sh run-tests.sh
./setup.sh
./run.sh
```

Le shop écoute sur [http://localhost:5000](http://localhost:5000). HTTPS local : `./run-https.sh`. Tests : `./run-tests.sh`.

| Page | URL |
| --- | --- |
| Accueil | http://localhost:5000/accueil.html |
| Boutique | http://localhost:5000/shop.html |
| Panier | http://localhost:5000/panier.html |
| Paiement | http://localhost:5000/checkout.html |
| Commandes | http://localhost:5000/commandes.html |
| Contact | http://localhost:5000/contact.html |
| Admin | http://localhost:5000/admin.html |
| Identité (SIREN) | http://localhost:5000/identite.html |
| API | http://localhost:5000/api/v1 |

`./setup.sh` copie [`.env.example`](.env.example) vers `Demoday/.env` et génère `SECRET_KEY` / `JWT_SECRET_KEY` (`openssl rand -hex 32`). Ne jamais committer `.env`.

## Comptes de démonstration

| Rôle | Email | Mot de passe |
| --- | --- | --- |
| Client | `marie@test.com` | `marie123` |
| Client | `client@test.com` | `client123` |
| Fleuriste | `admin@florashop.com` | `admin123` |

Paiement accepté : `4242 4242 4242 4242`, date future, CVC `123`.  
Refusé : `4000 0000 0000 0002`. Fonds insuffisants : `4000 0000 0000 9995`.

Les totaux viennent de la base, jamais du navigateur. Sans clés Stripe, le PAN de test reste local. Avec Stripe, la carte passe par Stripe.js (jamais stockée ici).

## Mettre en ligne

Le dépôt n’invente pas d’URL publique, de clés Stripe ni de SIREN. Brancher un hébergeur, coller les vraies clés, saisir l’identité légale sur la page Identité.

**Docker Compose** (Postgres + gunicorn)

```bash
./setup.sh
docker compose up --build
```

Le shop écoute sur [http://localhost:5000](http://localhost:5000). `SECRET_KEY` vide → Flask en génère une, persistée dans le volume `instance`. Changer le mot de passe Postgres d’exemple hors démo.

**Render** — `render.yaml` : `SECRET_KEY` et `JWT_SECRET_KEY` en `generateValue`, `FORCE_HTTPS=1`. Relier le dépôt, déployer. L’URL Render devient l’adresse HTTPS du shop (webhook Stripe : `https://VOTRE_DOMAINE/api/v1/payments/webhook`). Renseigner `STRIPE_*` et `MAIL_*` dans le dashboard Render, sans les committer.

### Stripe.js + webhook

1. Compte Stripe Dashboard → clés `pk_test_` / `sk_test_` (ou live) dans `Demoday/.env`.
2. Endpoint webhook `https://VOTRE_DOMAINE/api/v1/payments/webhook`, secret `whsec_…`, événements `payment_intent.succeeded` et `payment_intent.payment_failed`.
3. HTTPS public (Render le force). En local : `./run-https.sh` + Stripe CLI si besoin.
4. Checkout charge alors Stripe.js (Card Element). Le montant PI = devis serveur (catalogue + livraison + promo + acompte). Le stock n’est consommé qu’au passage `pending` → `paid`.

Sans clés, le processeur de test (4242…) reste actif. PayPal sans `PAYPAL_CLIENT_ID` : sandbox local. SMS sans Twilio : le code est journalisé.

### SMTP (`MAIL_*`)

`MAIL_SERVER` + `MAIL_USER` / `MAIL_PASSWORD` + `MAIL_FROM`. Port 587 + `MAIL_STARTTLS=1`, ou 465 + `MAIL_SSL=1`. `MAIL_TO` = boîte atelier. Sans serveur, les mails de commande / contact sont journalisés, le paiement n’échoue pas.

### Identité légale et livraison

Admin → page Identité (`identite.html`) : SIREN (9 chiffres, Luhn, **vide par défaut**), adresse de siège, forme, capital, RCS, TVA. L’atelier (`admin.html`, onglet Boutique) garde transporteur, délai métropole (`24–48 h`), délai DOM (`3–5 jours ouvrés`), tarif DOM distinct du forfait métropole.

## Technique

| Couche | Choix |
| --- | --- |
| Front | HTML, CSS, JavaScript, Jinja2 |
| API | Flask 3, Flask-RESTX |
| Auth | JWT, mots de passe hashés, verrouillage après 5 échecs |
| Données | SQLAlchemy 2, `Numeric(10, 2)` pour l’argent |
| Paiement | Processeur de test, ou Stripe.js + webhook |
| Prod | gunicorn, Docker, Render |

Le navigateur affiche les pages et appelle `/api/v1`. La vitrine lue par le shop est celle posée par le fleuriste (`GET /api/v1/themes`). Le logo est servi en local (`/static/img/logo.png`), pas depuis un CDN.

## Tests

La suite reste dans `Demoday/tests/` (`test_accounts.py`, `test_admin_guard.py`, `test_checkout.py`, `test_shop_ops.py`, `test_shop_commerce.py`, `test_go_live.py`, `test_shop_ready.py`).

```bash
./run-tests.sh
```

Détail et preuves : [`docs/testing.md`](docs/testing.md).

## API principale

Documentation interactive : [http://localhost:5000/api/v1](http://localhost:5000/api/v1)

| Méthode | Chemin | Qui |
| --- | --- | --- |
| POST | `/api/v1/auth/register` · `/login` · `/verify` | public |
| GET | `/api/v1/products` · `/categories` · `/themes` | public |
| GET / PUT / DELETE | `/api/v1/cart` | public (header `X-Cart-Token`) ou JWT |
| POST | `/api/v1/contact` | public |
| GET / PATCH | `/api/v1/contact` | fleuriste |
| GET | `/api/v1/atelier/today` | fleuriste |
| GET / PUT | `/api/v1/settings` | public / fleuriste |
| GET | `/api/v1/shipping` · `/promo/quote` | public |
| GET / POST / PATCH | `/api/v1/promos` | fleuriste |
| POST | `/api/v1/payments/checkout` | public ou JWT (mode test) |
| POST | `/api/v1/payments/create-payment-intent` | public ou JWT (Stripe) |
| POST | `/api/v1/payments/confirm-payment` | JWT ou invité (email) |
| POST | `/api/v1/payments/webhook` | Stripe |
| POST | `/api/v1/payments/track` | public (email + n°) |
| GET | `/api/v1/payments/my-orders` | client |
| GET / PATCH | `/api/v1/payments/orders` | fleuriste |
| POST / PUT / DELETE | `/api/v1/products` · `/themes` · `/categories` | fleuriste |

## Auteur

[Dimitri Jaille](https://github.com/Issercio)

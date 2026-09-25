# Tests

FloraShop est testé avec **unittest** et le client Flask, sur une SQLite en mémoire (`DATABASE_URL=sqlite://`). Les pages HTML sont aussi lues pour vérifier les garde-fous UI.

## Lancer

```bash
./run-tests.sh
```

ou :

```bash
cd Demoday
source .venv/bin/activate
python3 -m coverage run --source=app -m unittest discover -s tests -v
python3 -m coverage report -m
```

Dernière capture : [test-evidence/unittest-output.txt](test-evidence/unittest-output.txt), [test-evidence/coverage-report.txt](test-evidence/coverage-report.txt).

Dernière exécution enregistrée : **101 tests, OK**.

## Fichiers

| Fichier | Ce qui est couvert |
| --- | --- |
| `tests/test_accounts.py` | Comptes démo, catalogue, auth, vitrine, verrouillage login, HTTPS |
| `tests/test_admin_guard.py` | Rôles, photos produits, page admin, facture |
| `tests/test_checkout.py` | Paiement, acompte, atelier, IDOR, suivi commandes |
| `tests/test_shop_ops.py` | Contact, panier serveur, stock, tableau du jour, marque FloraShop |

## Hors périmètre

- E2E navigateur (Cypress / Playwright)
- Stripe réel (clés vides en test)
- SMTP production
- PostgreSQL spécifique

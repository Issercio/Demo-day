# Demo-day / FloraShop

Guide rapide pour lancer le projet correctement en local.

## 1) Prérequis

- Python 3.10+
- PostgreSQL en local
- pip

## 2) Se placer dans le projet

```bash
cd Demoday
```

## 3) Créer et activer un environnement virtuel

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4) Installer les dépendances

```bash
pip install -r requirements.txt
```

## 5) Préparer la base de données

L'application utilise PostgreSQL avec cette URL dans la config:

`postgresql://postgres:root@localhost:5432/florashop`

Créer la base si nécessaire:

```bash
createdb florashop
```

Initialiser les tables et l'utilisateur admin:

```bash
python3 init_db.py
```

## 6) Lancer l'application (point d'entrée unique)

```bash
python3 run.py
```

Serveur attendu:

- http://localhost:5000

## 7) Pages utiles

- Accueil: /accueil.html
- Boutique: /shop.html
- Abonnements: /subscription.html
- Panier: /panier.html
- Swagger API: /api/v1

## Dépannage rapide

- Si le port 5000 est déjà utilisé, arrêter l'autre processus puis relancer.
- Si la base ne répond pas, vérifier que PostgreSQL est démarré et que les identifiants correspondent.
#!/bin/bash

echo "🔄 Test de la base de données FloraShop..."

# Vérifier si PostgreSQL est en cours d'exécution
if ! systemctl is-active --quiet postgresql; then
    echo "⚠️  PostgreSQL n'est pas démarré. Démarrage..."
    sudo service postgresql start
fi

# Création de la base de données et insertion des données
echo "🗄️  Configuration de la base de données..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS florashop;"
sudo -u postgres psql -c "CREATE DATABASE florashop;"
sudo -u postgres psql -d florashop -f sql/create_tables.sql
sudo -u postgres psql -d florashop -f sql/insert_initial_data.sql

# Test de la connexion avec Python
echo "🔍 Test de la connexion..."
python3 -m app

echo "✨ Terminé!"

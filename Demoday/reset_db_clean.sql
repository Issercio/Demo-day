-- Suppression complète et recréation propre de la base

-- Supprimer toutes les tables existantes
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Recréer les tables avec des IDs auto-incrémentés propres
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
    stock INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insérer uniquement l'utilisateur admin
INSERT INTO users (username, email, password, is_admin) 
VALUES (
    'admin',
    'admin@florashop.com',
    '$2b$12$tXuY6/3rkTWjgGqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.',
    TRUE
);

-- Aucune catégorie ou produit par défaut - tout sera créé via l'interface admin

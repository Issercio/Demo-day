DROP DATABASE IF EXISTS florashop;
CREATE DATABASE florashop;
USE florashop;

-- Supprimer les tables dans l'ordre pour éviter les erreurs de clés étrangères
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);

-- Ajout de l'utilisateur admin avec password = admin123
INSERT INTO users (username, email, password, is_admin) 
VALUES (
    'admin',
    'admin@florashop.com',
    '$2b$12$tXuY6/3rkTWjgGqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.',
    TRUE
);
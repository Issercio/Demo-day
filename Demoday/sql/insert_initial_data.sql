-- Insertion de l'utilisateur administrateur
INSERT INTO users (id, email, password, first_name, last_name, is_admin)
VALUES (
    gen_random_uuid(), 
    'admin@florashop.com',
    '$2b$12$tXuY6/3rkTWjgGqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.', -- mot de passe haché
    'Admin',
    'Floral',
    TRUE
);

-- Insertion des catégories initiales
INSERT INTO categories (id, name, description) VALUES
(gen_random_uuid(), 'Fleurs Fraîches', 'Bouquets et compositions de fleurs fraîches'),
(gen_random_uuid(), 'Vases', 'Collection de vases décoratifs'),
(gen_random_uuid(), 'Parfums', 'Parfums d''ambiance et bougies parfumées');

-- Insertion de produits exemple
INSERT INTO products (id, category_id, name, price, description, stock) VALUES
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Fleurs Fraîches'), 'Bouquet Roses Rouges', 29.99, 'Magnifique bouquet de 12 roses rouges', 10),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Vases'), 'Vase Cristal', 49.99, 'Vase en cristal transparent', 5);

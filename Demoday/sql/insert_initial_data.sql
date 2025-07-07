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
(gen_random_uuid(), 'Parfums', 'Parfums d''ambiance et bougies parfumées'),
(gen_random_uuid(), 'Plantes d''Intérieur', 'Plantes vertes et fleuries pour la maison'),
(gen_random_uuid(), 'Accessoires', 'Accessoires de jardinage et décoration'),
(gen_random_uuid(), 'Compositions', 'Arrangements floraux pour événements'),
(gen_random_uuid(), 'Cadeaux', 'Coffrets cadeaux et paniers garnis');

-- Insertion de produits exemple
INSERT INTO products (id, category_id, name, price, description, stock) VALUES
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Fleurs Fraîches'), 'Bouquet Roses Rouges', 29.99, 'Magnifique bouquet de 12 roses rouges', 10),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Fleurs Fraîches'), 'Bouquet Printanier', 34.99, 'Mélange coloré de fleurs de saison', 8),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Fleurs Fraîches'), 'Lys Blancs', 39.99, 'Élégant bouquet de lys orientaux', 5),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Vases'), 'Vase Cristal', 49.99, 'Vase en cristal transparent', 5),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Vases'), 'Vase Moderne', 39.99, 'Vase design en céramique', 7),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Parfums'), 'Bougie Jasmin', 19.99, 'Bougie parfumée au jasmin', 15),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Plantes d''Intérieur'), 'Orchidée', 45.99, 'Orchidée Phalaenopsis', 6),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Accessoires'), 'Kit Jardinage', 24.99, 'Kit d''outils de jardinage', 12),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Compositions'), 'Centre de Table', 59.99, 'Composition florale pour table', 4),
(gen_random_uuid(), (SELECT id FROM categories WHERE name = 'Cadeaux'), 'Coffret Floral', 69.99, 'Coffret cadeau avec fleurs et chocolats', 3);

-- Insertion de données de test
INSERT INTO test_table (id, name) VALUES
(gen_random_uuid(), 'Test 1'),
(gen_random_uuid(), 'Test 2'),
(gen_random_uuid(), 'Test 3');

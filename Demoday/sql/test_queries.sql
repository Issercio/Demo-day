-- Test de récupération des produits avec leurs catégories
SELECT p.*, c.name as category_name
FROM products p
JOIN categories c ON p.category_id = c.id;

-- Test de recherche de produits disponibles en livraison
SELECT *
FROM products
WHERE delivery_available = TRUE;

-- Test de recherche de produits par catégorie
SELECT p.*
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE c.name = 'Fleurs Fraîches';

-- Test de recherche des produits en stock
SELECT *
FROM products
WHERE stock > 0;

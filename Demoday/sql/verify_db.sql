-- Vérification des tables
SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'users'
) THEN 1 ELSE 0 END AS users_exists;

SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'categories'
) THEN 1 ELSE 0 END AS categories_exists;

SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_name = 'products'
) THEN 1 ELSE 0 END AS products_exists;

-- Vérification de l'admin
SELECT COUNT(*) FROM users WHERE is_admin = TRUE;

-- Vérification des contraintes
SELECT
    tc.constraint_name, tc.table_name, kcu.column_name
FROM
    information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.table_name IN ('users', 'categories', 'products');

-- Vérification des données initiales
SELECT COUNT(*) as categories_count FROM categories;
SELECT COUNT(*) as products_count FROM products;

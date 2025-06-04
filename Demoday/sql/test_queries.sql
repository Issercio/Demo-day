-- Sélectionner tous les utilisateurs
SELECT * FROM User;

-- Insérer un nouveau lieu
INSERT INTO Place (id, title, price, owner_id) 
VALUES (lower(hex(randomblob(16))), 'New Place', 100.00, '36c9050e-ddd3-4c3b-9731-9f487208bbc1');

-- Mettre à jour un lieu
UPDATE Place SET price = 150.00 WHERE title = 'New Place';

-- Supprimer un lieu
DELETE FROM Place WHERE title = 'New Place';

-- Vérifier que l'admin est créé avec is_admin = TRUE
SELECT * FROM User WHERE is_admin = TRUE;

-- Vérifier que les amenités sont insérées correctement
SELECT * FROM Amenity;

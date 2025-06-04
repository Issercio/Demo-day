-- Insertion de l'utilisateur administrateur
INSERT INTO User (id, email, first_name, last_name, password, is_admin)
VALUES ('36c9050e-ddd3-4c3b-9731-9f487208bbc1', 'admin@hbnb.io', 'Admin', 'HBnB', '$2b$12$tXuY6/3rkTWjgqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.', TRUE);

-- Insertion des amenités initiales
INSERT INTO Amenity (id, name) VALUES
(lower(hex(randomblob(16))), 'WiFi'),
(lower(hex(randomblob(16))), 'Swimming Pool'),
(lower(hex(randomblob(16))), 'Air Conditioning');

-- Suppression des tables existantes
DROP TABLE IF EXISTS Place_Amenity;
DROP TABLE IF EXISTS Review;
DROP TABLE IF EXISTS Place;
DROP TABLE IF EXISTS Amenity;
DROP TABLE IF EXISTS User;

-- Création de la table User
CREATE TABLE User (
    id CHAR(36) PRIMARY KEY,
    first_name VARCHAR(255) NOT NULL,
    last_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE
);

-- Création de la table Place
CREATE TABLE Place (
    id CHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    owner_id CHAR(36),
    FOREIGN KEY (owner_id) REFERENCES User(id)
);

-- Création de la table Review
CREATE TABLE Review (
    id CHAR(36) PRIMARY KEY,
    text TEXT NOT NULL,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    user_id CHAR(36),
    place_id CHAR(36),
    FOREIGN KEY (user_id) REFERENCES User(id),
    FOREIGN KEY (place_id) REFERENCES Place(id),
    UNIQUE (user_id, place_id)
);

-- Création de la table Amenity
CREATE TABLE Amenity (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

-- Création de la table Place_Amenity
CREATE TABLE Place_Amenity (
    place_id CHAR(36),
    amenity_id CHAR(36),
    PRIMARY KEY (place_id, amenity_id),
    FOREIGN KEY (place_id) REFERENCES Place(id),
    FOREIGN KEY (amenity_id) REFERENCES Amenity(id)
);

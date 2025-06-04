-- Tables principales
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_admin BOOLEAN DEFAULT FALSE
);

CREATE TABLE categories (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE products (
    id UUID PRIMARY KEY,
    category_id UUID REFERENCES categories(id),
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    image_url VARCHAR(255),
    stock INTEGER NOT NULL DEFAULT 0,
    delivery_available BOOLEAN DEFAULT TRUE,
    click_collect_available BOOLEAN DEFAULT TRUE
);

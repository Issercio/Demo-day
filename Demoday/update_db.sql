IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns 
    WHERE table_name = 'users' AND column_name = 'password'
)
BEGIN
    ALTER TABLE users ADD password VARCHAR(255);
END;

UPDATE users SET password = '$2b$12$tXuY6/3rkTWjgGqW0QTQzqu/p7Zv4iLF0YLcLIQEHgGOXXIRMbmml.' 
WHERE email = 'admin@florashop.com';

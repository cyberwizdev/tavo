-- Migration: Create users table with basic fields
-- Created: 2025-08-30T09:47:44.491894


-- UP

                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX idx_users_email ON users(email);
                CREATE INDEX idx_users_username ON users(username);
                

-- DOWN

                DROP INDEX IF EXISTS idx_users_username;
                DROP INDEX IF EXISTS idx_users_email;
                DROP TABLE IF EXISTS users;
                

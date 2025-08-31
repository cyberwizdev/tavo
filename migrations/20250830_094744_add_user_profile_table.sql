-- Migration: Add user profiles table
-- Created: 2025-08-30T09:47:44.494415
-- Depends: create_users_table

-- UP

                CREATE TABLE user_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    first_name VARCHAR(50),
                    last_name VARCHAR(50),
                    bio TEXT,
                    avatar_url VARCHAR(500),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                
                CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
                

-- DOWN
DROP TABLE IF EXISTS user_profiles;

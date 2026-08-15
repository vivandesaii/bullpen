ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
UPDATE users SET username = 'Trader #' || id WHERE username IS NULL;
ALTER TABLE users ALTER COLUMN username SET NOT NULL;
ALTER TABLE users ADD CONSTRAINT users_username_unique UNIQUE (username);

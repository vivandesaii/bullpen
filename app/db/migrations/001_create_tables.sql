
-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY, 
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    balance NUMERIC(15,2) NOT NULL DEFAULT 100000.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- Documents
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    s3_key TEXT UNIQUE NOT NULL,
    document_type TEXT NOT NULL,
    content_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trades
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_id UUID NOT NULL UNIQUE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price NUMERIC(15,4) NOT NULL CHECK (price > 0),
    direction VARCHAR(4) NOT NULL CHECK (direction IN ('buy', 'sell')),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('completed', 'failed', 'pending')),
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Holdings
CREATE TABLE IF NOT EXISTS holdings (
    user_id INTEGER NOT NULL REFERENCES users(id),
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    avg_price NUMERIC(15,4) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol)
);

-- Leaderboard snapshots
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    return_pct NUMERIC(10,4) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

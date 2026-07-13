# Bullpen

A production-grade paper trading competition API built for UofT and Rotman 
Commerce students. Track your portfolio, compete on the leaderboard, and 
see how your returns stack up against other students.

## What it does

- Track a virtual $100,000 portfolio in real time
- Submit buy/sell trades processed asynchronously
- Cache live stock prices with sub-10ms response times
- Rate limit the API per user to prevent abuse
- Store monthly portfolio statements as downloadable PDFs
- Compete on a leaderboard ranked by portfolio return %

## Tech stack

| Technology | Why |
|------------|-----|
| FastAPI    | Async Python API framework |
| PostgreSQL | Users, portfolios, trades, holdings |
| Redis      | Price caching, session auth, rate limiting, leaderboard |
| AWS SQS    | Async trade processing decoupled from API response |
| AWS S3     | Portfolio statements and trade confirmation PDFs |
| Docker     | One command spins up entire local environment |

## Project structure

### Why this structure

**routes/** handles HTTP only — receives request, calls a service,
returns response. No business logic lives here.

**services/** does the actual work — cache operations, trade logic,
S3 uploads, SQS publishing. Can be called from routes, workers,
or tests without caring where the call came from.

**workers/** runs separately from the web server — pulls trades
from SQS and processes them in the background so the API
stays fast.

**models/** defines what data looks like in Postgres — imported
by services and routes to know the shape of users, trades,
portfolios, holdings.

**redis_client.py at app level** — one shared connection pool
imported everywhere. Creating multiple pools would exhaust
Redis connections under load.

## Architecture decisions

**Cache-aside for prices:** yfinance lookups average 200-300ms.
Redis caches prices with a 5s TTL so repeated requests return
in under 10ms. Cache invalidates automatically on TTL expiry.

**SQS for trade submission:** trade execution touches multiple
systems (price lookup, balance check, holdings update, trade
record). Doing this synchronously blocks the HTTP response.
SQS decouples submission from execution — user gets an instant
response, worker handles the rest. Failed trades retry
automatically, dead trades go to a DLQ.

**FIFO queue with per-user MessageGroupId:** guarantees a user's
buy is processed before their sell on the same stock, while
different users process in parallel.

**Session storage in Redis over JWT:** sliding expiration means
active users never get logged out. logout-all-devices is one
Redis set delete instead of a token blacklist.

**Rate limiting via Redis INCR + pipeline:** atomic increment
and TTL check in a single round trip. Resets per window without
a cron job.

## Running locally

```bash
cp .env.example .env
# fill in .env values
docker-compose up
```

## API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /auth/register | Create account |
| POST | /auth/login | Login, receive session token |
| POST | /auth/logout | Invalidate current session |
| POST | /auth/logout-all | Invalidate all devices |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /portfolio/me | Holdings, balance, return % |

### Trades
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /trades | Submit buy/sell → queued via SQS |
| GET | /trades/{trade_id} | Check trade status (coming soon) |

### Prices
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /prices/{symbol} | Current price → Redis cached |

### Leaderboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /leaderboard | Top N users by return % |
| GET | /leaderboard/{user_id} | Individual rank and score |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /documents/{user_id} | List portfolio statements |
| GET | /documents/{user_id}/{filename} | Presigned S3 download URL |

## Modules built

- [x] Redis: caching, sessions, rate limiting, leaderboard
- [X] SQS: async trade processing
- [ ] S3: document storage
- [ ] Docker: containerization
- [ ] PostgreSQL: schema, transactions, indexes
# WealthLens

A production-grade portfolio intelligence API built to mirror 
the infrastructure patterns used in financial applications at scale.

## What it does

- Track stock portfolios in real time
- Process trades asynchronously
- Answer natural language questions about your portfolio
- Stream live price events

## Tech stack

| Technology | Why |
|------------|-----|
| Redis      | Cache prices and balances, session auth, rate limiting |
| AWS SQS    | Async trade processing, decoupled from API |
| AWS S3     | Portfolio statements and trade confirmations |
| Kafka      | Real-time price event streaming |
| RAG        | Natural language portfolio queries with citations |
| Docker     | Consistent local and production environment |

## Project structure

### Why this structure

**routes/** handles HTTP only — receives request, calls a service, 
returns response. No business logic lives here.

**services/** does the actual work — cache operations, trade logic, 
S3 uploads. Can be called from routes, workers, or tests without 
caring where the call came from.

**workers/** runs separately from the web server — pulls trades 
from SQS and processes them in the background so the API 
stays fast.

**models/** defines what data looks like in Postgres — imported 
by services and routes to know the shape of users, trades, portfolios.

**redis_client.py at app level** — one shared connection pool 
imported everywhere. Creating it in multiple files would open 
multiple pools and exhaust Redis connections under load.

## Architecture decisions

**Redis over pure Postgres reads** — 50,000 users hitting 
/portfolio simultaneously would overwhelm Postgres. Redis 
caches balances with a short TTL and invalidates on every trade.

**SQS for trades** — trade processing is slow and should not 
block the HTTP response. User submits trade, API returns 
immediately, worker processes in background.

**Kafka over SQS for prices** — price events need ordered, 
replayable history. SQS doesn't guarantee order. Kafka does.

## Running locally

```bash
cp .env.example .env
docker-compose up
```

## API endpoints


## Modules built

- [x] Redis — caching, sessions, rate limiting
- [ ] SQS — async trade processing
- [ ] S3 — document storage
- [ ] Docker — containerization
- [ ] Kafka — price streaming
- [ ] LLM — AI endpoints
- [ ] RAG — retrieval pipeline
- [ ] CI/CD — automated deployment
- [ ] AWS — production infrastructure
- [ ] Postgres — optimized schema

# Paper Trading API

A paper-trading backend built with **FastAPI**, **PostgreSQL** and **SQLAlchemy**. Users buy and sell stocks with virtual cash, and the API tracks their positions, average cost, and realized and unrealized P&L. The focus is on correctness under concurrency and on measured performance.

> **Status:** work in progress. Trading, portfolio and history work today. A simulated price engine, JWT auth and a limit-order matching engine are next (see [Roadmap](#roadmap)).

## Features

- Buy and sell endpoints with validation (symbol, positive integer quantity)
- Portfolio view: cash, holdings, weighted average price, market value, unrealized and realized P&L
- Trade history, newest first, with a `limit` parameter (default 50, max 200)
- All money is `Decimal` / `NUMERIC(15, 2)`, never floats
- Every trade runs in one database transaction with rollback on any error

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI, Pydantic |
| Database | PostgreSQL, SQLAlchemy 2.x |
| Testing | pytest, FastAPI `TestClient` |
| Load testing | Locust |

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stocks` | Available symbols and current prices |
| GET | `/api/portfolio` | Cash, holdings, market value, P&L |
| POST | `/api/trade/buy` | Body: `{"symbol": "TCS", "quantity": 1}` |
| POST | `/api/trade/sell` | Same body as buy |
| GET | `/api/trades?limit=50` | Latest trades, newest first |

Interactive docs are available at `http://127.0.0.1:8000/docs` while the server is running.

## Design decisions

**Race-condition safety.** Each trade locks the user's row with `SELECT ... FOR UPDATE` and re-reads it before checking cash or shares, so parallel requests cannot overspend. This is verified by `test_concurrency.py`: with 100,000 cash and TCS at 3,500, 40 parallel buys produce exactly 28 successes and 12 rejections, and the final cash matches the arithmetic.

**Money handling.** `Decimal` throughout, quantized to 2 places, with `NUMERIC` columns in Postgres. Average price is recomputed as a weighted average on each buy, and realized P&L is booked on each sell.

**Database constraints.** `CHECK` constraints on `side`, `quantity > 0` and `price > 0`, plus a composite index on `trades (user_id, id)` so the "latest trades for a user" query reads straight from the index.

## Performance

Measured with Locust (mixed reads and buy/sell tasks, 50 concurrent users, no wait time) on a single laptop. The load generator, uvicorn and Postgres all shared the same CPU, so treat the numbers as relative comparisons, not absolute capacity.

| Experiment | Result |
|---|---|
| Baseline, 1 worker (30 s) | ~200 req/s, aggregated p95 470 ms |
| SQLAlchemy pool size 15 to 20 | No measurable change, so the pool was not the bottleneck |
| 4 uvicorn workers | ~380 req/s over the first 30 s. Read medians dropped sharply (`/api/stocks` 82 ms to 6 ms). Write p95 rose to ~2.8 s because every user locked the same account row |
| Paginated `/api/trades` + composite index (90 s) | Aggregated p95 1.6 s to 270 ms, max latency 5.5 s to 0.5 s |

**Findings**

- The first bottleneck was single-process CPU, fixed by running multiple workers.
- Trades on one account serialize on its row lock. This is the cost of correctness, and it should mostly disappear once users trade on separate accounts.
- The unbounded `/api/trades` query made throughput decay over a long run. Several changes were applied together, so the gain is not attributed to the index alone.

## Getting started

Requires Python 3.11+ and a running PostgreSQL instance.

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

pip install fastapi uvicorn sqlalchemy psycopg2-binary pytest httpx locust
```

Configure the database connection in `database.py` (or via a `DATABASE_URL` environment variable if you use one), create the tables, and seed a user named `trader1` with 100,000 cash.

```bash
uvicorn main:app                 # development
uvicorn main:app --workers 4     # multiple workers (set pool_size so workers x pool_size stays under Postgres max_connections)
```

## Testing

```bash
pytest test_concurrency.py -v
```

The test resets `trader1` to 100,000 cash and deletes that user's trades and positions, so run it against a development database only.

### Load test

```bash
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 50 -r 10 -t 90s --csv results
```

## Project structure

```
main.py              API routes and trade execution
database.py          Engine, session factory, connection pool
models.py            User, Position, Trade models
test_concurrency.py  Concurrent-buy correctness test
locustfile.py        Load test scenarios
```

## Roadmap

- [ ] Simulated price engine: each stock follows its own function, replacing the fixed prices
- [ ] Limit-order matching engine (price-time priority, heap-based bids and asks, cancel support) with a pytest suite and orders/sec benchmark
- [ ] `orders` table, and trades with separate buyer and seller
- [ ] JWT authentication and per-user accounts
- [ ] WebSocket feed for live prices and order book updates
- [ ] Bot traders for market liquidity
- [ ] Docker Compose, CI with GitHub Actions
- [ ] Valkey/Redis for shared price state and a leaderboard

## Limitations

- Prices are currently fixed values, and orders fill instantly against the house.
- Authentication is a hardcoded user (`trader1`), so the API is for local development only.
- Benchmarks come from a single laptop and are not representative of production hardware.

## License

MIT

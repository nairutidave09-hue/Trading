from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import select, delete
from database import SessionLocal
from main import app
from models import User, Trade, Position

START_CASH = Decimal("100000.00")
PRICE = Decimal("3500.00")


def reset_user():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "trader1"))
        db.execute(delete(Trade).where(Trade.user_id == user.id))
        db.execute(delete(Position).where(Position.user_id == user.id))
        user.cash = START_CASH
        db.commit()


def buy(_):
    with TestClient(app) as client:
        return client.post(
            "/api/trade/buy", json={"symbol": "TCS", "quantity": 1}
        ).status_code


def test_no_overspend():
    reset_user()
    with ThreadPoolExecutor(max_workers=20) as ex:
        codes = list(ex.map(buy, range(40)))

    ok = codes.count(200)
    assert ok == 28, f"expected 28 successes, got {ok}"
    assert codes.count(400) == 12

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == "trader1"))
        assert user.cash == START_CASH - PRICE * ok
        assert user.cash >= 0

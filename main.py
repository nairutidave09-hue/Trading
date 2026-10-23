from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Trade, Position

app = FastAPI(title="Paper Trading API")


# Fixed stock prices for learning
STOCKS = {
    "TCS": Decimal("3500.00"),
    "RELIANCE": Decimal("1400.00"),
    "INFY": Decimal("1800.00"),
}


# Provide a database session to each request
def get_db():
    db = SessionLocal()
    try:
        yield db  # to close the session after executing
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.username == "trader1"))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Validate incoming trade requests
class TradeRequest(BaseModel):
    symbol: str
    quantity: int = Field(gt=0)


@app.get("/")
def home():
    return {"message": "Paper Trading API is running"}


# List available stocks
@app.get("/api/stocks")
def get_stocks():
    return {symbol: {"price": str(price)} for symbol, price in STOCKS.items()}


# View cash and current holdings
@app.get("/api/portfolio")
def get_portfolio(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    positions = db.scalars(select(Position).where(Position.user_id == user.id)).all()

    if positions is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    holdings = {}
    market_value_total = Decimal("0")
    unrealized_total = Decimal("0")
    realized_total = Decimal("0")

    for p in positions:  # need a list
        realized_total += p.realized_pnl
        if p.quantity == 0:
            continue

        ltp = STOCKS.get(p.symbol, Decimal("0"))
        value = ltp * p.quantity
        unrealized = (ltp - p.avg_price) * p.quantity

        market_value_total += value
        unrealized_total += unrealized
        holdings[p.symbol] = {
            "quantity": p.quantity,
            "avg_price": str(p.avg_price.quantize(Decimal("0.01"))),
            "ltp": str(ltp),
            "market_value": str(value.quantize(Decimal("0.01"))),
            "unrealized_pnl": str(unrealized.quantize(Decimal("0.01"))),
        }

    return {
        "username": user.username,
        "cash": str(user.cash),
        "holdings": holdings,
        "market_value": str(market_value_total.quantize(Decimal("0.01"))),
        "total_equity": str((user.cash + market_value_total).quantize(Decimal("0.01"))),
        "unrealized_pnl": str(unrealized_total.quantize(Decimal("0.01"))),
        "realized_pnl": str(realized_total),
    }


# Shared logic for buying and selling
def execute_trade(side: str, request: TradeRequest, db: Session, current_user: User):
    symbol = request.symbol.upper()
    if symbol not in STOCKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stock symbol: {symbol}",
        )
    try:  # any prob solved at last moment, rollback to previous state
        # Lock the user row; populate_existing forces fresh values after the lock is acquired
        user = db.scalar(
            select(User)
            .where(User.id == current_user.id)
            .with_for_update()  # lock
            .execution_options(populate_existing=True)
        )

        price = STOCKS[symbol]
        total = price * request.quantity

        position = db.get(Position, (user.id, symbol))
        if position is None:
            position = Position(
                user_id=user.id,
                symbol=symbol,
                quantity=0,
                avg_price=Decimal("0"),
                realized_pnl=Decimal("0"),
            )
            db.add(position)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        if side == "BUY":
            if user.cash < total:
                raise HTTPException(
                    status_code=400,
                    detail="Insufficient cash",
                )

            new_qty = position.quantity + request.quantity
            position.avg_price = (
                ((position.avg_price * position.quantity) + total) / new_qty
            ).quantize(Decimal("0.01"))
            position.quantity = new_qty
            user.cash -= total

        else:
            if position.quantity < request.quantity:
                raise HTTPException(
                    status_code=400, detail="Insufficient shares to sell"
                )

            position.realized_pnl += (
                (price - position.avg_price) * request.quantity
            ).quantize(Decimal("0.01"))
            position.quantity -= request.quantity
            if position.quantity == 0:
                position.avg_price = Decimal("0")
            user.cash += total

        db.add(
            Trade(
                user_id=user.id,
                symbol=symbol,
                side=side,
                quantity=request.quantity,
                price=price,
            )
        )
        db.commit()

    except Exception:
        db.rollback()
        raise  # to raise a problem tell to fastapi as returns 500 error

    # Transaction commits automatically on successful exit
    return {
        "message": f"{side} successful",
        "symbol": symbol,
        "quantity": request.quantity,
        "price": str(price),
        "total": str(total),
        "side": side,
    }


@app.post("/api/trade/buy")
def buy_stock(
    request: TradeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return execute_trade("BUY", request, db, current_user)


@app.post("/api/trade/sell")
def sell_stock(
    request: TradeRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return execute_trade("SELL", request, db, current_user)


# View all trades, newest first
@app.get("/api/trades")
def get_trades(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    trades = db.scalars(
        select(Trade)
        .where(Trade.user_id == current_user.id)
        .order_by(Trade.id.desc())
        .limit(limit)
    ).all()

    return [
        {
            "id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side,
            "quantity": trade.quantity,
            "price": str(trade.price),
        }
        for trade in trades
    ]

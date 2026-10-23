from decimal import Decimal

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Numeric,
    Integer,
    ForeignKey,
    Index,
    CheckConstraint,
    func,
    DateTime,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    cash = Column(Numeric(15, 2), nullable=False, default=1000000.00)

    __table_args__ = (CheckConstraint("cash>0"),)
    trades = relationship("Trade", back_populates="user")
    positions = relationship("Position", back_populates="user")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(String(4), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(15, 2), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("side IN ('BUY', 'SELL')"),
        CheckConstraint("quantity > 0"),
        CheckConstraint("price > 0"),
        Index("idx_trades_user_latest", "user_id", "id"),
    )

    user = relationship("User", back_populates="trades")


class Position(Base):
    __tablename__ = "positions"

    user_id = Column(BigInteger, ForeignKey("users.id"), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    quantity = Column(Integer, nullable=False, default=0)
    avg_price = Column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    realized_pnl = Column(Numeric(15, 2), nullable=False, default=Decimal("0"))

    __table_args__ = (CheckConstraint("quantity >= 0"),)

    user = relationship("User", back_populates="positions")

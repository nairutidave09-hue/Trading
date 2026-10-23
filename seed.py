
from sqlalchemy.orm import Session
from database import engine
from models import User

with Session(engine) as session:
    user = User(username="trader1", cash=1000000.00)

    session.add(user)
    session.commit()
    session.refresh(user)

    print("User created!")
    print("ID:", user.id)
    print("Username:", user.username)
    print("Cash:", user.cash)

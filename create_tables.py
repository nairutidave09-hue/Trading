# reset_db.py
from database import engine, Base, SessionLocal
import models
from models import User

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    db.add(User(username="trader1"))
    db.commit()

print("Reset done, trader1 created with default cash")
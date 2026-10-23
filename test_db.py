from database import engine

with engine.connect() as connection:
    print("Connected to PostgreSQL successfully!")
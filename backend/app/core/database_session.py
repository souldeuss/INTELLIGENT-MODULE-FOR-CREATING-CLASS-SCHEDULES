"""Database session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Використовуємо SQLite для локального тестування (замість PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./timetabling.db")

engine = create_engine(
    DATABASE_URL, 
    echo=False,  # Вимкнули детальні SQL логи для продуктивності
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency для отримання DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

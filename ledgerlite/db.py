from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_DEFAULT_URL = "sqlite:///./ledgerlite.db"

engine = create_engine(
    _DEFAULT_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_engine(url: str) -> None:
    """Replace the engine and session factory (used by tests)."""
    global engine, SessionLocal
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

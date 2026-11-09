import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import Request

from database_pool_policy import application_name,pool_options,install_idle_session_timeout
from performance_monitoring import install_sqlalchemy_performance_hooks

load_dotenv(Path(__file__).resolve().parent / ".env")


DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "xinshi_system")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    if not DB_PASSWORD:
        raise RuntimeError("DB_PASSWORD or DATABASE_URL environment variable is not set")
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine_options = {"pool_pre_ping": True}
if DATABASE_URL.startswith("postgresql"):
    engine_options.update(pool_options())
    engine_options["connect_args"] = {
        "connect_timeout": 5,
        "application_name": application_name("business"),
        "options": " ".join(
            [
                "-c timezone=Asia/Hong_Kong",
                f"-c statement_timeout={int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000'))}",
                f"-c lock_timeout={int(os.getenv('DB_LOCK_TIMEOUT_MS', '5000'))}",
                f"-c idle_in_transaction_session_timeout={int(os.getenv('DB_IDLE_TRANSACTION_TIMEOUT_MS', '60000'))}",
            ]
        )
    }
engine = create_engine(DATABASE_URL, **engine_options)
install_sqlalchemy_performance_hooks(engine)
install_idle_session_timeout(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(request: Request = None):
    db = SessionLocal()
    db.info['number_tokens'] = request.headers.get('X-Business-Number-Leases', '[]') if request else '[]'
    try:
        yield db
    finally:
        db.close()

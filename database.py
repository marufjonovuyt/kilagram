from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Mahalliy test uchun SQLite (loyiha papkasida chat.db fayli ochiladi)
SQLALCHEMY_DATABASE_URL = "sqlite:///./chat.db"

# Render/PostgreSQL uchun (keyinchalik ishlatiladi):
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@host/dbname"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Baza sessiyasini boshqarish uchun helper
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel

app = FastAPI()

# CORS ruxsatlari
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# DATABASE_URL ni aniqroq qilib olish
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chat.db")

# Agar URL postgres bo'lsa, connect_args ni bo'sh qoldiramiz, aks holda sqlite uchun sozlamani qo'shamiz
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

# Foydalanuvchi modeli
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    phone = Column(String)

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class RegisterSchema(BaseModel):
    username: str
    password: str
    phone: str

@app.post("/api/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username.lower()).first():
        raise HTTPException(400, "Username band")
    user = User(username=data.username.lower(), password_hash=pwd_context.hash(data.password), phone=data.phone)
    db.add(user)
    db.commit()
    return {"status": "ok"}

@app.get("/")
def serve_index():
    return FileResponse("index.html")
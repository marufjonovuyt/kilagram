import os
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chat.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Frontend
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

# API Endpoints
@app.post("/api/register")
def register(data: dict, db: Session = SessionLocal()):
    # Bu yerda Register logikasi bo'ladi
    user = User(username=data["username"].lower(), password_hash=pwd_context.hash(data["password"]), phone=data["phone"])
    db.add(user); db.commit()
    return {"status": "ok"}

@app.post("/api/login")
def login(data: dict, db: Session = SessionLocal()):
    # Oddiy login logikasi
    user = db.query(User).filter(User.username == data["phone_or_user"].lower()).first()
    if not user: raise HTTPException(400, "Foydalanuvchi topilmadi")
    return {"token": user.username, "username": user.username}

@app.get("/api/profile")
def profile(token: str):
    return {"username": token, "phone": "0000000", "is_admin": True}

@app.get("/api/rooms")
def get_rooms():
    return [{"id": 1, "name": "Umumiy chat", "is_group": True}]

# WebSocket
@app.websocket("/ws/{room_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
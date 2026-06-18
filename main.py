import os
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel

# Pydantic modellari
class RegisterSchema(BaseModel):
    username: str
    password: str
    phone: str

class LoginSchema(BaseModel):
    phone_or_user: str
    password: str

# App va DB sozlamalari
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
DATABASE_URL = "sqlite:///./chat.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    phone = Column(String)

Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Routes
@app.post("/api/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username.lower()).first():
        raise HTTPException(400, "Username band")
    user = User(username=data.username.lower(), password_hash=pwd_context.hash(data.password), phone=data.phone)
    db.add(user); db.commit()
    return {"status": "ok"}

@app.post("/api/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.phone_or_user.lower()).first()
    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(400, "Login yoki parol xato")
    return {"token": user.username}

@app.get("/api/profile")
def profile(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if not user: raise HTTPException(404, "Topilmadi")
    return {"username": user.username, "phone": user.phone}

@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Server: {data}")
    except WebSocketDisconnect:
        pass

@app.get("/{rest_of_path:path}")
def serve_spa(rest_of_path: str):
    return FileResponse("index.html")
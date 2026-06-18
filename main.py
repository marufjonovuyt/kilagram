import os
import uuid
from datetime import datetime
from typing import List, Dict
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext

# 1. Sozlamalar
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# Render uchun DATABASE_URL, bo'lmasa SQLite
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chat.db")

# 2. Baza ulanishi
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Model klasslari
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    is_admin = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# 4. FastAPI Ilova
app = FastAPI()

# Uploads papkasini tekshirish
for folder in ["uploads", "uploads/images", "uploads/voice"]:
    if not os.path.exists(folder): os.makedirs(folder)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# 5. API Endpointlar
class RegisterSchema(BaseModel):
    username: str
    password: str
    phone: str

@app.post("/api/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    username = data.username.strip().lower()
    if db.query(User).filter(User.username == username).first(): 
        raise HTTPException(status_code=400, detail="Username band!")
    
    is_first = db.query(User).count() == 0
    new_user = User(
        username=username, 
        password_hash=pwd_context.hash(data.password), 
        phone=data.phone.strip(), 
        is_admin=is_first
    )
    db.add(new_user)
    db.commit()
    return {"status": "ok"}

# 6. WebSocket Manager
class ConnectionManager:
    def __init__(self): self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections: self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, room_id: int):
        self.active_connections[room_id].remove(websocket)
        
    async def broadcast(self, message: dict, room_id: int):
        for connection in self.active_connections.get(room_id, []): 
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{room_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == token).first()
    if not user: 
        await websocket.close()
        return
        
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.broadcast(data, room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
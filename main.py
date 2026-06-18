import os
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from pydantic import BaseModel
from typing import List, Dict

# Parol shifrlash uchun
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 1. Baza URL (Render-dan keladi, bo'lmasa SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chat.db")

# 2. Engine sozlamasi
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Foydalanuvchi modeli
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    is_admin = Column(Boolean, default=False)

Base.metadata.create_all(bind=engine)

# 4. FastAPI ilovasi
app = FastAPI()
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Bu hamma saytdan so'rovni qabul qiladi
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bosh sahifa (404 chiqmasligi uchun)
@app.get("/")
def read_root():
    return {"message": "Server ishlamoqda!"}

# Bazaga ulanish
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Ro'yxatdan o'tish
class RegisterSchema(BaseModel):
    username: str
    password: str
    phone: str

@app.post("/api/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data.username.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Username band!")
    
    new_user = User(
        username=data.username.strip().lower(),
        password_hash=pwd_context.hash(data.password),
        phone=data.phone.strip()
    )
    db.add(new_user)
    db.commit()
    return {"status": "ok"}

# 5. WebSocket (Chat)
class ConnectionManager:
    def __init__(self): self.active_connections: Dict[int, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections: self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        
    def disconnect(self, websocket: WebSocket, room_id: int):
        self.active_connections[room_id].remove(websocket)
        
    async def broadcast(self, message: str, room_id: int):
        for connection in self.active_connections.get(room_id, []):
            await connection.send_text(message)

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
            data = await websocket.receive_text()
            await manager.broadcast(f"{user.username}: {data}", room_id)
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
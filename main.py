import os
from passlib.context import CryptContext

# Mana shu qator yetishmayapti:
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
from sqlalchemy import create_engine
import logging
import uuid
from datetime import datetime
from typing import List, Dict
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Form, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, DateTime, Text, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from fastapi import FastAPI, HTTPException
# ... boshqa importlar

# 1. Baza sozlamalari
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")

# 2. Baza Engine va Base ni aniqlash (XATOLIK SHU YERDA EDI)
if DATABASE_URL.startswith("postgres"):
    DATABASE_URL = os.environ.get("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base() # BAZA KLASLARI UCHUN ASOS

# 3. Model klasslari (Endi Base aniq bo'lgani uchun xato bermaydi)
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    is_online = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    is_group = Column(Boolean, default=False)

class RoomMember(Base):
    __tablename__ = "room_members"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    is_owner = Column(Boolean, default=False)

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    sender_id = Column(Integer, ForeignKey("users.id"))
    text = Column(Text, nullable=True)
    file_url = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    reply_to_id = Column(String, nullable=True)
    reply_to_text = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

# 4. Bazani yaratish
Base.metadata.create_all(bind=engine)

# Qolgan kodlar (app = FastAPI(), API endpointlar va h.k.) shu pastdan davom etadi...
app = FastAPI()

for folder in ["uploads", "uploads/images", "uploads/voice"]:
    if not os.path.exists(folder): os.makedirs(folder)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class RegisterSchema(BaseModel):
    username: str; password: str; phone: str

class LoginSchema(BaseModel):
    phone_or_user: str; password: str

def get_current_user(token: str, db: Session):
    user = db.query(User).filter(User.username == token).first()
    if not user: raise HTTPException(401, "Sessiya yaroqsiz")
    return user

@app.get("/")
def index_page():
    with open("templates/chat.html", "r", encoding="utf-8") as f: return HTMLResponse(content=f.read())

# Ilk foydalanuvchini admin qilish (sinov uchun)
@app.post("/api/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    username = data.username.strip().lower()
    phone = data.phone.strip()
    if db.query(User).filter(User.username == username).first(): raise HTTPException(400, "Username band!")
    if db.query(User).filter(User.phone == phone).first(): raise HTTPException(400, "Telefon band!")
    
    # Agar bazada hech kim bo'lmasa, birinchi odam admin bo'ladi
    is_first = db.query(User).count() == 0
    db.add(User(username=username, password_hash=pwd_context.hash(data.password), phone=phone, is_admin=is_first))
    db.commit()
    return {"status": "ok"}

@app.post("/api/login")
def login(data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(or_(User.username == data.phone_or_user.strip().lower(), User.phone == data.phone_or_user.strip())).first()
    if not user or not pwd_context.verify(data.password, user.password_hash): raise HTTPException(400, "Xato!")
    user.is_online = True
    db.commit()
    return {"token": user.username, "username": user.username, "is_admin": user.is_admin}

@app.get("/api/rooms")
def get_rooms(token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    memberships = db.query(RoomMember).filter(RoomMember.user_id == current_user.id).all()
    room_ids = [m.room_id for m in memberships]
    rooms = db.query(Room).filter(Room.id.in_(room_ids)).all()
    
    result = []
    for r in rooms:
        name = r.name
        if not r.is_group:
            other_member = db.query(RoomMember).filter(RoomMember.room_id == r.id, RoomMember.user_id != current_user.id).first()
            if other_member:
                other_user = db.query(User).filter(User.id == other_member.user_id).first()
                name = other_user.username if other_user else "Foydalanuvchi"
        result.append({"id": r.id, "name": name, "is_group": r.is_group})
    return result

@app.get("/api/rooms/{room_id}/check")
def check_membership(room_id: int, token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    room = db.query(Room).filter(Room.id == room_id).first()
    if not room: raise HTTPException(404, "Xona topilmadi")
    is_mem = db.query(RoomMember).filter(RoomMember.room_id == room_id, RoomMember.user_id == current_user.id).first()
    return {"is_member": is_mem is not None, "is_group": room.is_group}

@app.post("/api/rooms/{room_id}/join")
def join_group(room_id: int, token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    room = db.query(Room).filter(Room.id == room_id, Room.is_group == True).first()
    if not room: raise HTTPException(404, "Guruh topilmadi")
    is_mem = db.query(RoomMember).filter(RoomMember.room_id == room_id, RoomMember.user_id == current_user.id).first()
    if not is_mem:
        db.add(RoomMember(room_id=room_id, user_id=current_user.id))
        db.commit()
    return {"status": "ok"}

@app.post("/api/rooms/{room_id}/add-member")
def add_member_by_username(room_id: int, target_username: str = Form(...), token: str = None, db: Session = Depends(get_db)):
    get_current_user(token, db) # Tekshirish
    target_user = db.query(User).filter(User.username == target_username.strip().lower()).first()
    if not target_user: raise HTTPException(404, "Foydalanuvchi topilmadi")
    
    is_mem = db.query(RoomMember).filter(RoomMember.room_id == room_id, RoomMember.user_id == target_user.id).first()
    if is_mem: raise HTTPException(400, "U allaqachon guruhda bor")
    
    db.add(RoomMember(room_id=room_id, user_id=target_user.id))
    db.commit()
    return {"status": "ok"}

@app.post("/api/rooms/create-group")
def create_group(name: str = Form(...), token: str = None, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    new_room = Room(name=name, is_group=True)
    db.add(new_room)
    db.commit()
    db.add(RoomMember(room_id=new_room.id, user_id=current_user.id, is_owner=True))
    db.commit()
    return {"status": "ok", "room_id": new_room.id}

@app.post("/api/rooms/open-direct/{user_id}")
def open_direct(user_id: int, token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    new_room = Room(name=None, is_group=False)
    db.add(new_room)
    db.commit()
    db.add(RoomMember(room_id=new_room.id, user_id=current_user.id))
    db.add(RoomMember(room_id=new_room.id, user_id=user_id))
    db.commit()
    return {"room_id": new_room.id}

@app.get("/api/search")
def global_search(q: str, token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    users = db.query(User).filter(User.username.contains(q), User.id != current_user.id).all()
    rooms = db.query(Room).filter(Room.name.contains(q), Room.is_group == True).all()
    return {
        "users": [{"id": u.id, "username": u.username, "phone": u.phone} for u in users],
        "rooms": [{"id": r.id, "name": r.name} for r in rooms]
    }

@app.get("/api/admin/users")
def admin_get_users(token: str, db: Session = Depends(get_db)):
    current_user = get_current_user(token, db)
    if not current_user.is_admin: raise HTTPException(403, "Ruxsat yo'q!")
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "phone": u.phone, "is_online": u.is_online, "is_admin": u.is_admin} for u in users]

@app.post("/api/upload-file")
async def upload_file(token: str, file: UploadFile = File(...)):
    ext = file.filename.split(".")[-1].lower()
    file_id = uuid.uuid4().hex
    folder = "uploads/images" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "uploads/voice"
    file_type = "image" if ext in ["jpg", "jpeg", "png", "gif", "webp"] else "voice"
    filepath = os.path.join(folder, f"{file_id}.{ext}")
    with open(filepath, "wb") as f: f.write(await file.read())
    return {"file_url": f"/{filepath}", "file_type": file_type}

@app.get("/api/rooms/{room_id}/members")
def get_room_members(room_id: int, token: str, db: Session = Depends(get_db)):
    members = db.query(RoomMember).filter(RoomMember.room_id == room_id).all()
    res = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u: res.append({"id": u.id, "username": u.username, "is_online": u.is_online, "is_owner": m.is_owner})
    return res

@app.get("/api/profile")
def get_profile(token: str, db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    return {"username": user.username, "phone": user.phone, "is_admin": user.is_admin}

# ---- WEBSOCKET MANAGER ----
class ConnectionManager:
    def __init__(self): self.active_connections: Dict[int, List[WebSocket]] = {}
    async def connect(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.active_connections: self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
    def disconnect(self, websocket: WebSocket, room_id: int):
        if room_id in self.active_connections and websocket in self.active_connections[room_id]:
            self.active_connections[room_id].remove(websocket)
    async def broadcast(self, message: dict, room_id: int):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]: await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{room_id}/{token}")
async def websocket_endpoint(websocket: WebSocket, room_id: int, token: str, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == token).first()
        if not user: return
        user.is_online = True; db.commit()
        await manager.connect(websocket, room_id)
        
        while True:
            data = await websocket.receive_json()
            time_str = datetime.now().strftime("%H:%M")
            msg_id = uuid.uuid4().hex[:8]
            
            if data.get("type") == "chat":
                payload = {
                    "type": "chat", "sender": user.username, "message": data.get("message", ""),
                    "file_url": data.get("file_url", None), "file_type": data.get("file_type", None),
                    "reply_to_user": data.get("reply_to_user", None),
                    "reply_to_text": data.get("reply_to_text", None),
                    "time": time_str, "msg_id": msg_id
                }
                await manager.broadcast(payload, room_id)
            elif data.get("type") == "reaction":
                await manager.broadcast({"type": "reaction_update", "msg_id": data.get("msg_id"), "emoji": data.get("emoji")}, room_id)
            elif data.get("type") == "typing":
                await manager.broadcast({"type": "typing", "sender": user.username}, room_id)
    except WebSocketDisconnect:
        user.is_online = False; db.commit()
        manager.disconnect(websocket, room_id)
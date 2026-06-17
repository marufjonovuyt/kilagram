from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table, Boolean
from sqlalchemy.orm import relationship
import datetime
from database import Base

# Guruh a'zolari va ularning huquqlari
class RoomMember(Base):
    __tablename__ = "room_members"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True)
    is_owner = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    user = relationship("User", back_populates="room_memberships")
    room = relationship("Room", back_populates="member_roles")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    phone = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    avatar_url = Column(String, default="https://cdn-icons-png.flaticon.com/512/149/149071.png")
    is_online = Column(Boolean, default=False)

    room_memberships = relationship("RoomMember", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="sender")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    device_info = Column(String)
    ip_address = Column(String)
    last_active = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="sessions")

class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True) # Guruh nomi (Lichkada bo'sh bo'ladi)
    is_direct = Column(Boolean, default=False) # True bo'lsa - Lichka, False bo'lsa - Guruh
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    member_roles = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="room", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"))
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    text = Column(String, nullable=True)
    file_url = Column(String, nullable=True) 
    file_type = Column(String, nullable=True) # "image" yoki "voice"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    room = relationship("Room", back_populates="messages")
    sender = relationship("User", back_populates="messages")
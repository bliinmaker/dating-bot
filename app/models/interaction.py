from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True)
    from_profile_id = Column(Integer, ForeignKey("profiles.id"))
    to_profile_id = Column(Integer, ForeignKey("profiles.id"))
    type = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)

    from_profile = relationship("Profile", foreign_keys=[from_profile_id], back_populates="sent_interactions")
    to_profile = relationship("Profile", foreign_keys=[to_profile_id], back_populates="received_interactions")

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    profile_id_1 = Column(Integer, ForeignKey("profiles.id"))
    profile_id_2 = Column(Integer, ForeignKey("profiles.id"))
    status = Column(String(20), default="active")
    initiated_chat = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile_1 = relationship("Profile", foreign_keys=[profile_id_1])
    profile_2 = relationship("Profile", foreign_keys=[profile_id_2])
    messages = relationship("Message", back_populates="match")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    sender_id = Column(Integer, ForeignKey("profiles.id"))
    content = Column(Text)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="messages")
    sender = relationship("Profile", foreign_keys=[sender_id])
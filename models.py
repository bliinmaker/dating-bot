from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import config

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False)

class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    name = Column(String(100))
    age = Column(Integer)
    gender = Column(String(20))
    bio = Column(Text)
    location = Column(String(100))
    interests = Column(JSON)
    preferred_age_min = Column(Integer)
    preferred_age_max = Column(Integer)
    preferred_gender = Column(String(20))
    preferred_location = Column(String(100))
    profile_completeness = Column(Float, default=0.0)
    photo_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")
    photos = relationship("Photo", back_populates="profile")
    rating = relationship("Rating", back_populates="profile", uselist=False)
    sent_interactions = relationship("Interaction", foreign_keys="Interaction.from_profile_id", back_populates="from_profile")
    received_interactions = relationship("Interaction", foreign_keys="Interaction.to_profile_id", back_populates="to_profile")

class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"))
    s3_path = Column(String(255), nullable=False)
    telegram_file_id = Column(String(255))
    is_main = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="photos")

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), unique=True)
    primary_rating = Column(Float, default=0.0)
    behavioral_rating = Column(Float, default=0.0)
    combined_rating = Column(Float, default=0.0)
    last_calculated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile = relationship("Profile", back_populates="rating")

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

engine = create_engine(config.DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
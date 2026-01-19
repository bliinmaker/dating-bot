from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

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
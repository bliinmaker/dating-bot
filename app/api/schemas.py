from pydantic import BaseModel, Field
from typing import Optional, List

class UserCreate(BaseModel):
    telegram_id: int = Field(..., description="Telegram ID пользователя")
    username: Optional[str] = Field(None, description="Telegram username")

class UserResponse(BaseModel):
    id: int
    telegram_id: int
    username: Optional[str]
    created_at: str
    last_active: Optional[str]

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Имя пользователя")
    age: int = Field(..., ge=18, le=100, description="Возраст пользователя")
    gender: str = Field(..., description="Пол: Мужской/Женский")
    bio: Optional[str] = Field(None, max_length=500, description="О себе")
    location: str = Field(..., description="Город")
    interests: Optional[str] = Field(None, description="Интересы")
    preferred_age_min: int = Field(..., ge=18, le=100, description="Минимальный возраст партнера")
    preferred_age_max: int = Field(..., ge=18, le=100, description="Максимальный возраст партнера")
    preferred_gender: str = Field(..., description="Предпочитаемый пол партнера")
    preferred_location: Optional[str] = Field(None, description="Предпочитаемый город партнера")

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    age: int
    gender: str
    bio: Optional[str]
    location: str
    interests: Optional[str]
    preferred_age_min: int
    preferred_age_max: int
    preferred_gender: str
    preferred_location: Optional[str]
    profile_completeness: float
    photo_count: int
    created_at: str
    updated_at: str

class InteractionCreate(BaseModel):
    to_profile_id: int = Field(..., description="ID профиля, с которым взаимодействуют")
    type: str = Field(..., description="Тип взаимодействия: like/pass")

class InteractionResponse(BaseModel):
    id: int
    from_profile_id: int
    to_profile_id: int
    type: str
    created_at: str

class MatchResponse(BaseModel):
    id: int
    profile_id_1: int
    profile_id_2: int
    status: str
    initiated_chat: bool
    created_at: str

class RatingResponse(BaseModel):
    profile_id: int
    primary_rating: float
    behavioral_rating: float
    combined_rating: float
    last_calculated: str
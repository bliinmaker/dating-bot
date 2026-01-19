from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from sqlalchemy.orm import Session
from app.models import *
from app.api.schemas import *
from app.services.user_service import UserService
from app.services.profile_service import ProfileService
from app.core.config import *
import logging

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dating Bot API",
    description="API для телеграм-бота знакомств с микросервисной архитектурой",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    from app.models.database import Session as DB_Session
    session = DB_Session()
    try:
        yield session
    finally:
        session.close()

@app.get("/", tags=["Health"])
async def root():
    return {"message": "Dating Bot API работает", "version": "1.0.0"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "dating-bot-api"}

@app.post("/users", response_model=UserResponse, tags=["Users"])
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        user = UserService.get_or_create_user(
            session=db, 
            telegram_id=user_data.telegram_id,
            telegram_username=user_data.username
        )
        
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            created_at=user.created_at.isoformat(),
            last_active=user.last_active.isoformat() if user.last_active else None
        )
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания пользователя: {str(e)}")

@app.get("/users/{telegram_id}", response_model=UserResponse, tags=["Users"])
async def get_user(telegram_id: int, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return UserResponse(
            id=user.id,
            telegram_id=user.telegram_id,
            username=user.username,
            created_at=user.created_at.isoformat(),
            last_active=user.last_active.isoformat() if user.last_active else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения пользователя: {str(e)}")

@app.post("/users/{telegram_id}/profile", response_model=ProfileResponse, tags=["Profiles"])
async def create_profile(telegram_id: int, profile_data: ProfileCreate, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        profile_service = ProfileService()
        profile = profile_service.create_profile(
            session=db,
            user_id=user.id,
            profile_data=profile_data.dict()
        )
        
        if not profile:
            raise HTTPException(status_code=400, detail="Ошибка создания профиля")
        
        return ProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            name=profile.name,
            age=profile.age,
            gender=profile.gender,
            bio=profile.bio,
            location=profile.location,
            interests=profile.interests,
            preferred_age_min=profile.preferred_age_min,
            preferred_age_max=profile.preferred_age_max,
            preferred_gender=profile.preferred_gender,
            preferred_location=profile.preferred_location,
            profile_completeness=profile.profile_completeness,
            photo_count=profile.photo_count,
            created_at=profile.created_at.isoformat(),
            updated_at=profile.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating profile: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания профиля: {str(e)}")

@app.get("/users/{telegram_id}/profile", tags=["Profiles"])
async def get_user_profile(telegram_id: int, db: Session = Depends(get_db)):
    try:
        profile_data = UserService.get_user_profile(session=db, telegram_id=telegram_id)
        
        if not profile_data:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        if not profile_data.get("has_profile"):
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        return profile_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения профиля: {str(e)}")

@app.post("/profiles/{profile_id}/interactions", response_model=InteractionResponse, tags=["Matching"])
async def create_interaction(profile_id: int, interaction_data: InteractionCreate, db: Session = Depends(get_db)):
    try:
        profile = db.query(Profile).filter_by(id=profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        interaction = Interaction(
            from_profile_id=profile_id,
            to_profile_id=interaction_data.to_profile_id,
            type=interaction_data.type
        )
        
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        return InteractionResponse(
            id=interaction.id,
            from_profile_id=interaction.from_profile_id,
            to_profile_id=interaction.to_profile_id,
            type=interaction.type,
            created_at=interaction.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating interaction: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания взаимодействия: {str(e)}")

@app.get("/profiles/{profile_id}/matches", response_model=List[MatchResponse], tags=["Matching"])
async def get_profile_matches(profile_id: int, db: Session = Depends(get_db)):
    try:
        profile = db.query(Profile).filter_by(id=profile_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Профиль не найден")
        
        matches = db.query(Match).filter(
            (Match.profile_id_1 == profile_id) | 
            (Match.profile_id_2 == profile_id)
        ).all()
        
        return [
            MatchResponse(
                id=match.id,
                profile_id_1=match.profile_id_1,
                profile_id_2=match.profile_id_2,
                status=match.status,
                initiated_chat=match.initiated_chat,
                created_at=match.created_at.isoformat()
            )
            for match in matches
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting matches: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения совпадений: {str(e)}")

@app.get("/profiles/{profile_id}/rating", response_model=RatingResponse, tags=["Rating"])
async def get_profile_rating(profile_id: int, db: Session = Depends(get_db)):
    try:
        rating = db.query(Rating).filter_by(profile_id=profile_id).first()
        if not rating:
            raise HTTPException(status_code=404, detail="Рейтинг не найден")
        
        return RatingResponse(
            profile_id=rating.profile_id,
            primary_rating=rating.primary_rating,
            behavioral_rating=rating.behavioral_rating,
            combined_rating=rating.combined_rating,
            last_calculated=rating.last_calculated.isoformat()
        )
    except Exception as e:
        logger.error(f"Error getting rating: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения рейтинга: {str(e)}")

@app.get("/stats", tags=["Statistics"])
async def get_system_stats(db: Session = Depends(get_db)):
    try:
        return {
            "total_users": db.query(User).count(),
            "total_profiles": db.query(Profile).count(),
            "total_interactions": db.query(Interaction).count(),
            "total_matches": db.query(Match).count(),
            "profiles_with_photos": db.query(Profile).filter(Profile.photo_count > 0).count()
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API сервер корректно завершает работу...")

if __name__ == "__main__":
    import uvicorn
    import signal
    import sys
    
    def signal_handler(signum, frame):
        logger.info(f"Получен сигнал {signum}, завершаю API сервер...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("API сервер запущен с поддержкой graceful shutdown")
    uvicorn.run(app, host="0.0.0.0", port=8000)
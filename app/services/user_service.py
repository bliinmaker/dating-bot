from sqlalchemy.orm import Session
from app.models import *
from typing import Optional, Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def get_or_create_user(session: Session, telegram_id: int, telegram_username: Optional[str] = None) -> User:
        """Get a user by Telegram ID or create if not exists"""
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()

            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=telegram_username
                )
                session.add(user)
                session.commit()
                logger.info(f"Created new user with Telegram ID {telegram_id}")
            else:
                if telegram_username:
                    user.username = telegram_username
                user.last_active = datetime.utcnow()
                session.commit()
                logger.debug(f"User with Telegram ID {telegram_id} found")

            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Error getting/creating user with Telegram ID {telegram_id}: {e}")
            raise

    @staticmethod
    def get_user_profile(session: Session, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's profile data"""
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                logger.error(f"User with Telegram ID {telegram_id} not found")
                return None

            profile = session.query(Profile).filter_by(user_id=user.id).first()
            if not profile:
                logger.debug(f"Profile not found for user with Telegram ID {telegram_id}")
                return {"has_profile": False, "user_id": user.id}

            photos = session.query(Photo).filter_by(profile_id=profile.id).all()
            photo_data = []

            for photo in photos:
                photo_data.append({
                    "id": photo.id,
                    "is_main": photo.is_main,
                    "created_at": photo.created_at.isoformat()
                })

            return {
                "has_profile": True,
                "user_id": user.id,
                "profile_id": profile.id,
                "name": profile.name,
                "age": profile.age,
                "gender": profile.gender,
                "bio": profile.bio,
                "location": profile.location,
                "interests": profile.interests,
                "preferred_age_min": profile.preferred_age_min,
                "preferred_age_max": profile.preferred_age_max,
                "preferred_gender": profile.preferred_gender,
                "preferred_location": profile.preferred_location,
                "profile_completeness": profile.profile_completeness,
                "photo_count": profile.photo_count,
                "photos": photo_data,
                "created_at": profile.created_at.isoformat(),
                "updated_at": profile.updated_at.isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting profile for user with Telegram ID {telegram_id}: {e}")
            return None
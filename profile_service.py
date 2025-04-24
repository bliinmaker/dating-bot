from sqlalchemy.orm import Session
import models
from s3_client import S3Client
from redis_client import RedisClient
from rating_service import RatingService
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ProfileService:
    def __init__(self):
        self.s3_client = S3Client()
        self.redis_client = RedisClient()
        logger.info("Profile service initialized")

    def create_profile(self, session: Session, user_id: int, profile_data: Dict[str, Any]) -> Optional[models.Profile]:
        """Create a new profile for a user"""
        try:
            gender = profile_data.get("gender", "")
            if gender == "Мужской":
                preferred_gender = "Женский"
            elif gender == "Женский":
                preferred_gender = "Мужской"
            else:
                preferred_gender = None

            profile = models.Profile(
                user_id=user_id,
                name=profile_data.get("name", ""),
                age=profile_data.get("age"),
                gender=profile_data.get("gender", ""),
                bio=profile_data.get("bio", ""),
                location=profile_data.get("location", ""),
                interests=profile_data.get("interests", {}),
                preferred_age_min=profile_data.get("preferred_age_min"),
                preferred_age_max=profile_data.get("preferred_age_max"),
                preferred_gender=preferred_gender,
                preferred_location=profile_data.get("preferred_location", ""),
                profile_completeness=self._calculate_profile_completeness(profile_data)
            )
            session.add(profile)
            session.commit()

            rating = models.Rating(profile_id=profile.id)
            session.add(rating)
            session.commit()

            RatingService.update_profile_rating(session, profile.id)

            logger.info(f"Created profile for user {user_id}")
            return profile
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating profile for user {user_id}: {e}")
            return None

    def update_profile(self, session: Session, profile_id: int, profile_data: Dict[str, Any]) -> Optional[
        models.Profile]:
        """Update an existing profile"""
        try:
            profile = session.query(models.Profile).filter_by(id=profile_id).first()
            if not profile:
                logger.error(f"Profile {profile_id} not found for update")
                return None

            if "name" in profile_data:
                profile.name = profile_data["name"]
            if "age" in profile_data:
                profile.age = profile_data["age"]
            if "gender" in profile_data:
                profile.gender = profile_data["gender"]
            if "bio" in profile_data:
                profile.bio = profile_data["bio"]
            if "location" in profile_data:
                profile.location = profile_data["location"]
            if "interests" in profile_data:
                profile.interests = profile_data["interests"]
            if "preferred_age_min" in profile_data:
                profile.preferred_age_min = profile_data["preferred_age_min"]
            if "preferred_age_max" in profile_data:
                profile.preferred_age_max = profile_data["preferred_age_max"]
            if "preferred_gender" in profile_data:
                profile.preferred_gender = profile_data["preferred_gender"]
            if "preferred_location" in profile_data:
                profile.preferred_location = profile_data["preferred_location"]

            profile.profile_completeness = self._calculate_profile_completeness({
                "name": profile.name,
                "age": profile.age,
                "gender": profile.gender,
                "bio": profile.bio,
                "location": profile.location,
                "interests": profile.interests,
                "preferred_age_min": profile.preferred_age_min,
                "preferred_age_max": profile.preferred_age_max,
                "preferred_gender": profile.preferred_gender,
                "preferred_location": profile.preferred_location
            })

            profile.updated_at = datetime.utcnow()
            session.commit()

            RatingService.update_profile_rating(session, profile.id)

            self.redis_client.delete_profile_list(profile.user_id)

            logger.info(f"Updated profile {profile_id}")
            return profile
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating profile {profile_id}: {e}")
            return None
    def add_photo(self, session: Session, profile_id: int, photo_data: bytes, telegram_file_id: str = None,
                  is_main: bool = False) -> Optional[str]:
        """Add a photo to a profile"""
        try:
            s3_path = self.s3_client.upload_photo(photo_data)
            if not s3_path:
                return None

            profile = session.query(models.Profile).filter_by(id=profile_id).first()
            if not profile:
                logger.error(f"Profile {profile_id} not found when adding photo")
                return None

            if is_main:
                session.query(models.Photo).filter_by(profile_id=profile_id, is_main=True).update(
                    {"is_main": False})

            photo = models.Photo(
                profile_id=profile_id,
                s3_path=s3_path,
                telegram_file_id=telegram_file_id,
                is_main=is_main
            )
            session.add(photo)

            profile.photo_count += 1

            session.commit()

            RatingService.update_profile_rating(session, profile_id)

            self.redis_client.delete_profile_list(profile.user_id)

            logger.info(f"Added photo for profile {profile_id}")
            return s3_path
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding photo for profile {profile_id}: {e}")
            return None

    def get_photos(self, session: Session, profile_id: int) -> List[Dict[str, Any]]:
        """Get all photos for a profile with their telegram file IDs (if available)"""
        try:
            photos = session.query(models.Photo).filter_by(profile_id=profile_id).all()
            result = []

            for photo in photos:
                photo_data = {
                    "id": photo.id,
                    "is_main": photo.is_main,
                    "created_at": photo.created_at.isoformat()
                }

                if photo.telegram_file_id:
                    photo_data["telegram_file_id"] = photo.telegram_file_id
                    photo_data["url"] = photo.telegram_file_id
                else:
                    url = self.s3_client.get_photo_url(photo.s3_path)
                    if url:
                        photo_data["url"] = url

                result.append(photo_data)

            logger.debug(f"Retrieved {len(result)} photos for profile {profile_id}")
            return result
        except Exception as e:
            logger.error(f"Error getting photos for profile {profile_id}: {e}")
            return []

    def get_profile(self, session: Session, profile_id: int) -> Optional[Dict[str, Any]]:
        """Get a profile with its photos and rating"""
        try:
            cached_profile = self.redis_client.get_cached_profile(profile_id)
            if cached_profile:
                return cached_profile

            profile = session.query(models.Profile).filter_by(id=profile_id).first()
            if not profile:
                logger.error(f"Profile {profile_id} not found")
                return None

            photos = self.get_photos(session, profile_id)

            rating = session.query(models.Rating).filter_by(profile_id=profile_id).first()

            result = {
                "id": profile.id,
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
                "photos": photos,
                "rating": {
                    "primary": rating.primary_rating if rating else 0.0,
                    "behavioral": rating.behavioral_rating if rating else 0.0,
                    "combined": rating.combined_rating if rating else 0.0
                } if rating else {"primary": 0.0, "behavioral": 0.0, "combined": 0.0},
                "created_at": profile.created_at.isoformat(),
                "updated_at": profile.updated_at.isoformat()
            }

            self.redis_client.cache_profile(profile_id, result)

            logger.debug(f"Retrieved profile {profile_id}")
            return result
        except Exception as e:
            logger.error(f"Error getting profile {profile_id}: {e}")
            return None

    def _calculate_profile_completeness(self, profile_data: Dict[str, Any]) -> float:
        """Calculate profile completeness percentage"""
        required_fields = ["name", "age", "gender", "bio", "location", "interests",
                           "preferred_age_min", "preferred_age_max", "preferred_gender"]

        filled = sum(1 for field in required_fields if profile_data.get(field))

        return filled / len(required_fields)
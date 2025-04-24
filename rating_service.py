from sqlalchemy.orm import Session
from sqlalchemy import func, desc
import models
from typing import List, Dict, Any
import config
import logging
from celery_app import celery_app

logger = logging.getLogger(__name__)


class RatingService:
    @staticmethod
    def calculate_primary_rating(session: Session, profile_id: int) -> float:
        """
        Calculate primary rating based on profile completeness and photo count
        Level 1:
        1) Формируется на основе данных из анкеты пользователя (возраст, пол, интересы, географическое положение)
        2) Учитывает полноту заполнения анкеты и количество загруженных фотографий
        3) Включает первичные предпочтения пользователя (возрастной диапазон, пол, город)
        """
        try:
            profile = session.query(models.Profile).filter_by(id=profile_id).first()
            if not profile:
                logger.error(f"Profile {profile_id} not found when calculating primary rating")
                return 0.0

            completeness_score = profile.profile_completeness * 0.4

            photo_score = min(profile.photo_count / 3, 1.0) * 0.3

            preferences_score = 0.0
            if profile.preferred_age_min and profile.preferred_age_max and profile.preferred_gender:
                preferences_score = 0.3

            primary_rating = (completeness_score + photo_score + preferences_score) * 100

            logger.debug(f"Calculated primary rating for profile {profile_id}: {primary_rating}")
            return primary_rating
        except Exception as e:
            logger.error(f"Error calculating primary rating for profile {profile_id}: {e}")
            return 0.0

    @staticmethod
    def calculate_behavioral_rating(session: Session, profile_id: int) -> float:
        """
        Calculate behavioral rating based on interactions
        Level 2:
        1) Динамически корректируется на основе взаимодействия других пользователей с анкетой:
           a) Количество лайков анкеты
           b) Соотношение лайков и пропусков
           c) Частота взаимных лайков (мэтчей)
           d) Частота инициирования диалогов после мэтча
        2) Включает временные параметры (активность в определенное время суток)
        """
        try:
            total_views = session.query(func.count(models.Interaction.id)).filter(
                models.Interaction.to_profile_id == profile_id
            ).scalar() or 0

            likes_received = session.query(func.count(models.Interaction.id)).filter(
                models.Interaction.to_profile_id == profile_id,
                models.Interaction.type == "like"
            ).scalar() or 0

            likes_score = min(likes_received / 100, 1.0) * 0.3

            ratio_score = 0.0
            if total_views > 0:
                ratio = likes_received / total_views
                ratio_score = ratio * 0.3

            matches_count = session.query(func.count(models.Match.id)).filter(
                ((models.Match.profile_id_1 == profile_id) | (models.Match.profile_id_2 == profile_id))
            ).scalar() or 0

            match_score = 0.0
            if likes_received > 0:
                match_ratio = min(matches_count / likes_received, 0.5) / 0.5
                match_score = match_ratio * 0.2

            initiated_chats = session.query(func.count(models.Match.id)).filter(
                ((models.Match.profile_id_1 == profile_id) | (models.Match.profile_id_2 == profile_id)),
                models.Match.initiated_chat == True
            ).scalar() or 0

            chat_score = 0.0
            if matches_count > 0:
                chat_ratio = initiated_chats / matches_count
                chat_score = chat_ratio * 0.2

            behavioral_rating = (likes_score + ratio_score + match_score + chat_score) * 100

            logger.debug(f"Calculated behavioral rating for profile {profile_id}: {behavioral_rating}")
            return behavioral_rating
        except Exception as e:
            logger.error(f"Error calculating behavioral rating for profile {profile_id}: {e}")
            return 0.0

    @staticmethod
    def calculate_combined_rating(primary_rating: float, behavioral_rating: float) -> float:
        """
        Calculate combined rating using weighted formula
        Level 3:
        1) Интегрирует первичный и поведенческий рейтинги по весовой модели
        """
        combined_rating = (primary_rating * config.PRIMARY_RATING_WEIGHT +
                           behavioral_rating * config.BEHAVIORAL_RATING_WEIGHT)
        return combined_rating

    @staticmethod
    def update_profile_rating(session: Session, profile_id: int) -> Dict[str, float]:
        """Update a profile's rating in the database"""
        try:
            primary_rating = RatingService.calculate_primary_rating(session, profile_id)
            behavioral_rating = RatingService.calculate_behavioral_rating(session, profile_id)
            combined_rating = RatingService.calculate_combined_rating(primary_rating, behavioral_rating)

            rating = session.query(models.Rating).filter_by(profile_id=profile_id).first()
            if not rating:
                rating = models.Rating(
                    profile_id=profile_id,
                    primary_rating=primary_rating,
                    behavioral_rating=behavioral_rating,
                    combined_rating=combined_rating
                )
                session.add(rating)
            else:
                rating.primary_rating = primary_rating
                rating.behavioral_rating = behavioral_rating
                rating.combined_rating = combined_rating

            session.commit()
            logger.info(f"Updated rating for profile {profile_id}: {combined_rating}")

            return {
                "primary_rating": primary_rating,
                "behavioral_rating": behavioral_rating,
                "combined_rating": combined_rating
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating rating for profile {profile_id}: {e}")
            return {
                "primary_rating": 0.0,
                "behavioral_rating": 0.0,
                "combined_rating": 0.0
            }

    @staticmethod
    def get_ranked_profiles(session: Session, user_profile_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get ranked profiles for a user based on preferences and ratings"""
        try:
            user_profile = session.query(models.Profile).filter_by(id=user_profile_id).first()
            if not user_profile:
                logger.error(f"Profile {user_profile_id} not found when getting ranked profiles")
                return []

            interacted_profiles = session.query(models.Interaction.to_profile_id).filter_by(
                from_profile_id=user_profile_id
            ).all()
            interacted_profile_ids = [p[0] for p in interacted_profiles]

            matching_profiles = session.query(
                models.Profile, models.Rating
            ).join(
                models.Rating, models.Profile.id == models.Rating.profile_id
            ).filter(
                models.Profile.gender == user_profile.preferred_gender if user_profile.preferred_gender else True,
                models.Profile.age >= user_profile.preferred_age_min if user_profile.preferred_age_min else True,
                models.Profile.age <= user_profile.preferred_age_max if user_profile.preferred_age_max else True,
                models.Profile.location == user_profile.preferred_location if user_profile.preferred_location else True,
                models.Profile.id != user_profile_id,
                ~models.Profile.id.in_(interacted_profile_ids) if interacted_profile_ids else True
            ).order_by(
                desc(models.Rating.combined_rating)
            ).limit(limit).all()

            result = []
            for profile, rating in matching_profiles:
                profile_dict = {
                    "id": profile.id,
                    "name": profile.name,
                    "age": profile.age,
                    "gender": profile.gender,
                    "bio": profile.bio,
                    "location": profile.location,
                    "interests": profile.interests,
                    "photo_count": profile.photo_count,
                    "rating": {
                        "primary": rating.primary_rating,
                        "behavioral": rating.behavioral_rating,
                        "combined": rating.combined_rating
                    }
                }
                result.append(profile_dict)

            logger.debug(f"Found {len(result)} ranked profiles for user {user_profile_id}")
            return result
        except Exception as e:
            logger.error(f"Error getting ranked profiles for user {user_profile_id}: {e}")
            return []


@celery_app.task
def update_all_ratings():
    """Periodic task to update all profile ratings"""
    logger.info("Starting batch update of all profile ratings")
    session = models.Session()
    try:
        profiles = session.query(models.Profile).all()
        updated_count = 0

        for profile in profiles:
            try:
                RatingService.update_profile_rating(session, profile.id)
                updated_count += 1
            except Exception as e:
                logger.error(f"Error updating rating for profile {profile.id}: {e}")

        logger.info(f"Completed batch update of ratings for {updated_count}/{len(profiles)} profiles")
        return {"updated_count": updated_count, "total": len(profiles)}
    except Exception as e:
        logger.error(f"Error in batch rating update: {e}")
        return {"error": str(e)}
    finally:
        session.close()
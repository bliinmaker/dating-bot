from sqlalchemy.orm import Session
from app.models import *
from app.core.redis_client import RedisClient
from app.services.rating_service import RatingService
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
from celery_app import celery_app
from app.core import config

logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self):
        self.redis_client = RedisClient()
        logger.info("Matching service initialized")

    def like_profile(self, session: Session, from_profile_id: int, to_profile_id: int) -> Dict[str, Any]:
        """Record a like interaction and check for a match"""
        try:
            interaction = Interaction(
                from_profile_id=from_profile_id,
                to_profile_id=to_profile_id,
                type="like"
            )
            session.add(interaction)

            mutual_like = session.query(Interaction).filter_by(
                from_profile_id=to_profile_id,
                to_profile_id=from_profile_id,
                type="like"
            ).first()

            is_match = False
            match_id = None

            if mutual_like:
                match = Match(
                    profile_id_1=from_profile_id,
                    profile_id_2=to_profile_id,
                    status="active"
                )
                session.add(match)
                session.commit()

                is_match = True
                match_id = match.id

                RatingService.update_profile_rating(session, from_profile_id)
                RatingService.update_profile_rating(session, to_profile_id)

                from_user_id = session.query(Profile.user_id).filter_by(id=from_profile_id).scalar()
                to_user_id = session.query(Profile.user_id).filter_by(id=to_profile_id).scalar()

                if from_user_id:
                    self.redis_client.delete_profile_list(from_user_id)
                if to_user_id:
                    self.redis_client.delete_profile_list(to_user_id)

                logger.info(f"Created match between profiles {from_profile_id} and {to_profile_id}")
            else:
                session.commit()
                logger.debug(f"Profile {from_profile_id} liked profile {to_profile_id}")

            return {
                "success": True,
                "is_match": is_match,
                "match_id": match_id
            }
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing like from {from_profile_id} to {to_profile_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def skip_profile(self, session: Session, from_profile_id: int, to_profile_id: int) -> Dict[str, bool]:
        """Record a skip interaction"""
        try:
            interaction = Interaction(
                from_profile_id=from_profile_id,
                to_profile_id=to_profile_id,
                type="skip"
            )
            session.add(interaction)
            session.commit()

            logger.debug(f"Profile {from_profile_id} skipped profile {to_profile_id}")
            return {"success": True}
        except Exception as e:
            session.rollback()
            logger.error(f"Error processing skip from {from_profile_id} to {to_profile_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_matches(self, session: Session, profile_id: int) -> List[Dict[str, Any]]:
        """Get all matches for a profile"""
        try:
            matches = session.query(Match).filter(
                ((Match.profile_id_1 == profile_id) | (Match.profile_id_2 == profile_id)),
                Match.status == "active"
            ).all()

            result = []
            for match in matches:
                other_profile_id = match.profile_id_2 if match.profile_id_1 == profile_id else match.profile_id_1

                other_profile = session.query(Profile).filter_by(id=other_profile_id).first()
                if not other_profile:
                    continue

                last_message = session.query(Message).filter_by(match_id=match.id).order_by(
                    Message.created_at.desc()
                ).first()

                match_info = {
                    "match_id": match.id,
                    "created_at": match.created_at.isoformat(),
                    "other_profile": {
                        "id": other_profile.id,
                        "name": other_profile.name,
                        "age": other_profile.age
                    },
                    "initiated_chat": match.initiated_chat,
                    "last_message": {
                        "content": last_message.content,
                        "sender_id": last_message.sender_id,
                        "created_at": last_message.created_at.isoformat(),
                        "is_read": last_message.read
                    } if last_message else None
                }
                result.append(match_info)

            logger.debug(f"Found {len(result)} matches for profile {profile_id}")
            return result
        except Exception as e:
            logger.error(f"Error getting matches for profile {profile_id}: {e}")
            return []

    def get_next_profiles(self, session: Session, user_id: int, limit: int = config.PROFILES_PRELOAD_COUNT) -> List[
        Dict[str, Any]]:
        """Get the next batch of profiles for a user to view"""
        try:
            profile = session.query(Profile).join(User).filter(User.id == user_id).first()
            if not profile:
                logger.error(f"Profile not found for user {user_id}")
                return []

            interacted_profiles = session.query(Interaction.to_profile_id).filter_by(
                from_profile_id=profile.id
            ).all()
            interacted_profile_ids = [p[0] for p in interacted_profiles]

            profiles = RatingService.get_ranked_profiles(session, profile.id, limit)

            profiles = [p for p in profiles if p["id"] not in interacted_profile_ids]

            if profiles:
                self.redis_client.set_profile_list(user_id, profiles)

            logger.debug(f"Retrieved {len(profiles)} profiles for user {user_id}")
            return profiles
        except Exception as e:
            logger.error(f"Error getting next profiles for user {user_id}: {e}")
            return []


@celery_app.task
def preload_profiles(user_id: int):
    """Preload profiles for a user into Redis cache"""
    session = Session()
    try:
        matching_service = MatchingService()
        profiles = matching_service.get_next_profiles(session, user_id)
        logger.info(f"Preloaded {len(profiles)} profiles for user {user_id}")
        return {"success": True, "count": len(profiles)}
    except Exception as e:
        logger.error(f"Error preloading profiles for user {user_id}: {e}")
        return {"success": False, "error": str(e)}
    finally:
        session.close()
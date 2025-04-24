import redis
import pickle
import json
from typing import List, Dict, Any
import config
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        self.client = redis.Redis.from_url(config.REDIS_URL, decode_responses=False)
        logger.info(f"Redis client initialized with URL: {config.REDIS_URL}")

    def set_profile_list(self, user_id: int, profiles: List[Dict[str, Any]], ttl: int = config.REDIS_CACHE_TTL):
        """Cache a list of profiles for a user"""
        key = f"profiles:{user_id}"
        try:
            self.client.set(key, pickle.dumps(profiles), ex=ttl)
            logger.debug(f"Cached {len(profiles)} profiles for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error caching profiles for user {user_id}: {e}")
            return False

    def get_profile_list(self, user_id: int) -> List[Dict[str, Any]]:
        """Get cached profile list for a user"""
        key = f"profiles:{user_id}"
        try:
            data = self.client.get(key)
            if data:
                profiles = pickle.loads(data)
                logger.debug(f"Retrieved {len(profiles)} cached profiles for user {user_id}")
                return profiles
            return []
        except Exception as e:
            logger.error(f"Error retrieving cached profiles for user {user_id}: {e}")
            return []

    def delete_profile_list(self, user_id: int):
        """Delete cached profile list for a user"""
        key = f"profiles:{user_id}"
        try:
            self.client.delete(key)
            logger.debug(f"Deleted cached profiles for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cached profiles for user {user_id}: {e}")
            return False

    def cache_profile(self, profile_id: int, profile_data: Dict[str, Any], ttl: int = config.REDIS_CACHE_TTL):
        """Cache a single profile"""
        key = f"profile:{profile_id}"
        try:
            self.client.set(key, json.dumps(profile_data), ex=ttl)
            logger.debug(f"Cached profile {profile_id}")
            return True
        except Exception as e:
            logger.error(f"Error caching profile {profile_id}: {e}")
            return False

    def get_cached_profile(self, profile_id: int) -> Dict[str, Any]:
        """Get a cached profile"""
        key = f"profile:{profile_id}"
        try:
            data = self.client.get(key)
            if data:
                profile = json.loads(data)
                logger.debug(f"Retrieved cached profile {profile_id}")
                return profile
            return {}
        except Exception as e:
            logger.error(f"Error retrieving cached profile {profile_id}: {e}")
            return {}
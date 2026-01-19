import pytest
from app.services.user_service import UserService
from app.models import *


class TestUserService:

    def test_get_or_create_user_new_user(self, test_session, sample_user_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        assert user is not None
        assert user.telegram_id == sample_user_data["telegram_id"]
        assert user.username == sample_user_data["username"]
        assert user.id is not None
        
        db_user = test_session.query(User).filter_by(
            telegram_id=sample_user_data["telegram_id"]
        ).first()
        assert db_user is not None
        assert db_user.telegram_id == sample_user_data["telegram_id"]

    def test_get_or_create_user_existing_user(self, test_session, sample_user_data):
        user1 = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        user2 = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username="updated_username"
        )
        
        assert user1.id == user2.id
        assert user2.username == "updated_username"
        
        users_count = test_session.query(User).filter_by(
            telegram_id=sample_user_data["telegram_id"]
        ).count()
        assert users_count == 1

    def test_get_user_profile_no_user(self, test_session):
        result = UserService.get_user_profile(
            session=test_session,
            telegram_id=999999999
        )
        
        assert result is None

    def test_get_user_profile_no_profile(self, test_session, sample_user_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        result = UserService.get_user_profile(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"]
        )
        
        assert result is not None
        assert result["has_profile"] is False
        assert result["user_id"] == user.id

    def test_get_user_profile_with_profile(self, test_session, sample_user_data, sample_profile_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        profile = Profile(
            user_id=user.id,
            **sample_profile_data
        )
        test_session.add(profile)
        test_session.commit()
        
        result = UserService.get_user_profile(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"]
        )
        
        assert result is not None
        assert result["has_profile"] is True
        assert result["name"] == sample_profile_data["name"]
        assert result["age"] == sample_profile_data["age"]
        assert result["gender"] == sample_profile_data["gender"]
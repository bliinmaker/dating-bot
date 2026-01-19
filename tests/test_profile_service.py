import pytest
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.models import *


class TestProfileService:

    def test_create_profile_success(self, test_session, sample_user_data, sample_profile_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        profile_service = ProfileService()
        profile = profile_service.create_profile(
            session=test_session,
            user_id=user.id,
            profile_data=sample_profile_data
        )
        
        assert profile is not None
        assert profile.user_id == user.id
        assert profile.name == sample_profile_data["name"]
        assert profile.age == sample_profile_data["age"]
        assert profile.gender == sample_profile_data["gender"]
        assert profile.bio == sample_profile_data["bio"]
        assert profile.location == sample_profile_data["location"]
        
        assert profile.preferred_gender == "Женский"
        
        db_profile = test_session.query(Profile).filter_by(user_id=user.id).first()
        assert db_profile is not None

    def test_create_profile_female_preferred_gender(self, test_session, sample_user_data, sample_profile_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        profile_data = sample_profile_data.copy()
        profile_data["gender"] = "Женский"
        
        profile_service = ProfileService()
        profile = profile_service.create_profile(
            session=test_session,
            user_id=user.id,
            profile_data=profile_data
        )
        
        assert profile.gender == "Женский"
        assert profile.preferred_gender == "Мужской"

    def test_create_profile_duplicate_user(self, test_session, sample_user_data, sample_profile_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        profile_service = ProfileService()
        
        profile1 = profile_service.create_profile(
            session=test_session,
            user_id=user.id,
            profile_data=sample_profile_data
        )
        assert profile1 is not None
        
        with pytest.raises(Exception):
            profile_service.create_profile(
                session=test_session,
                user_id=user.id,
                profile_data=sample_profile_data
            )

    def test_profile_completeness_calculation(self, test_session, sample_user_data, sample_profile_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        profile_service = ProfileService()
        profile = profile_service.create_profile(
            session=test_session,
            user_id=user.id,
            profile_data=sample_profile_data
        )
        
        assert profile.profile_completeness is not None
        assert profile.profile_completeness >= 0.0
        assert profile.profile_completeness <= 1.0

    def test_create_profile_minimal_data(self, test_session, sample_user_data):
        user = UserService.get_or_create_user(
            session=test_session,
            telegram_id=sample_user_data["telegram_id"],
            telegram_username=sample_user_data["username"]
        )
        
        minimal_data = {
            "name": "Тест",
            "age": 25,
            "gender": "Мужской",
            "location": "Москва",
            "preferred_age_min": 20,
            "preferred_age_max": 30,
            "preferred_gender": "Женский"
        }
        
        profile_service = ProfileService()
        profile = profile_service.create_profile(
            session=test_session,
            user_id=user.id,
            profile_data=minimal_data
        )
        
        assert profile is not None
        assert profile.name == "Тест"
        assert profile.bio is None
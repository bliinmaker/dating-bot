import pytest
from datetime import datetime
from app.models import *


class TestModels:

    def test_user_creation(self, test_session, sample_user_data):
        user = User(
            telegram_id=sample_user_data["telegram_id"],
            username=sample_user_data["username"]
        )
        
        test_session.add(user)
        test_session.commit()
        
        assert user.id is not None
        assert user.telegram_id == sample_user_data["telegram_id"]
        assert user.username == sample_user_data["username"]
        assert user.created_at is not None
        assert user.last_active is not None

    def test_profile_creation(self, test_session, sample_user_data, sample_profile_data):
        user = User(
            telegram_id=sample_user_data["telegram_id"],
            username=sample_user_data["username"]
        )
        test_session.add(user)
        test_session.commit()
        
        profile = Profile(
            user_id=user.id,
            **sample_profile_data
        )
        test_session.add(profile)
        test_session.commit()
        
        assert profile.id is not None
        assert profile.user_id == user.id
        assert profile.name == sample_profile_data["name"]
        assert profile.created_at is not None
        assert profile.updated_at is not None

    def test_user_profile_relationship(self, test_session, sample_user_data, sample_profile_data):
        user = User(
            telegram_id=sample_user_data["telegram_id"],
            username=sample_user_data["username"]
        )
        test_session.add(user)
        test_session.commit()
        
        profile = Profile(
            user_id=user.id,
            **sample_profile_data
        )
        test_session.add(profile)
        test_session.commit()
        
        assert user.profile is not None
        assert user.profile.id == profile.id
        assert profile.user is not None
        assert profile.user.id == user.id

    def test_interaction_creation(self, test_session, sample_user_data, sample_profile_data):
        user1 = User(telegram_id=111, username="user1")
        user2 = User(telegram_id=222, username="user2")
        test_session.add_all([user1, user2])
        test_session.commit()
        
        profile1 = Profile(user_id=user1.id, **sample_profile_data)
        profile_data2 = sample_profile_data.copy()
        profile_data2["name"] = "User2"
        profile2 = Profile(user_id=user2.id, **profile_data2)
        test_session.add_all([profile1, profile2])
        test_session.commit()
        
        interaction = Interaction(
            from_profile_id=profile1.id,
            to_profile_id=profile2.id,
            type="like"
        )
        test_session.add(interaction)
        test_session.commit()
        
        assert interaction.id is not None
        assert interaction.from_profile_id == profile1.id
        assert interaction.to_profile_id == profile2.id
        assert interaction.type == "like"
        assert interaction.created_at is not None

    def test_match_creation(self, test_session, sample_user_data, sample_profile_data):
        user1 = User(telegram_id=333, username="user3")
        user2 = User(telegram_id=444, username="user4")
        test_session.add_all([user1, user2])
        test_session.commit()
        
        profile1 = Profile(user_id=user1.id, **sample_profile_data)
        profile_data2 = sample_profile_data.copy()
        profile_data2["name"] = "User4"
        profile2 = Profile(user_id=user2.id, **profile_data2)
        test_session.add_all([profile1, profile2])
        test_session.commit()
        
        match = Match(
            profile_id_1=profile1.id,
            profile_id_2=profile2.id,
            status="active"
        )
        test_session.add(match)
        test_session.commit()
        
        assert match.id is not None
        assert match.profile_id_1 == profile1.id
        assert match.profile_id_2 == profile2.id
        assert match.status == "active"
        assert match.initiated_chat is False
        assert match.created_at is not None

    def test_rating_creation(self, test_session, sample_user_data, sample_profile_data):
        user = User(
            telegram_id=sample_user_data["telegram_id"],
            username=sample_user_data["username"]
        )
        test_session.add(user)
        test_session.commit()
        
        profile = Profile(user_id=user.id, **sample_profile_data)
        test_session.add(profile)
        test_session.commit()
        
        rating = Rating(
            profile_id=profile.id,
            primary_rating=0.8,
            behavioral_rating=0.7,
            combined_rating=0.75
        )
        test_session.add(rating)
        test_session.commit()
        
        assert rating.id is not None
        assert rating.profile_id == profile.id
        assert rating.primary_rating == 0.8
        assert rating.behavioral_rating == 0.7
        assert rating.combined_rating == 0.75
        assert rating.last_calculated is not None

    def test_photo_creation(self, test_session, sample_user_data, sample_profile_data):
        user = User(
            telegram_id=sample_user_data["telegram_id"],
            username=sample_user_data["username"]
        )
        test_session.add(user)
        test_session.commit()
        
        profile = Profile(user_id=user.id, **sample_profile_data)
        test_session.add(profile)
        test_session.commit()
        
        photo = Photo(
            profile_id=profile.id,
            s3_path="test/path/photo.jpg",
            telegram_file_id="test_file_id",
            is_main=True
        )
        test_session.add(photo)
        test_session.commit()
        
        assert photo.id is not None
        assert photo.profile_id == profile.id
        assert photo.s3_path == "test/path/photo.jpg"
        assert photo.telegram_file_id == "test_file_id"
        assert photo.is_main is True
        assert photo.created_at is not None
import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base
from app.core import config


@pytest.fixture(scope="session")
def test_db_engine():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    test_db_url = f"sqlite:///{temp_db.name}"
    engine = create_engine(test_db_url)
    
    Base.metadata.create_all(engine)
    
    yield engine
    
    engine.dispose()
    os.unlink(temp_db.name)


@pytest.fixture
def test_session(test_db_engine):
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    
    yield session
    
    session.rollback()
    session.close()


@pytest.fixture
def sample_user_data():
    return {
        "telegram_id": 123456789,
        "username": "test_user"
    }


@pytest.fixture
def sample_profile_data():
    return {
        "name": "Тест Пользователь",
        "age": 25,
        "gender": "Мужской",
        "bio": "Тестовое описание",
        "location": "Москва",
        "interests": "Тестовые интересы",
        "preferred_age_min": 20,
        "preferred_age_max": 30,
        "preferred_gender": "Женский",
        "preferred_location": "Москва"
    }
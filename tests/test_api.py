import pytest
from fastapi.testclient import TestClient
from app.api.server import app, get_db
from tests.conftest import test_session


def get_test_db(test_session):
    def _get_test_db():
        return test_session
    return _get_test_db


@pytest.fixture
def client(test_session):
    app.dependency_overrides[get_db] = get_test_db(test_session)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestAPI:

    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dating-bot-api"

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Dating Bot API работает" in data["message"]
        assert data["version"] == "1.0.0"

    def test_create_user(self, client, sample_user_data):
        response = client.post("/users", json=sample_user_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["telegram_id"] == sample_user_data["telegram_id"]
        assert data["username"] == sample_user_data["username"]
        assert "id" in data
        assert "created_at" in data

    def test_get_user(self, client, sample_user_data):
        create_response = client.post("/users", json=sample_user_data)
        assert create_response.status_code == 200
        
        telegram_id = sample_user_data["telegram_id"]
        response = client.get(f"/users/{telegram_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["telegram_id"] == telegram_id
        assert data["username"] == sample_user_data["username"]

    def test_get_nonexistent_user(self, client):
        response = client.get("/users/999999999")
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]

    def test_create_profile(self, client, sample_user_data, sample_profile_data):
        user_response = client.post("/users", json=sample_user_data)
        assert user_response.status_code == 200
        
        telegram_id = sample_user_data["telegram_id"]
        response = client.post(f"/users/{telegram_id}/profile", json=sample_profile_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == sample_profile_data["name"]
        assert data["age"] == sample_profile_data["age"]
        assert data["gender"] == sample_profile_data["gender"]
        assert "id" in data
        assert "user_id" in data

    def test_get_user_profile(self, client, sample_user_data, sample_profile_data):
        telegram_id = sample_user_data["telegram_id"]
        client.post("/users", json=sample_user_data)
        client.post(f"/users/{telegram_id}/profile", json=sample_profile_data)
        
        response = client.get(f"/users/{telegram_id}/profile")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_profile"] is True
        assert data["name"] == sample_profile_data["name"]

    def test_get_profile_for_user_without_profile(self, client, sample_user_data):
        telegram_id = sample_user_data["telegram_id"]
        client.post("/users", json=sample_user_data)
        
        response = client.get(f"/users/{telegram_id}/profile")
        assert response.status_code == 404
        assert "Профиль не найден" in response.json()["detail"]

    def test_get_stats(self, client, sample_user_data, sample_profile_data):
        telegram_id = sample_user_data["telegram_id"]
        client.post("/users", json=sample_user_data)
        client.post(f"/users/{telegram_id}/profile", json=sample_profile_data)
        
        response = client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_users" in data
        assert "total_profiles" in data
        assert "total_interactions" in data
        assert "total_matches" in data
        assert data["total_users"] >= 1
        assert data["total_profiles"] >= 1
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
from app.main import app
from app.core.database import get_db
from app.core.models import User
import uuid

client = TestClient(app)

@pytest.fixture
def mock_db():
    mock = AsyncMock()
    return mock

@pytest.fixture
def override_get_db(mock_db):
    async def _override():
        yield mock_db
    return _override

def test_register_user(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Mock existing user check (return None)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Mock refresh to set ID and other fields
    async def mock_refresh(instance):
        instance.id = uuid.uuid4()
        instance.is_active = True
        instance.created_at = "2023-01-01T00:00:00"
    
    mock_db.refresh.side_effect = mock_refresh
    
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data
    
    # Verify DB calls
    assert mock_db.add.called
    assert mock_db.commit.called
    assert mock_db.refresh.called

def test_register_existing_user(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    
    # Mock existing user check (return User)
    mock_user = User(email="test@example.com")
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_user
    mock_db.execute.return_value = mock_result
    
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "The user with this email already exists in the system."

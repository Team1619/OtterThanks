import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from backend.app.auth import create_session_token
from backend.app.config import settings
from backend.app.database import Base, get_db
from backend.app.main import app

# Use in-memory SQLite with StaticPool so all connections share the same memory database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    # Initialize tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_serve_frontend_index():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "OtterThanks" in response.text
        assert '<div id="root"></div>' in response.text


@pytest.mark.asyncio
async def test_create_kudos_team():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "team",
                "message": "Incredible job at the regional competition!",
                "sender_name": "Coach Steve",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["recipient_type"] == "team"
        assert data["recipient_name"] is None
        assert data["message"] == "Incredible job at the regional competition!"
        assert data["sender_name"] == "Coach Steve"
        assert data["slack_status"] == "pending"


@pytest.mark.asyncio
async def test_create_kudos_individual_with_anonymous():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "individual",
                "recipient_name": "Jordan",
                "message": "Thanks for fixing the intake mechanism between matches!",
                "sender_name": "",  # Empty should default to Anonymous
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["recipient_type"] == "individual"
        assert data["recipient_name"] == "Jordan"
        assert data["sender_name"] == "Anonymous"
        assert data["slack_status"] == "pending"


@pytest.mark.asyncio
async def test_create_kudos_validation_errors():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Missing recipient_name when recipient_type is individual
        res1 = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "individual",
                "recipient_name": "",
                "message": "Good job!",
            },
        )
        assert res1.status_code == 422

        # Invalid recipient_type
        res2 = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "robot",
                "message": "Good job!",
            },
        )
        assert res2.status_code == 422

        # Message too short
        res3 = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "team",
                "message": " ",
            },
        )
        assert res3.status_code == 422


@pytest.mark.asyncio
async def test_list_and_update_status():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create a kudos
        create_res = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "team",
                "message": "Team kudos for Slack bot test",
                "sender_name": "Bot Tester",
            },
        )
        kudos_id = create_res.json()["id"]

        # List pending kudos
        list_res = await client.get("/api/kudos?status=pending")
        assert list_res.status_code == 200
        items = list_res.json()
        assert len(items) >= 1
        assert any(item["id"] == kudos_id for item in items)

        # Update status to sent (simulating Slack microservice)
        patch_res = await client.patch(
            f"/api/kudos/{kudos_id}/status",
            json={"slack_status": "sent"},
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["slack_status"] == "sent"
        assert updated["slack_sent_at"] is not None

        # Verify it no longer appears under pending
        list_pending = await client.get("/api/kudos?status=pending")
        assert not any(item["id"] == kudos_id for item in list_pending.json())


@pytest.mark.asyncio
async def test_mentor_auth_and_kudos_management():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Unauthenticated request to mentor endpoint should fail (401)
        unauth_res = await client.get("/api/mentor/kudos")
        assert unauth_res.status_code == 401

        # 2. Check auth config
        config_res = await client.get("/api/auth/config")
        assert config_res.status_code == 200
        assert "dev_mode" in config_res.json()

        # 3. Create a test session token for a mentor
        mentor_token = create_session_token(
            {
                "email": "mentor.alice@team1619.net",
                "name": "Mentor Alice",
                "picture": None,
            }
        )
        client.cookies.set(settings.session_cookie_name, mentor_token)

        # 4. Check /api/auth/me with session cookie
        me_res = await client.get("/api/auth/me")
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["authenticated"] is True
        assert me_data["email"] == "mentor.alice@team1619.net"
        assert me_data["role"] == "mentor"

        # 5. Create some test kudos
        await client.post(
            "/api/kudos",
            json={
                "recipient_type": "individual",
                "recipient_name": "Taylor",
                "message": "Great work on the shooter tuning!",
                "sender_name": "Mentor Alice",
            },
        )

        # 6. Authenticated mentor query to list kudos
        mentor_kudos_res = await client.get("/api/mentor/kudos")
        assert mentor_kudos_res.status_code == 200
        data = mentor_kudos_res.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        kudos_entry = data["items"][0]
        kudos_id = kudos_entry["id"]

        # 7. Mentor changes status
        patch_res = await client.patch(
            f"/api/mentor/kudos/{kudos_id}/status",
            json={"slack_status": "sent"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["slack_status"] == "sent"

        # 8. Mentor deletes kudos
        del_res = await client.delete(f"/api/mentor/kudos/{kudos_id}")
        assert del_res.status_code == 204

        # 9. Verify deletion
        get_deleted = await client.get(f"/api/kudos/{kudos_id}")
        assert get_deleted.status_code == 404

        # 10. Logout
        logout_res = await client.post("/api/auth/logout")
        assert logout_res.status_code == 200


@pytest.mark.asyncio
async def test_mentor_release_to_slack(monkeypatch):
    from backend.app.routers import mentor

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        mentor_token = create_session_token(
            {
                "email": "mentor.alice@team1619.net",
                "name": "Mentor Alice",
                "picture": None,
            }
        )
        client.cookies.set(settings.session_cookie_name, mentor_token)

        # Create a pending kudos
        create_res = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "team",
                "message": "Testing Slack release button!",
                "sender_name": "Mentor Alice",
            },
        )
        kudos_id = create_res.json()["id"]

        # Mock Slack post failure
        async def mock_slack_fail(kudos):
            return False, "channel_not_found"

        monkeypatch.setattr(mentor, "post_kudos_to_slack", mock_slack_fail)
        fail_res = await client.post(f"/api/mentor/kudos/{kudos_id}/release")
        assert fail_res.status_code == 400
        assert "channel_not_found" in fail_res.json()["detail"]

        # Mock Slack post success
        async def mock_slack_success(kudos):
            return True, None

        monkeypatch.setattr(mentor, "post_kudos_to_slack", mock_slack_success)
        success_res = await client.post(f"/api/mentor/kudos/{kudos_id}/release")
        assert success_res.status_code == 200
        data = success_res.json()
        assert data["slack_status"] == "sent"
        assert data["slack_sent_at"] is not None


@pytest.mark.asyncio
async def test_slack_interactive_approve_and_reject(monkeypatch):
    import json
    from backend.app.routers import slack

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create a kudos to approve
        res1 = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "team",
                "message": "Slack button approval test!",
                "sender_name": "Slack Tester",
            },
        )
        kudos_approve_id = res1.json()["id"]

        # Mock public Slack post
        async def mock_post_slack(kudos):
            return True, None

        monkeypatch.setattr(slack, "post_kudos_to_slack", mock_post_slack)
        monkeypatch.setattr(slack, "verify_slack_signature", lambda b, t, s: True)

        # 1. Simulate Slack 'approve_kudos' button click
        approve_payload = {
            "type": "block_actions",
            "user": {"name": "coach_dan", "username": "dan"},
            "actions": [
                {
                    "action_id": "approve_kudos",
                    "value": str(kudos_approve_id),
                }
            ],
        }

        resp = await client.post(
            "/api/slack/interactions",
            data={"payload": json.dumps(approve_payload)},
        )
        assert resp.status_code == 200
        resp_data = resp.json()
        assert resp_data["replace_original"] is True
        assert "approved" in resp_data["text"]

        # Verify DB status is 'sent'
        get_res1 = await client.get(f"/api/kudos/{kudos_approve_id}")
        assert get_res1.json()["slack_status"] == "sent"

        # 2. Simulate Slack 'reject_kudos' button click
        res2 = await client.post(
            "/api/kudos",
            json={
                "recipient_type": "individual",
                "recipient_name": "Spam",
                "message": "Spam message test",
                "sender_name": "Spammer",
            },
        )
        kudos_reject_id = res2.json()["id"]

        reject_payload = {
            "type": "block_actions",
            "user": {"name": "coach_dan", "username": "dan"},
            "actions": [
                {
                    "action_id": "reject_kudos",
                    "value": str(kudos_reject_id),
                }
            ],
        }

        resp2 = await client.post(
            "/api/slack/interactions",
            data={"payload": json.dumps(reject_payload)},
        )
        assert resp2.status_code == 200
        resp_data2 = resp2.json()
        assert resp_data2["replace_original"] is True
        assert "rejected" in resp_data2["text"]

        # Verify DB status is 'rejected'
        get_res2 = await client.get(f"/api/kudos/{kudos_reject_id}")
        assert get_res2.json()["slack_status"] == "rejected"

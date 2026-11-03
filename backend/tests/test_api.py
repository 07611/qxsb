from __future__ import annotations

import time
from pathlib import Path

from app.config import settings


def test_health_and_public_content(client):
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["data"]["database"] == "ok"
    items = client.get("/api/v1/items?pageSize=2")
    assert items.status_code == 200
    assert len(items.json()["data"]["items"]) <= 2
    categories = client.get("/api/v1/categories")
    assert categories.status_code == 200
    assert categories.json()["data"]["categories"]


def test_auth_rbac_and_sessions(client, user_headers, admin_headers):
    assert client.get("/api/v1/auth/me").status_code == 401
    me = client.get("/api/v1/auth/me", headers=user_headers)
    assert me.status_code == 200
    assert me.json()["data"]["user"]["email"] == "demo@moodwave.app"
    assert client.get("/api/v1/admin/stats", headers=user_headers).status_code == 403
    assert client.get("/api/v1/admin/stats", headers=admin_headers).status_code == 200
    sessions = client.get("/api/v1/auth/sessions", headers=user_headers)
    assert sessions.status_code == 200
    assert sessions.json()["data"]["items"]
    refreshed = client.post("/api/v1/auth/refresh", json={})
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["accessToken"]


def test_registration_duplicate_and_validation(client):
    suffix = int(time.time() * 1000)
    payload = {
        "email": f"pytest-{suffix}@example.com",
        "password": "TestPass123",
        "nickname": f"测试用户{suffix % 10000}",
    }
    created = client.post("/api/v1/auth/register", json=payload)
    assert created.status_code == 200, created.text
    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409
    assert "已注册" in duplicate.json()["message"]
    invalid = client.post("/api/v1/auth/register", json={**payload, "email": "not-an-email"})
    assert invalid.status_code == 422
    assert invalid.json()["data"]["errors"]


def test_item_crud_search_and_ownership(client, user_headers, admin_headers):
    categories = client.get("/api/v1/categories").json()["data"]["categories"]
    category_id = categories[0]["children"][0]["id"]
    created = client.post(
        "/api/v1/items",
        headers=user_headers,
        json={
            "title": "pytest 情绪歌单",
            "content": "雨声、钢琴与城市夜晚。\n\n第二段用于搜索高亮。",
            "categoryId": category_id,
            "tags": ["pytest", "雨声"],
            "status": "published",
        },
    )
    assert created.status_code == 201, created.text
    item_id = created.json()["data"]["item"]["id"]
    detail = client.get(f"/api/v1/items/{item_id}", headers=user_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["item"]["canEdit"] is True
    updated = client.put(
        f"/api/v1/items/{item_id}",
        headers=user_headers,
        json={"title": "pytest 情绪歌单已更新", "content": "更新后的内容", "categoryId": category_id, "tags": ["pytest"], "status": "published"},
    )
    assert updated.status_code == 200
    # 另一个普通用户不能修改该内容：401/403 语义分离
    other_suffix = int(time.time() * 1000000) % 100000000
    other = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"pytest-other-{other_suffix}@example.com",
            "password": "OtherPass123",
            "nickname": f"路人{other_suffix % 10000}",
        },
    )
    assert other.status_code == 200
    other_headers = {"Authorization": f"Bearer {other.json()['data']['accessToken']}"}
    forbidden = client.put(
        f"/api/v1/items/{item_id}",
        headers=other_headers,
        json={"title": "越权修改标题", "content": "越权修改内容", "status": "published"},
    )
    assert forbidden.status_code == 403
    # 管理员具备 content:manage，可以代为编辑
    admin_edit = client.put(
        f"/api/v1/items/{item_id}",
        headers=admin_headers,
        json={"title": "管理员编辑后的标题", "content": "管理员编辑内容", "status": "published"},
    )
    assert admin_edit.status_code == 200
    search = client.get("/api/v1/search?q=管理员编辑")
    assert search.status_code == 200
    assert any("管理员编辑" in item["title"] for item in search.json()["data"]["results"]["items"])


def test_emotion_demo_mapping_and_recommendations(client, user_headers):
    expected = {
        "happy": "happy",
        "sad": "sad",
        "angry": "angry",
        "surprised": "surprised",
        "fear": "fear",
        "neutral": "neutral",
    }
    for demo_id, expected_emotion in expected.items():
        response = client.post(
            "/api/v1/emotion/analyze",
            data={"demoId": demo_id, "source": "demo"},
            headers=user_headers,
        )
        assert response.status_code == 200, response.text
        payload = response.json()["data"]
        assert payload["emotion"] == expected_emotion, (demo_id, payload["emotion"], payload["scores"])
        assert 0 < payload["confidence"] <= 1
        rec = client.get(f"/api/v1/music/recommendations?emotion={expected_emotion}&limit=6&includeOnline=false", headers=user_headers)
        assert rec.status_code == 200
        assert rec.json()["data"]["local"], expected_emotion
    history = client.get("/api/v1/emotion/history", headers=user_headers)
    assert history.status_code == 200
    assert history.json()["data"]["pagination"]["total"] >= 6


def test_notifications_feedback_and_admin_flow(client, user_headers, admin_headers):
    notes = client.get("/api/v1/notifications", headers=user_headers)
    assert notes.status_code == 200
    unread = client.get("/api/v1/notifications/unread-count", headers=user_headers)
    assert unread.status_code == 200
    marked = client.patch("/api/v1/notifications/read-all", headers=user_headers)
    assert marked.status_code == 200
    assert client.get("/api/v1/notifications/unread-count", headers=user_headers).json()["data"]["count"] == 0

    feedback = client.post(
        "/api/v1/feedback",
        headers=user_headers,
        json={"type": "bug", "content": "pytest 反馈工单内容，用于验证管理员回复。", "images": []},
    )
    assert feedback.status_code == 201, feedback.text
    ticket = feedback.json()["data"]["feedback"]
    reply = client.patch(
        f"/api/v1/admin/feedback/{ticket['id']}",
        headers=admin_headers,
        json={"status": "processing", "reply": "已收到，正在处理。"},
    )
    assert reply.status_code == 200
    assert reply.json()["data"]["feedback"]["status"] == "processing"


def test_upload_presign_and_attachment(client, user_headers, tmp_path):
    image_path = Path(settings.demo_dir) / "neutral.jpg"
    content = image_path.read_bytes()
    presign = client.post(
        "/api/v1/upload/presign",
        headers=user_headers,
        json={"filename": "neutral.jpg", "mime": "image/jpeg", "size": len(content), "bizType": "test"},
    )
    assert presign.status_code == 200, presign.text
    data = presign.json()["data"]
    put = client.put(
        data["uploadUrl"],
        headers={"Content-Type": "image/jpeg", "Authorization": user_headers["Authorization"]},
        content=content,
    )
    assert put.status_code == 200, put.text
    assert put.json()["data"]["thumbUrl"].endswith("_400.webp")
    attachment = client.post(
        "/api/v1/attachments",
        headers=user_headers,
        json={"uploadToken": data["uploadToken"], "bizType": "test"},
    )
    assert attachment.status_code == 201, attachment.text
    assert attachment.json()["data"]["attachment"]["width"] > 0
    assert attachment.json()["data"]["attachment"]["size"] > 0


def test_idempotency_and_share(client, user_headers):
    key = f"pytest-idem-{time.time_ns()}"
    body = {"targetType": "item", "targetId": 1, "expiresInDays": 2}
    first = client.post("/api/v1/shares", headers={**user_headers, "X-Idempotency-Key": key}, json=body)
    second = client.post("/api/v1/shares", headers={**user_headers, "X-Idempotency-Key": key}, json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["code"] == second.json()["data"]["code"]
    assert second.headers.get("x-idempotent-replay") == "true"
    code = first.json()["data"]["code"]
    landing = client.get(f"/s/{code}")
    assert landing.status_code == 200
    assert 'property="og:title"' in landing.text


def test_profile_avatar_and_push_banner_admin(client, user_headers, admin_headers):
    # profile PATCH only changes own record and keeps email immutable without re-verification
    profile = client.patch(
        "/api/v1/users/me",
        headers=user_headers,
        json={"bio": "pytest 更新后的简介", "location": "杭州", "locale": "zh-CN"},
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["data"]["user"]["location"] == "杭州"
    blocked = client.patch("/api/v1/users/me", headers=user_headers, json={"email": "hijack@example.com"})
    assert blocked.status_code == 422

    # dedicated avatar endpoint compresses server-side to 512x512 webp
    image_bytes = (Path(settings.demo_dir) / "neutral.jpg").read_bytes()
    avatar = client.post(
        "/api/v1/users/me/avatar",
        headers=user_headers,
        files={"file": ("avatar.jpg", image_bytes, "image/jpeg")},
    )
    assert avatar.status_code == 200, avatar.text
    assert avatar.json()["data"]["width"] == 512

    push = client.post(
        "/api/v1/admin/push/send",
        headers=admin_headers,
        json={
            "templateCode": "system_notice",
            "content": "pytest 推送模板内容",
            "userIds": [2],
            "channels": ["inapp"],
            "marketing": False,
        },
    )
    assert push.status_code == 200, push.text
    assert push.json()["data"]["tasksCreated"] >= 1

    banner = client.post(
        "/api/v1/admin/banners",
        headers=admin_headers,
        json={
            "position": "home",
            "title": "pytest 运营位",
            "subtitle": "测试运营位",
            "imageUrl": "/media/banners/banner-hero.svg",
            "linkUrl": "/algorithms",
            "sort": 0,
            "status": "active",
            "aspectRatio": "16/5",
        },
    )
    assert banner.status_code == 201, banner.text
    banner_id = banner.json()["data"]["banner"]["id"]
    deleted = client.delete(f"/api/v1/admin/banners/{banner_id}", headers=admin_headers)
    assert deleted.status_code == 200


def test_reports_and_analytics(client, admin_headers):
    report = client.get("/api/v1/reports/overview?from=2026-01-01&to=2026-12-31", headers=admin_headers)
    assert report.status_code == 200, report.text
    assert "series" in report.json()["data"]
    csv_response = client.get("/api/v1/reports/emotions?from=2026-01-01&to=2026-12-31&format=csv", headers=admin_headers)
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    tracked = client.post(
        "/api/v1/track",
        json={
            "events": [
                {
                    "eventKey": "page_view",
                    "sessionId": "pytest-session-1234",
                    "props": {"route": "/pytest", "email": "should-not-store@example.com"},
                }
            ]
        },
    )
    assert tracked.status_code == 200
    assert tracked.json()["data"]["accepted"] == 1
    funnel = client.get("/api/v1/admin/analytics/funnel", headers=admin_headers)
    assert funnel.status_code == 200
    assert funnel.json()["data"]["steps"]


def test_password_reset_flow(client, user_headers):
    forgot = client.post("/api/v1/auth/password/forgot", json={"email": "demo@moodwave.app"})
    assert forgot.status_code == 200
    # 默认 DEBUG=true，但测试环境显式关闭 EXPOSE_DEV_RESET_LINK，不能泄露链接
    assert forgot.json()["data"]["devResetUrl"] is None
    unknown = client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200
    assert unknown.json()["data"]["message"] == forgot.json()["data"]["message"]

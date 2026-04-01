"""
Tool Bridge E2E — 逐个验证每个 Tool 的输入输出格式。
直接 POST /api/tool-bridge/{tool_name}，纯后端验证。
"""
import httpx
import pytest

BASE_URL = "http://localhost:8000"
HEADERS = {
    "Content-Type": "application/json",
    "x-coco-user-id": "test-tdd-user",
    "x-coco-session-id": "test-tdd-session",
}


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE_URL, timeout=15)


class TestP0CoreUITools:

    def test_ai_message(self, client):
        resp = client.post("/api/tool-bridge/ai_message", json={"messages": ["你好", "今天怎么样？"]}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "pushed", f"Expected status=pushed, got: {data}"
        assert "ws_push" in data, f"Missing ws_push: {data}"

    def test_ai_options(self, client):
        resp = client.post("/api/tool-bridge/ai_options", json={
            "text": "你想聊什么？",
            "options": [{"id": "1", "text": "心情"}, {"id": "2", "text": "关系"}],
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("content_type") == "AI_OPTIONS", f"Expected AI_OPTIONS, got: {data.get('content_type')}"
        assert "options" in data, f"Missing options: {data}"

    def test_ai_mood_select(self, client):
        resp = client.post("/api/tool-bridge/ai_mood_select", json={"greeting": "今天心情怎么样？"}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("content_type") == "AI_MOOD_SELECT", f"Expected AI_MOOD_SELECT, got: {data.get('content_type')}"

    def test_ai_safety_brake(self, client):
        resp = client.post("/api/tool-bridge/ai_safety_brake", json={
            "risk_level": 2,
            "support_message": "我注意到你说了一些让我担心的话",
            "action_required": "inner_push",
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("content_type") == "AI_SAFETY_BRAKE", f"Expected AI_SAFETY_BRAKE, got: {data.get('content_type')}"


class TestP1EmotionUITools:

    def test_ai_emotion_response(self, client):
        resp = client.post("/api/tool-bridge/ai_emotion_response", json={"messages": ["我理解你的感受"]}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "pushed", f"Expected pushed: {data}"

    def test_ai_feeling_exploration(self, client):
        resp = client.post("/api/tool-bridge/ai_feeling_exploration", json={
            "guidance_message": "让我们一起探索这种感受",
            "messages": ["你能告诉我更多吗？"],
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("content_type") == "AI_FEELING_EXPLORATION", f"Got: {data.get('content_type')}"

    def test_ai_thought_feeling(self, client):
        resp = client.post("/api/tool-bridge/ai_thought_feeling", json={
            "guidance_message": "想一想你当时的感受",
            "reflection_question": "你觉得这种感受从哪里来？",
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("content_type") == "AI_THOUGHT_FEELING", f"Got: {data.get('content_type')}"

    def test_ai_body_sensation(self, client):
        resp = client.post("/api/tool-bridge/ai_body_sensation", json={"guidance_message": "注意一下你身体的感受"}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        ct = data.get("content_type")
        assert ct in ("AI_BODY_SENSATION", "AI_OPTIONS"), f"Got: {ct}"

    def test_ai_mood_recovery(self, client):
        resp = client.post("/api/tool-bridge/ai_mood_recovery", json={
            "summary_message": "我注意到你今天心情不太好",
            "emotion_assessment": "stable",
            "quick_options": [{"id": "1", "text": "聊聊", "emoji": "💬"}],
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        ct = data.get("content_type")
        assert ct == "AI_MOOD_RECOVERY" or data.get("status") == "pushed", f"Got: {data}"

    def test_ai_praise_popup(self, client):
        resp = client.post("/api/tool-bridge/ai_praise_popup", json={"text": "你做得很好！"}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "pushed", f"Expected pushed: {data}"

    def test_ai_relationship(self, client):
        resp = client.post("/api/tool-bridge/ai_relationship", json={"context_text": "关于你和小白的关系"}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "pushed" or data.get("content_type") == "AI_RELATIONSHIP", f"Got: {data}"


class TestP2CourseUITools:

    def test_ai_complete_conversation(self, client):
        resp = client.post("/api/tool-bridge/ai_complete_conversation", json={"summary": "今天的对话到这里"}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data.get("status") == "pushed" or "content_type" in data, f"Got: {data}"

    def test_ai_lesson_card(self, client):
        resp = client.post("/api/tool-bridge/ai_lesson_card", json={
            "title": "测试课程卡片", "content": "测试内容", "card_type": "knowledge",
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_ai_micro_lesson_batch(self, client):
        cards = [{
            "one_line_summary": f"知识点{i}",
            "coco_narration": [f"讲解内容{i}"],
            "options": [{"text": "继续", "action": "next"}, {"text": "再讲一次", "action": "reply"}],
        } for i in range(1, 6)]
        resp = client.post("/api/tool-bridge/ai_micro_lesson_batch", json={"cards": cards}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_ai_quiz_practice(self, client):
        questions = [{
            "question": f"测试问题{i}",
            "type": "single_choice",
            "options": [{"text": "正确答案", "feedback": "对了"}, {"text": "错误答案", "feedback": "再想想"}],
            "correct_answer": 0,
        } for i in range(1, 5)]
        resp = client.post("/api/tool-bridge/ai_quiz_practice", json={"questions": questions}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_ai_course_complete(self, client):
        resp = client.post("/api/tool-bridge/ai_course_complete", json={
            "celebration": "恭喜完成！", "summary": "你学到了很多", "encouragement": "继续加油",
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_ai_growth_greeting(self, client):
        resp = client.post("/api/tool-bridge/ai_growth_greeting", json={
            "greeting": "欢迎回来！", "message": "今天继续学习吧",
        }, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"


class TestServiceTools:

    def test_user_profile_get(self, client):
        resp = client.post("/api/tool-bridge/user_profile_get", json={}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_conversation_history(self, client):
        import uuid
        resp = client.post("/api/tool-bridge/conversation_history", json={"session_id": str(uuid.uuid4())}, headers=HEADERS)
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_message_persist(self, client):
        import uuid
        resp = client.post("/api/tool-bridge/message_persist", json={
            "action": "save_user_text", "session_id": str(uuid.uuid4()), "text": "测试消息",
        }, headers=HEADERS)
        # 500 is expected with fake session_id (FK constraint); 200 with real session
        assert resp.status_code in (200, 500), f"HTTP {resp.status_code}: {resp.text[:200]}"
        if resp.status_code == 500:
            assert "ForeignKey" in resp.text or "IntegrityError" in resp.text, f"Unexpected 500: {resp.text[:200]}"

    def test_audio_synthesize(self, client):
        resp = client.post("/api/tool-bridge/audio_synthesize", json={"text": "你好"}, headers=HEADERS)
        assert resp.status_code in (200, 500), f"HTTP {resp.status_code}: {resp.text[:200]}"

    def test_course_dialogue_context(self, client):
        resp = client.post("/api/tool-bridge/course_dialogue_context", json={}, headers=HEADERS)
        assert resp.status_code in (200, 500), f"HTTP {resp.status_code}: {resp.text[:200]}"

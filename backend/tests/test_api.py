"""Tests for the FastAPI endpoints' request/response handling"""
import pytest

from conftest import RAG_COURSE, MCP_COURSE, SAMPLE_SOURCES, ROOT_HTML

pytestmark = pytest.mark.api


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:
    def test_returns_answer_sources_and_session(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is a vector database?"})

        assert response.status_code == 200
        assert response.json() == {
            "answer": "Vector databases store embeddings.",
            "sources": SAMPLE_SOURCES,
            "session_id": "session_1",
        }

    def test_creates_session_when_none_given(self, client, mock_rag_system):
        client.post("/api/query", json={"query": "hi"})

        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("hi", "session_1")

    def test_reuses_given_session(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "hi", "session_id": "existing"})

        assert response.json()["session_id"] == "existing"
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("hi", "existing")

    def test_source_link_is_optional(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("answer", [{"text": "Some Course"}])

        response = client.post("/api/query", json={"query": "hi"})

        assert response.json()["sources"] == [{"text": "Some Course", "link": None}]

    def test_no_sources(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("Hello!", [])

        response = client.post("/api/query", json={"query": "hi"})

        assert response.status_code == 200
        assert response.json()["sources"] == []

    @pytest.mark.parametrize("body", [{}, {"session_id": "s"}, {"query": None}, {"query": 123}])
    def test_rejects_invalid_body(self, client, mock_rag_system, body):
        response = client.post("/api/query", json=body)

        assert response.status_code == 422
        mock_rag_system.query.assert_not_called()

    def test_rejects_non_json_body(self, client):
        response = client.post("/api/query", content="not json",
                               headers={"Content-Type": "application/json"})

        assert response.status_code == 422

    def test_rag_error_becomes_500_with_detail(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("Anthropic API unavailable")

        response = client.post("/api/query", json={"query": "hi"})

        assert response.status_code == 500
        assert response.json() == {"detail": "Anthropic API unavailable"}

    def test_get_not_allowed(self, client):
        assert client.get("/api/query").status_code == 405


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:
    def test_returns_course_stats(self, client):
        response = client.get("/api/courses")

        assert response.status_code == 200
        assert response.json() == {
            "total_courses": 2,
            "course_titles": [RAG_COURSE, MCP_COURSE],
        }

    def test_empty_catalog(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {"total_courses": 0, "course_titles": []}

        response = client.get("/api/courses")

        assert response.json() == {"total_courses": 0, "course_titles": []}

    def test_analytics_error_becomes_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("ChromaDB down")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert response.json() == {"detail": "ChromaDB down"}

    def test_malformed_analytics_becomes_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.return_value = {"course_titles": []}

        response = client.get("/api/courses")

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /api/session/{session_id}
# ---------------------------------------------------------------------------

class TestSessionEndpoint:
    def test_deletes_session(self, client, mock_rag_system):
        response = client.delete("/api/session/session_1")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_rag_system.session_manager.delete_session.assert_called_once_with("session_1")


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestRoot:
    def test_serves_html(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.text == ROOT_HTML

    def test_unknown_route_is_404(self, client):
        assert client.get("/api/does-not-exist").status_code == 404

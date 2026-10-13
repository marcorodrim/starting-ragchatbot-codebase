"""Tests for CourseSearchTool.execute and ToolManager"""
import pytest

from config import config
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults

from conftest import (
    RAG_COURSE, MCP_COURSE, RAG_COURSE_LINK, MCP_COURSE_LINK,
    VECTOR_DB_TEXT, MCP_SERVER_TEXT,
)


def results(docs_and_meta):
    return SearchResults(
        documents=[d for d, _ in docs_and_meta],
        metadata=[m for _, m in docs_and_meta],
        distances=[0.1] * len(docs_and_meta),
    )


# ---------------------------------------------------------------------------
# Unit tests (mocked vector store)
# ---------------------------------------------------------------------------

class TestExecuteWithMockStore:

    def test_forwards_parameters_to_store(self, mock_store):
        mock_store.search.return_value = results([])
        CourseSearchTool(mock_store).execute(query="embeddings", course_name="RAG", lesson_number=2)
        mock_store.search.assert_called_once_with(query="embeddings", course_name="RAG", lesson_number=2)

    def test_returns_store_error_verbatim(self, mock_store):
        mock_store.search.return_value = SearchResults.empty("No course found matching 'XYZ'")
        assert CourseSearchTool(mock_store).execute(query="q", course_name="XYZ") == "No course found matching 'XYZ'"

    def test_empty_results_without_filters(self, mock_store):
        mock_store.search.return_value = results([])
        assert CourseSearchTool(mock_store).execute(query="q") == "No relevant content found."

    def test_empty_results_mentions_filters(self, mock_store):
        mock_store.search.return_value = results([])
        out = CourseSearchTool(mock_store).execute(query="q", course_name="RAG", lesson_number=2)
        assert out == "No relevant content found in course 'RAG' in lesson 2."

    def test_empty_results_mentions_lesson_zero(self, mock_store):
        mock_store.search.return_value = results([])
        out = CourseSearchTool(mock_store).execute(query="q", lesson_number=0)
        assert out == "No relevant content found in lesson 0."

    def test_formats_results_with_headers(self, mock_store):
        mock_store.search.return_value = results([
            ("doc one", {"course_title": RAG_COURSE, "lesson_number": 1}),
            ("doc two", {"course_title": MCP_COURSE, "lesson_number": None}),
        ])
        out = CourseSearchTool(mock_store).execute(query="q")
        assert out == f"[{RAG_COURSE} - Lesson 1]\ndoc one\n\n[{MCP_COURSE}]\ndoc two"

    def test_tracks_sources_with_lesson_link(self, mock_store):
        mock_store.search.return_value = results([("d", {"course_title": RAG_COURSE, "lesson_number": 1})])
        mock_store.get_lesson_link.return_value = f"{RAG_COURSE_LINK}/1"
        tool = CourseSearchTool(mock_store)
        tool.execute(query="q")
        assert tool.last_sources == [{"text": f"{RAG_COURSE} - Lesson 1", "link": f"{RAG_COURSE_LINK}/1"}]
        mock_store.get_lesson_link.assert_called_once_with(RAG_COURSE, 1)

    def test_source_falls_back_to_course_link(self, mock_store):
        mock_store.search.return_value = results([("d", {"course_title": MCP_COURSE, "lesson_number": 1})])
        mock_store.get_course_link.return_value = MCP_COURSE_LINK
        tool = CourseSearchTool(mock_store)
        tool.execute(query="q")
        assert tool.last_sources == [{"text": f"{MCP_COURSE} - Lesson 1", "link": MCP_COURSE_LINK}]


class TestToolManager:

    def test_executes_registered_tool_by_name(self, mock_store):
        mock_store.search.return_value = results([])
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        assert manager.execute_tool("search_course_content", query="q") == "No relevant content found."

    def test_unknown_tool(self):
        assert ToolManager().execute_tool("nope") == "Tool 'nope' not found"

    def test_tool_exception_propagates(self, mock_store):
        mock_store.search.side_effect = RuntimeError("boom")
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        with pytest.raises(RuntimeError, match="boom"):
            manager.execute_tool("search_course_content", query="q")

    def test_unexpected_arguments_propagates(self, mock_store):
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        with pytest.raises(TypeError):
            manager.execute_tool("search_course_content", query="q", bogus_arg=1)

    def test_sources_reset(self, mock_store):
        mock_store.search.return_value = results([("d", {"course_title": RAG_COURSE, "lesson_number": 1})])
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_store))
        manager.execute_tool("search_course_content", query="q")
        assert manager.get_last_sources()
        manager.reset_sources()
        assert manager.get_last_sources() == []


# ---------------------------------------------------------------------------
# Integration tests (real ChromaDB, real config)
# ---------------------------------------------------------------------------

class TestExecuteWithRealStore:

    def test_config_max_results_is_positive(self):
        max_results = config.MAX_RESULTS  # local copy keeps the config (and API key) out of failure output
        assert max_results > 0, f"MAX_RESULTS={max_results}; ChromaDB rejects n_results <= 0, so every search fails"

    def test_search_returns_content_not_error(self, real_store):
        out = CourseSearchTool(real_store).execute(query="How do vector databases store embeddings?")
        assert not out.startswith("Search error"), out
        assert VECTOR_DB_TEXT in out

    def test_search_with_course_and_lesson_filter(self, real_store):
        tool = CourseSearchTool(real_store)
        out = tool.execute(query="what is covered", course_name="MCP", lesson_number=1)
        assert not out.startswith("Search error"), out
        assert MCP_SERVER_TEXT in out
        assert RAG_COURSE not in out
        assert tool.last_sources == [{"text": f"{MCP_COURSE} - Lesson 1", "link": MCP_COURSE_LINK}]

    def test_search_populates_lesson_link_sources(self, real_store):
        tool = CourseSearchTool(real_store)
        tool.execute(query="vector databases", course_name="Retrieval", lesson_number=1)
        assert tool.last_sources == [{"text": f"{RAG_COURSE} - Lesson 1", "link": f"{RAG_COURSE_LINK}/1"}]

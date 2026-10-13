"""Tests for how RAGSystem handles content-related queries"""
import dataclasses
import os
from pathlib import Path

import pytest

from config import config
from rag_system import RAGSystem

from conftest import (
    RAG_COURSE, RAG_COURSE_LINK, VECTOR_DB_TEXT,
    make_response, text_block, tool_use_block,
)


class FakeMessages:
    """Scripted stand-in for client.messages: searches on the first call, echoes tool results on the second"""

    def __init__(self, tool_input):
        self.tool_input = tool_input
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        last = kwargs["messages"][-1]
        if isinstance(last["content"], str):
            return make_response(
                tool_use_block("search_course_content", self.tool_input, block_id="toolu_rag"),
                stop_reason="tool_use",
            )
        tool_output = "\n".join(block["content"] for block in last["content"])
        return make_response(text_block(f"ANSWER BASED ON:\n{tool_output}"))


class FakeClient:
    def __init__(self, tool_input):
        self.messages = FakeMessages(tool_input)


@pytest.fixture
def make_rag(test_config):
    def _make(tool_input):
        rag = RAGSystem(test_config)
        rag.ai_generator.client = FakeClient(tool_input)
        return rag
    return _make


class TestContentQueries:

    def test_rag_system_uses_real_max_results(self, make_rag):
        rag = make_rag({"query": "x"})
        assert rag.vector_store.max_results == config.MAX_RESULTS

    def test_content_query_returns_course_content(self, make_rag):
        rag = make_rag({"query": "How do vector databases store embeddings?"})
        answer, _ = rag.query("How do vector databases store embeddings?")
        assert "Search error" not in answer, answer
        assert VECTOR_DB_TEXT in answer

    def test_query_is_wrapped_and_tools_offered(self, make_rag):
        rag = make_rag({"query": "vector databases"})
        rag.query("What are vector databases?")
        first_call = rag.ai_generator.client.messages.calls[0]
        assert first_call["messages"][0]["content"] == "Answer this question about course materials: What are vector databases?"
        assert {t["name"] for t in first_call["tools"]} == {"search_course_content", "get_course_outline"}

    def test_content_query_returns_sources_and_resets_them(self, make_rag):
        rag = make_rag({"query": "vector databases", "course_name": "Retrieval", "lesson_number": 1})
        _, sources = rag.query("What does lesson 1 say about vector databases?")
        assert sources == [{"text": f"{RAG_COURSE} - Lesson 1", "link": f"{RAG_COURSE_LINK}/1"}]
        assert rag.tool_manager.get_last_sources() == []

    def test_session_history_is_recorded_and_reused(self, make_rag):
        rag = make_rag({"query": "vector databases"})
        session_id = rag.session_manager.create_session()
        answer, _ = rag.query("What are vector databases?", session_id)

        history = rag.session_manager.get_conversation_history(session_id)
        assert "User: What are vector databases?" in history
        assert f"Assistant: {answer}" in history

        rag.query("Tell me more", session_id)
        second_system = rag.ai_generator.client.messages.calls[-2]["system"]
        assert "User: What are vector databases?" in second_system

    def test_tool_failure_does_not_raise(self, make_rag):
        rag = make_rag({"query": "x"})
        rag.vector_store.search = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("db down"))
        answer, sources = rag.query("What are vector databases?")
        assert isinstance(answer, str)
        assert sources == []


# ---------------------------------------------------------------------------
# Live test: real ChromaDB (backend/chroma_db) + real Anthropic API. Opt-in: uv run pytest -m live
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_live_content_query():
    if not config.ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")
    chroma_path = Path(__file__).resolve().parents[1] / "chroma_db"
    rag = RAGSystem(dataclasses.replace(config, CHROMA_PATH=str(chroma_path)))
    assert rag.vector_store.get_course_count() > 0, "backend/chroma_db is empty; start the app once to index docs/"

    # Record raw tool outputs so a search error can't hide behind Claude's paraphrasing
    tool_outputs = []
    original_execute = rag.tool_manager.execute_tool

    def recording_execute(name, **kwargs):
        out = original_execute(name, **kwargs)
        tool_outputs.append((name, kwargs, out))
        return out

    rag.tool_manager.execute_tool = recording_execute

    answer, sources = rag.query(
        "In the Building Towards Computer Use with Anthropic course, what is prompt caching and why is it useful?"
    )
    print("\nTOOL CALLS:", [(n, k, o[:200]) for n, k, o in tool_outputs])
    print("ANSWER:", answer[:500])
    print("SOURCES:", sources)

    searches = [o for n, _, o in tool_outputs if n == "search_course_content"]
    assert searches, "Claude did not call search_course_content"
    assert not any(o.startswith("Search error") for o in searches), searches
    assert answer.strip()
    assert sources

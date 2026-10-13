"""Shared fixtures and helpers for the backend test suite"""
import dataclasses
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from config import config
from models import Course, Lesson, CourseChunk
from vector_store import VectorStore


RAG_COURSE = "Introduction to Retrieval Augmented Generation"
MCP_COURSE = "Building Agents with MCP"

RAG_COURSE_LINK = "https://example.com/rag"
MCP_COURSE_LINK = "https://example.com/mcp"

VECTOR_DB_TEXT = (
    "Vector databases store embeddings so that semantically similar text can be "
    "retrieved with nearest neighbour search."
)
CHUNKING_TEXT = (
    "Chunking splits long documents into overlapping pieces so each embedding "
    "covers a focused span of text."
)
MCP_SERVER_TEXT = (
    "An MCP server exposes tools and resources to a client over the Model Context "
    "Protocol, so agents can call external systems."
)


# ---------------------------------------------------------------------------
# Sample course data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def sample_courses():
    rag = Course(
        title=RAG_COURSE,
        course_link=RAG_COURSE_LINK,
        instructor="Ada Lovelace",
        lessons=[
            Lesson(lesson_number=0, title="Welcome", lesson_link=f"{RAG_COURSE_LINK}/0"),
            Lesson(lesson_number=1, title="Vector Databases", lesson_link=f"{RAG_COURSE_LINK}/1"),
            Lesson(lesson_number=2, title="Chunking", lesson_link=f"{RAG_COURSE_LINK}/2"),
        ],
    )
    mcp = Course(
        title=MCP_COURSE,
        course_link=MCP_COURSE_LINK,
        instructor="Alan Turing",
        lessons=[Lesson(lesson_number=1, title="MCP Servers", lesson_link=None)],
    )
    return [rag, mcp]


@pytest.fixture(scope="session")
def sample_chunks():
    return [
        CourseChunk(content="Welcome to the course on retrieval augmented generation.",
                    course_title=RAG_COURSE, lesson_number=0, chunk_index=0),
        CourseChunk(content=VECTOR_DB_TEXT, course_title=RAG_COURSE, lesson_number=1, chunk_index=1),
        CourseChunk(content=CHUNKING_TEXT, course_title=RAG_COURSE, lesson_number=2, chunk_index=2),
        CourseChunk(content=MCP_SERVER_TEXT, course_title=MCP_COURSE, lesson_number=1, chunk_index=0),
    ]


@pytest.fixture(scope="session")
def seeded_chroma_path(tmp_path_factory, sample_courses, sample_chunks):
    """A ChromaDB directory seeded once with the sample courses"""
    path = str(tmp_path_factory.mktemp("chroma"))
    store = VectorStore(path, config.EMBEDDING_MODEL, max_results=5)
    for course in sample_courses:
        store.add_course_metadata(course)
    store.add_course_content(sample_chunks)
    return path


@pytest.fixture
def real_store(seeded_chroma_path):
    """Real VectorStore over seeded data, using the app's real MAX_RESULTS setting"""
    return VectorStore(seeded_chroma_path, config.EMBEDDING_MODEL, config.MAX_RESULTS)


@pytest.fixture
def test_config(seeded_chroma_path):
    """The app's real config, pointed at the seeded test database"""
    return dataclasses.replace(config, CHROMA_PATH=seeded_chroma_path, ANTHROPIC_API_KEY="test-key")


@pytest.fixture
def mock_store():
    store = Mock(spec=VectorStore)
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    return store


# ---------------------------------------------------------------------------
# Fake Anthropic responses
# ---------------------------------------------------------------------------

def text_block(text):
    return SimpleNamespace(type="text", text=text)


def thinking_block(thinking="internal reasoning"):
    return SimpleNamespace(type="thinking", thinking=thinking)


def tool_use_block(name, tool_input, block_id="toolu_01"):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def make_response(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# API test app
# ---------------------------------------------------------------------------
# app.py builds a real RAGSystem and mounts ../frontend as static files at
# import time, neither of which works in the test environment. Instead we
# build a test app that mirrors app.py's API endpoints, backed by a mock
# RAGSystem, and serves a stub page at "/" in place of the static mount.

SAMPLE_SOURCES = [
    {"text": f"{RAG_COURSE} - Lesson 1", "link": f"{RAG_COURSE_LINK}/1"},
    {"text": f"{MCP_COURSE} - Lesson 1", "link": None},
]

ROOT_HTML = "<!DOCTYPE html><html><body><h1>Course Materials Assistant</h1></body></html>"


@pytest.fixture
def mock_rag_system():
    """Mock RAGSystem with canned answers, sources, and analytics"""
    rag = Mock()
    rag.session_manager.create_session.return_value = "session_1"
    rag.query.return_value = ("Vector databases store embeddings.", SAMPLE_SOURCES)
    rag.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": [RAG_COURSE, MCP_COURSE],
    }
    return rag


def create_test_app(rag_system):
    """Build a FastAPI app exposing the same API as app.py, without static files"""
    from typing import List, Optional

    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from pydantic import BaseModel

    app = FastAPI(title="Course Materials RAG System (test)")

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class Source(BaseModel):
        text: str
        link: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[Source]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()
            answer, sources = rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        rag_system.session_manager.delete_session(session_id)
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return ROOT_HTML

    return app


@pytest.fixture
def client(mock_rag_system):
    """TestClient for the test app, backed by mock_rag_system"""
    from fastapi.testclient import TestClient

    with TestClient(create_test_app(mock_rag_system)) as test_client:
        yield test_client

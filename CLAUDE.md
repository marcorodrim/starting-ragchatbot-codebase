# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A full-stack RAG chatbot that answers questions about course materials. FastAPI backend + ChromaDB vector store + Anthropic Claude (tool calling), with a vanilla HTML/JS/CSS frontend served by the same FastAPI app.

## Commands

Dependencies are managed with `uv` (Python >= 3.13). On Windows, run shell commands in Git Bash.

```bash
uv sync                                              # install dependencies
cp .env.example .env                                 # then set ANTHROPIC_API_KEY
./run.sh                                             # start the app
cd backend && uv run uvicorn app:app --reload --port 8000   # manual start
```

- **Always use `uv`** — run the server with `uv run` (or `./run.sh`) and manage dependencies with `uv add`/`uv sync`. Never call `pip` directly.
- Web UI: http://localhost:8000 — API docs: http://localhost:8000/docs
- The server **must be started from `backend/`**: `app.py` uses relative paths (`../docs`, `../frontend`) and `config.py` stores ChromaDB at `./chroma_db` (i.e. `backend/chroma_db`).
- There is no test suite, linter, or formatter configured. `main.py` at the root is an unused placeholder.

## Architecture

Backend modules live flat in `backend/` and import each other by bare module name (e.g. `from config import config`), which is why they run with `backend/` as the working directory.

`RAGSystem` (`rag_system.py`) is the orchestrator; `app.py` creates one global instance and exposes `POST /api/query` and `GET /api/courses`.

**Query flow (tool-based RAG, not retrieve-then-generate):**

1. `RAGSystem.query` wraps the user query in a prompt and pulls formatted history from `SessionManager` (in-memory, last `MAX_HISTORY` exchanges, injected into the _system prompt_, not as messages).
2. `AIGenerator.generate_response` calls Claude with the tool definitions from `ToolManager`. Claude decides whether to search.
3. While `stop_reason == "tool_use"`, `_run_tools` executes the tool(s) and Claude is called again _with_ tools, seeing all prior results — up to `MAX_TOOL_ROUNDS` (2) sequential rounds. After the last round (or as soon as a tool raises, which is sent back as an `is_error` tool_result), one final call is made _without_ tools to force a text answer. `ToolManager.execute_tool` lets exceptions propagate; the generator is the single place that handles them.
4. `CourseSearchTool` calls `VectorStore.search`, formats results, and stashes UI source labels in `last_sources`. `RAGSystem` reads them via `ToolManager.get_last_sources()` and then resets them — sources are passed back through this side channel, not through the Claude response.

**Vector store (`vector_store.py`)** has two ChromaDB collections:

- `course_catalog` — one doc per course (title is both document and ID); metadata includes instructor, link, and lessons serialized as `lessons_json`.
- `course_content` — text chunks with `course_title`, `lesson_number`, `chunk_index` metadata; IDs are `{title_with_underscores}_{chunk_index}`.

`search()` first resolves a fuzzy `course_name` to an exact title via semantic search on `course_catalog`, then queries `course_content` with a `where` filter on course and/or lesson.

**Adding a tool:** subclass `Tool` in `search_tools.py` (implement `get_tool_definition` returning an Anthropic tool schema, and `execute`), then register it with `tool_manager.register_tool(...)` in `RAGSystem.__init__`.

## Document ingestion

On startup, `app.py` loads every `.txt`/`.pdf`/`.docx` in `docs/` (all read as plain text, so only `.txt` really works). Courses whose title already exists in ChromaDB are skipped — **edits to an existing course file won't be re-indexed** unless you delete `backend/chroma_db` or call `add_course_folder(..., clear_existing=True)`.

`DocumentProcessor.process_course_document` expects this format:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<lesson content...>
Lesson 1: ...
```

Content is split into sentence-based chunks (`CHUNK_SIZE`=800 chars, `CHUNK_OVERLAP`=100). Note the inconsistent context prefixing: only the first chunk of non-final lessons gets `Lesson N content:`, while every chunk of the final lesson gets `Course <title> Lesson N content:`.

## Configuration

All tunables (model name, embedding model, chunk sizes, `MAX_RESULTS`, `MAX_HISTORY`, Chroma path) are in the `Config` dataclass in `backend/config.py`. The Claude system prompt is `AIGenerator.SYSTEM_PROMPT` in `ai_generator.py`.

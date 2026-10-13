# Frontend Changes

**None.** This feature only added backend test infrastructure. No files under `frontend/` were changed.

For reference, here is what changed:

## API testing infrastructure

- **`backend/tests/conftest.py`**: added shared API fixtures:
  - `mock_rag_system`: a mock `RAGSystem` that returns a canned answer, sources (`SAMPLE_SOURCES`), and course analytics.
  - `create_test_app(rag_system)`: builds a FastAPI app with the same endpoints as `app.py` (`POST /api/query`, `GET /api/courses`, `DELETE /api/session/{id}`) plus a stub HTML page at `/`. This avoids importing `app.py`, which builds a real `RAGSystem` and mounts `../frontend` as static files when it is imported.
  - `client`: a `TestClient` for the test app.
- **`backend/tests/test_api.py`** (new): 19 endpoint tests (marked `api`). They cover:
  - successful responses
  - creating a new session vs. reusing an existing one
  - optional source links and empty sources
  - 422 validation errors
  - 500 error mapping with `detail`
  - 405/404 handling
  - session deletion
  - the root HTML page
- **`pyproject.toml`**:
  - added `httpx` to the dev dependency group (`TestClient` needs it)
  - extended `[tool.pytest.ini_options]` with an `api` marker, `-ra --strict-markers`, and a `filterwarnings` entry that silences DeprecationWarnings

Run them with `uv run pytest` (all tests) or `uv run pytest -m api` (API tests only).

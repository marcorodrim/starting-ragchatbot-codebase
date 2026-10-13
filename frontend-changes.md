# Frontend Changes

This file collects the change notes from each feature branch.

## Code Quality Tooling

### Summary

Added automatic formatting and linting for the frontend (`frontend/index.html`, `frontend/script.js`,
`frontend/style.css`) and dev scripts to run the checks.

The request mentioned **black**, but black only formats Python, and this change is limited to the
frontend. **Prettier** is the frontend equivalent of black: an opinionated formatter with almost no
settings. **ESLint** handles JavaScript correctness checks.

### Tooling added (repo root)

| File | Purpose |
| --- | --- |
| `package.json` / `package-lock.json` | Dev dependencies (`prettier`, `eslint`, `@eslint/js`) and npm scripts |
| `.prettierrc.json` | Prettier settings matching the existing style: 4-space indent, single quotes, semicolons, 100-col width (120 for HTML), LF endings |
| `.prettierignore` | Limits Prettier to the frontend (ignores `backend/`, `docs/`, Markdown, `uv.lock`) |
| `eslint.config.js` | ESLint flat config: `recommended` rules plus `eqeqeq`, `prefer-const`, `no-var`, and `no-unused-vars` as a warning; browser globals and the CDN-loaded `marked` declared |
| `.editorconfig` | Shared editor settings (UTF-8, LF, final newline, trim trailing whitespace, 4-space frontend indent) |
| `.gitignore` | Added `node_modules/` |

The tooling lives at the repo root, not in `frontend/`, because FastAPI serves `frontend/` as static
files. A `frontend/node_modules` folder would be publicly reachable.

### Development scripts

| Command | What it does |
| --- | --- |
| `./scripts/format-frontend.sh` | Installs tools if needed, runs `prettier --write frontend`, then `eslint frontend --fix` |
| `./scripts/check-frontend.sh` | Read-only check: `prettier --check` + `eslint`; exits non-zero on any issue (CI-friendly) |
| `npm run format` / `npm run format:check` | Prettier write / check |
| `npm run lint` / `npm run lint:fix` | ESLint check / autofix |
| `npm run quality` / `npm run quality:fix` | All checks / all fixes |

Run the shell scripts in Git Bash on Windows.

### Formatting applied to the existing frontend

I ran the formatter once over the existing files. Behavior is unchanged; only whitespace and style changed:

- **`script.js`**: removed trailing whitespace and duplicate blank lines, added parentheses to
  single-argument arrow functions (`button => …` → `(button) => …`), added trailing commas in
  multi-line objects/calls, and wrapped long lines.
- **`index.html`**: consistent nested indentation inside `<head>`/`<body>`, self-closing void
  elements (`<meta … />`, `<link … />`), `<!doctype html>`, and long attribute lists wrapped one per
  line.
- **`style.css`**: consistent spacing, multi-selector rules split one selector per line, and long
  values wrapped.

ESLint reports no errors or warnings on the formatted code.

## Backend API Testing

No files under `frontend/` were changed by this feature. For reference, here is what changed:

### API testing infrastructure

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

## Dark/Light Theme Toggle

### Summary
Added a toggle button in the top-right corner that switches between the existing dark theme and a new light theme. Theme switching is driven by CSS custom properties and a `data-theme` attribute on the `<html>` element.

### Files Changed

#### `frontend/index.html`
- Added a `<button id="themeToggle" class="theme-toggle">` at the top of `<body>` with inline sun and moon SVG icons (`aria-hidden`), plus an `aria-label`/`title` describing the action.
- Added a small inline script in `<head>` that applies the saved theme (`localStorage.theme`) before first paint, so the page doesn't flash the wrong theme.
- Bumped the cache-busting versions of `style.css` and `script.js` (`v=11` → `v=12`).

#### `frontend/style.css`
- **New variables** in `:root` (dark defaults): `--code-bg`, `--error-text`, `--success-text`, `--welcome-shadow`, and `color-scheme: dark`.
- **Light theme** block `:root[data-theme="light"]` overriding every color variable:
  - Background `#ffffff`, surface `#f1f5f9`, surface-hover `#e2e8f0`, border `#cbd5e1`
  - Text primary `#0f172a`, text secondary `#475569` (both meet WCAG AA on light backgrounds)
  - Primary `#2563eb` / hover `#1d4ed8` (white text on primary still passes AA)
  - Darker error/success text (`#b91c1c` / `#15803d`) for contrast on light backgrounds
  - Softer shadows and code background
- Replaced hard-coded colors with variables (code/pre background, welcome-message shadow, error and success message text) so they adapt to both themes.
- Fixed the blockquote border, which referenced an undefined `--primary` variable (now `--primary-color`).
- **`.theme-transition` class**: while it is present, background, text, border, and shadow colors animate over 0.3s. JS adds it only during a switch, so existing hover/transform transitions are unaffected the rest of the time.
- **`.theme-toggle` styles**: a fixed, round 40px button in the top-right that uses the surface/border variables and matches the existing hover lift and focus-ring style. A `:focus-visible` ring supports keyboard users.
- Icon animation: the sun shows in dark mode (meaning "switch to light") and the moon shows in light mode. They cross-fade with a rotate and scale effect.
- `prefers-reduced-motion` turns off the toggle and theme transitions.

#### `frontend/script.js`
- Added `themeToggle` to the DOM references and a click listener for it.
- New functions:
  - `getCurrentTheme()`: returns `'light'` or `'dark'` based on `data-theme`.
  - `toggleTheme()`: flips the theme by setting `data-theme="light"` on `<html>` or removing it for dark, applies `.theme-transition` for 300ms, saves the choice to `localStorage`, and updates the button label.
  - `updateThemeToggle()`: keeps `aria-label`/`title` in sync ("Switch to light theme" / "Switch to dark theme").

### Accessibility
- The toggle is a native `<button>`, so it is focusable with Tab and works with Enter and Space.
- Its accessible label describes the action and updates after each toggle.
- It has a visible focus ring (`:focus-visible`).
- Contrast ratios in the light theme meet WCAG AA for body and secondary text.
- Reduced-motion preferences are respected.

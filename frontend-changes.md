# Frontend Changes: Code Quality Tooling

## Summary

Added automatic formatting and linting for the frontend (`frontend/index.html`, `frontend/script.js`,
`frontend/style.css`) and dev scripts to run the checks.

The request mentioned **black**, but black only formats Python, and this change is limited to the
frontend. **Prettier** is the frontend equivalent of black: an opinionated formatter with almost no
settings. **ESLint** handles JavaScript correctness checks.

## Tooling added (repo root)

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

## Development scripts

| Command | What it does |
| --- | --- |
| `./scripts/format-frontend.sh` | Installs tools if needed, runs `prettier --write frontend`, then `eslint frontend --fix` |
| `./scripts/check-frontend.sh` | Read-only check: `prettier --check` + `eslint`; exits non-zero on any issue (CI-friendly) |
| `npm run format` / `npm run format:check` | Prettier write / check |
| `npm run lint` / `npm run lint:fix` | ESLint check / autofix |
| `npm run quality` / `npm run quality:fix` | All checks / all fixes |

Run the shell scripts in Git Bash on Windows.

## Formatting applied to the existing frontend

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

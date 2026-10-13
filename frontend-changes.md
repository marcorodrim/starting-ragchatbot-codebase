# Frontend Changes: Dark/Light Theme Toggle

## Summary
Added a toggle button in the top-right corner that switches between the existing dark theme and a new light theme. Theme switching is driven by CSS custom properties and a `data-theme` attribute on the `<html>` element.

## Files Changed

### `frontend/index.html`
- Added a `<button id="themeToggle" class="theme-toggle">` at the top of `<body>` with inline sun and moon SVG icons (`aria-hidden`), plus an `aria-label`/`title` describing the action.
- Added a small inline script in `<head>` that applies the saved theme (`localStorage.theme`) before first paint, so the page doesn't flash the wrong theme.
- Bumped the cache-busting versions of `style.css` and `script.js` (`v=11` → `v=12`).

### `frontend/style.css`
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

### `frontend/script.js`
- Added `themeToggle` to the DOM references and a click listener for it.
- New functions:
  - `getCurrentTheme()`: returns `'light'` or `'dark'` based on `data-theme`.
  - `toggleTheme()`: flips the theme by setting `data-theme="light"` on `<html>` or removing it for dark, applies `.theme-transition` for 300ms, saves the choice to `localStorage`, and updates the button label.
  - `updateThemeToggle()`: keeps `aria-label`/`title` in sync ("Switch to light theme" / "Switch to dark theme").

## Accessibility
- The toggle is a native `<button>`, so it is focusable with Tab and works with Enter and Space.
- Its accessible label describes the action and updates after each toggle.
- It has a visible focus ring (`:focus-visible`).
- Contrast ratios in the light theme meet WCAG AA for body and secondary text.
- Reduced-motion preferences are respected.

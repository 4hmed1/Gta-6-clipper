# UI Recovery Root Cause Analysis (Step 1)

## Executive Summary
The web UI disappeared because during recent sprint refactoring (introducing new backend modules `clipforge/ingest`, `clipforge/resilience`, and `clipforge/security`), the project structure evolved toward a package CLI layout (`clipforge/cli.py`) but the FastAPI server (`app/main.py`) relied on `static/` files from the project root (`BASE_DIR / "static"`). Furthermore, when starting the app from different working directories or via the `clipforge` entry point, relative path resolution failed or templates/static files were not packaged or correctly mounted.

Additionally, multiple competing UI directories (`static/` vs `web/`) were created during sprint changes without unified static asset mounting or building.

## Detailed Root Cause Analysis

1. **Static Directory Path Resolution**:
   - `app/main.py` uses `STATIC_DIR = BASE_DIR / "static"` where `BASE_DIR` is `Path(__file__).resolve().parent.parent`.
   - When running via `clipforge` CLI command or from external working directories, static files were either not found or path resolution defaulted incorrectly.

2. **Divergent UI Assets**:
   - Original static frontend (`static/index.html`, `static/js/app.js`, `static/css/style.css`) is fully intact in the project root.
   - Another directory `web/` was added with Vue/HTML components, creating confusion over which frontend bundle is active.
   - The primary functional UI (`static/index.html` + `app.js` + `style.css`) is robust, featuring the full Studio workspace, YouTube/upload tabs, agent swarm visualizer, progress tracker, clips library, and editor modal.

3. **Package Distribution & Entry Point**:
   - `pyproject.toml` did not explicitly include static and template assets in setuptools package data (`[tool.setuptools.package-data]`), meaning when installed as a Python package, the UI assets were omitted from site-packages.
   - The `clipforge` CLI did not have a robust server runner function that guarantees static asset mounting relative to package installation path (`importlib.resources` or `Path(__file__)`).

## Corrective Action Plan (Steps 2-5)
1. **Restore & Consolidate**: Ensure `app/main.py` robustly serves the primary frontend from `static/` using absolute package-relative paths (`Path(__file__).parent.parent / "static"`).
2. **Package Data**: Update `pyproject.toml` to include static assets in `package-data`.
3. **Robust CLI**: Update `clipforge` launcher in `clipforge/cli.py` to serve the web UI reliably on port 3000, auto-open browser, and include robust doctor checks for UI assets.
4. **Testing & Verification**: Add automated pytest and Playwright UI tests verifying `/` returns the UI and all key screens function correctly.

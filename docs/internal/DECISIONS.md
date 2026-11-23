# MaxClipper Architecture Decisions & Decision Log (DECISIONS.md)

## ADR-001: Open Source License
- **Decision**: MIT License.
- **Rationale**: Simple, permissive open-source license that encourages community contributions while allowing open-core commercial extensions in `pro/`.

## ADR-002: Deterministic Selection Architecture
- **Decision**: Zero mandatory LLM or paid API dependencies for clip selection.
- **Rationale**: Clip selection uses deterministic DSP (energy variance, spectral flux, pitch contour, dead-air map), classic NLP (TextRank/TF-IDF, sentence boundaries, hook pattern scoring), and classical computer vision (OpenCV face cascade + optical flow motion saliency). YouTube json3 captions provide word-level timing by default; offline Whisper is optional and opt-in only.

## ADR-003: Package Structure & Monorepo Layout
- **Decision**: Monorepo with `maxclipper/` (Python package + backend + resilience + algorithms), `web/` (React/TS frontend source, bundled into `maxclipper/static`), `installers/` (`install.ps1`, `install.sh`), `config/` (YAML scoring presets & hook rules), `tests/` (Pytest unit/chaos/golden/e2e), `docs/`.
- **Rationale**: Meets Section 5 requirements while retaining clean module isolation and single-command wheel installation (`pip install .` or `uv pip install .`).

## ADR-004: Editor & Exporter Synchronization
- **Decision**: Single `ProjectJSON` format representing timeline state. Editor preview renders `ProjectJSON` via HTML5 Video + Canvas/DOM overlay; `maxclipper.editor.compiler` converts the exact same `ProjectJSON` into a single, deterministic FFmpeg filtergraph.
- **Rationale**: Eliminates drift between preview and final export; validated via automated golden tests.

## ADR-005: Self-Healing & Resilience First Design
- **Decision**: All heavy processing is state-machine checkpointed in SQLite/JSON cache. Every error is classified with an automated fallback ladder before raising to user.
- **Rationale**: Meets headline product promise of auto-healing on weak or unreliable machines.

## ADR-06: Design System Source of Truth
- **Decision**: `docs/DESIGN_SYSTEM.md` is the single source of truth for all visual tokens (colors, type scale, spacing, radius, shadows, motion). CSS is generated from these tokens.
- **Rationale**: Enables consistent dark/light theme switching and easy brand updates without touching component code.

## ADR-07: App-Style UI Over Marketing Landing Page
- **Decision**: Replace the marketing landing page with a sticky app bar + tabbed app shell (Create / Library / Settings). Max content width 760px, responsive down to 360px, 44px touch targets, WCAG AA contrast.
- **Rationale**: The product is a desktop app, not a website. App-style navigation (tabs, status chips) is the correct mental model for a clipping studio.

## ADR-08: Open-License Fonts Only
- **Decision**: Inter (UI), Archivo Black (display), Anton, Bebas Neue, Bangers, Poppins (caption styles). All from Google Fonts with open licenses (OFL / Apache).
- **Rationale**: Section 2 hard constraint — no proprietary font licensing issues for users.

## ADR-09: Backend Settings Payload Shape
- **Decision**: The Create screen POSTs a single JSON payload: `{source, clip_count, length_min, length_max, aspect, caption_style, framing, hook_text, tighten_pauses, focus_text, range_start, range_end}`. Time inputs are parsed server-side from `mm:ss` or `h:mm:ss` strings.
- **Rationale**: One clean shape keeps the frontend and backend in sync; server-side parsing gives honest error messages for malformed input.

## ADR-10: Settings Persistence via localStorage
- **Decision**: User preferences (clip count, length, aspect, caption style, framing, toggles, focus text) are saved to `localStorage` under `maxclipper_settings` and restored on page load. Quality overrides are also persisted.
- **Rationale**: The wizard's "every question can be skipped" requirement means defaults must remember the user's last choice without a backend round-trip.

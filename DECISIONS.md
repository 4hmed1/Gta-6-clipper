# ClipForge Architecture Decisions & Decision Log (DECISIONS.md)

## ADR-001: Open Source License
- **Decision**: MIT License.
- **Rationale**: Simple, permissive open-source license that encourages community contributions while allowing open-core commercial extensions in `pro/`.

## ADR-002: Deterministic Selection Architecture
- **Decision**: Zero mandatory LLM or paid API dependencies for clip selection.
- **Rationale**: Clip selection uses deterministic DSP (energy variance, spectral flux, pitch contour, dead-air map), classic NLP (TextRank/TF-IDF, sentence boundaries, hook pattern scoring), and classical computer vision (OpenCV face cascade + optical flow motion saliency). YouTube json3 captions provide word-level timing by default; offline Whisper is optional and opt-in only.

## ADR-003: Package Structure & Monorepo Layout
- **Decision**: Monorepo with `clipforge/` (Python package + backend + resilience + algorithms), `web/` (React/TS frontend source, bundled into `clipforge/static`), `installers/` (`install.ps1`, `install.sh`), `config/` (YAML scoring presets & hook rules), `tests/` (Pytest unit/chaos/golden/e2e), `docs/`.
- **Rationale**: Meets Section 5 requirements while retaining clean module isolation and single-command wheel installation (`pip install .` or `uv pip install .`).

## ADR-004: Editor & Exporter Synchronization
- **Decision**: Single `ProjectJSON` format representing timeline state. Editor preview renders `ProjectJSON` via HTML5 Video + Canvas/DOM overlay; `clipforge.editor.compiler` converts the exact same `ProjectJSON` into a single, deterministic FFmpeg filtergraph.
- **Rationale**: Eliminates drift between preview and final export; validated via automated golden tests.

## ADR-005: Self-Healing & Resilience First Design
- **Decision**: All heavy processing is state-machine checkpointed in SQLite/JSON cache. Every error is classified with an automated fallback ladder before raising to user.
- **Rationale**: Meets headline product promise of auto-healing on weak or unreliable machines.

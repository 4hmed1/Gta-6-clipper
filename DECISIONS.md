# DECISIONS.md - ClipForge Project Decisions

## Key Decisions Made During Development

### 1. Package Structure
- **Decision**: Move `static/`, `config/`, `templates/` directories into `app/` package
- **Rationale**: Ensures proper package data inclusion via pyproject.toml `[tool.setuptools.package-data]`
- **Status**: Completed - pyproject.toml updated, MANIFEST.in updated

### 2. Path Handling Fix
- **Decision**: Wrap `platformdirs.user_data_dir()` result with `Path()` in cli.py
- **Rationale**: Fixed `TypeError: unsupported operand type(s) for /: 'str' and 'str'` in captions-debug command
- **Status**: Completed - Line 340 in clipforge/cli.py updated

### 3. Port Unification
- **Decision**: Use port 3000 as default across all components
- **Components**: cli.py, install.sh, install.ps1, README.md, app/main.py
- **Rationale**: Consistent user experience, avoids confusion
- **Status**: In progress - verify all references use port 3000

### 4. Server Bind Address
- **Decision**: Changed from `0.0.0.0` to `127.0.0.1` for local development
- **Rationale**: More predictable localhost behavior, aligns with curl tests
- **Status**: Completed - app/main.py updated

### 5. CLI Flags
- **Decision**: Add `--port` and `--no-browser` flags to clipforge command
- **Rationale**: User flexibility for custom ports and headless operation
- **Status**: Completed - cli.py updated

### 6. Install Script
- **Decision**: Complete rewrite of installers/install.sh with proper shebang, uv-aware install, venv creation
- **Rationale**: One-command install must work flawlessly on all platforms
- **Status**: Completed - install.sh rewritten

### 7. Package Data Configuration
- **Decision**: Configure pyproject.toml `[tool.setuptools.package-data]` for app/static/, app/config/, app/templates/
- **Rationale**: Prevent `RuntimeError: Directory '.../site-packages/static' does not exist`
- **Status**: Completed - pyproject.toml and MANIFEST.in updated

### 8. API Endpoint
- **Decision**: Ensure `/api/status/{task_id}` GET endpoint returns full task state
- **Rationale**: captions-debug command needs task data including transcript_words, status, meta
- **Status**: Completed - app/main.py get_task_status() function verified working

### 9. Package Installation
- **Decision**: Install into isolated venv using system Python 3.11+, no global pollution
- **Rationale**: Clean separation, easy uninstall, no system Python breakage
- **Status**: Completed - verified with /home/max/.gta6-clipper/venv

### 10. Offline-First Design
- **Decision**: No LLM, no paid API, no cloud AI in core clip selection
- **Rationale**: Free, unlimited, no watermark, private - everything runs locally
- **Status**: Core design principle confirmed throughout development
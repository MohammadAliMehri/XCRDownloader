# Development Guide

## Prerequisites

- Python 3.10+
- FFmpeg (for video/audio processing)
- Git
- (Optional) Docker and Docker Compose

## Setting Up a Development Environment

```bash
# Clone the repository
git clone https://github.com/MohammadAliMehri/XCRDownloader.git
cd XCRDownloader

# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in editable mode (for development)
pip install -e .
```

## Project Structure

See [Architecture](ARCHITECTURE.md) for a detailed component breakdown.

```
XCRDownloader/
├── src/                  # Main source code
│   ├── api/              # API blueprints
│   ├── anime/            # Anime providers
│   ├── network/          # Shared HTTP client
│   ├── services/         # Job manager, logging, config
│   ├── platforms/        # Downloader providers
│   ├── utils/            # Helpers
│   ├── relay.py          # Media relay
│   ├── engine.py         # Download engine
│   ├── search.py         # Music search
│   ├── web.py            # Flask app factory
│   ├── config.py         # Configuration
│   └── logging.py        # Logging setup
├── tests/                # Unit tests
├── static/               # Frontend assets
├── templates/            # HTML templates
├── cli.py                # CLI entry point
├── app.py                # WSGI entry point
├── pyproject.toml        # Packaging
├── requirements.txt      # Dependencies
├── Dockerfile            # Docker build
├── docker-compose.yml    # Compose definition
├── .env.example          # Environment template
└── downloads/            # Download directory (gitignored)
```

## Development Workflow

### Running the Web UI in Development

```bash
# Using cli.py (auto‑opens browser)
python cli.py --web

# Or run the Flask app directly
python -m src.web

# With custom host/port
python cli.py --web --host 127.0.0.1 --port 8080
```

### Running the CLI

```bash
# Download a URL
python cli.py https://www.youtube.com/watch?v=abc

# With audio extraction
python cli.py --audio https://www.youtube.com/watch?v=abc

# Search music
python cli.py --search "Eminem Lose Yourself"

# Batch download
python cli.py -u URL1 -u URL2 -u URL3
```

### Running Tests

```bash
# Install dev dependencies (pytest)
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run a specific test
pytest tests/test_security.py -k test_host_allowlist
```

### Code Quality

```bash
# Install linting tools
pip install ruff mypy

# Run ruff
ruff check .

# Run mypy
mypy src/ --ignore-missing-imports
```

## Adding a New Platform Provider

1. Create a new file in `src/platforms/` (e.g., `newplatform.py`).
2. Subclass `BaseDownloader`:

```python
from .base import BaseDownloader

class NewPlatformDownloader(BaseDownloader):
    def download(self, url: str, quality: str = "best", **kwargs) -> dict:
        # Custom logic or call self._ytdlp_download()
        return self._ytdlp_download(url, self._make_opts(...))
```

3. Register it in `src/engine.py` under `_downloader_classes`.

## Adding a New Anime Provider

1. Create a new file in `src/anime/` (e.g., `provider.py`).
2. Subclass `AnimeProvider`:

```python
from .base import AnimeProvider

class MyProvider(AnimeProvider):
    name = "myprovider"

    def search(self, query: str, page: int = 1) -> list:
        # Return list of results with keys: id, provider, title, url, cover, etc.
        pass

    def episodes(self, anime_id=None, page_url=None):
        # Return dict with 'success', 'episodes' list, optional 'info'
        pass

    def stream(self, anime_id=None, episode=1, dub=False, page_url=None, episode_url=None):
        # Return dict with 'success', 'stream_url', 'subtitles', 'referer', or 'player_url'/'embed_only'
        pass

    @property
    def supports_dub(self) -> bool:
        return False
```

3. Register it in `src/anime/__init__.py`:

```python
from .myprovider import MyProvider
registry.register(MyProvider())
```

## Adding a New API Route

1. Determine which blueprint it belongs to (download, search, anime).
2. Add the route function in the appropriate file in `src/api/`.
3. Use `error_response()` for consistent error formatting.
4. Access engine/job_manager via `current_app.config['engine']` and `current_app.config['job_manager']`.
5. Update frontend `app.js` to call the new endpoint.

## Modifying the Media Relay

1. Most relay logic is in `src/relay.py`.
2. Key functions:
   - `_media_url_allowed()`: validation.
   - `_safe_fetch_url()`: fetch with redirect validation.
   - `_rewrite_playlist()`: playlist rewriting.
   - `_strip_wrapper_stream()`: de‑wrapping.
3. Add new hosts to the allow‑list via `_ALLOWED_RELAY_HOSTS` (or environment).

## Configuration for Development

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

Set `XCR_DEBUG=true` for verbose logging and auto‑reload (if enabled).

## Docker Development

```bash
# Build the image
docker build -t xcrdownloader .

# Run with compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Debugging Tips

- **Logging**: Set `XCR_LOG_LEVEL=DEBUG` to see detailed logs.
- **Frontend**: Use browser DevTools (F12) to inspect network requests and console errors.
- **API tests**: Use `curl` or Postman to test endpoints directly.
- **SSRF issues**: Check `_media_url_allowed()` and the allow‑lists.
- **Anime issues**: Verify the provider allow‑lists in `src/config.py` `anime_allowed_hosts`.

## Common Pitfalls

- **Windows UTF‑8**: `cli.py` automatically reconfigures stdout, but if you see encoding errors, run `python -X utf8 cli.py`.
- **FFmpeg not found**: Ensure FFmpeg is on PATH or set `ffmpeg_location` in config.
- **YouTube 403**: Ensure `curl_cffi` is installed; the client rotation should handle it.
- **Docker port conflict**: Change `XCR_SERVER_PORT` or map a different host port.

## Contributing Guidelines

- Fork the repo and create a feature branch.
- Write tests for new functionality.
- Run `pytest` and `ruff check` before committing.
- Keep commit messages clear and concise.
- Update documentation (this file, README, ARCHITECTURE, SECURITY) as needed.
- Submit a pull request.

## License

MIT — see [LICENSE](../LICENSE).

---
Last updated: 2026-08-17 for v1.8.0
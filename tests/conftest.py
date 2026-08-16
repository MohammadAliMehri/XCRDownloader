import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.web import _media_url_allowed, _safe_fetch_url, _strip_wrapper_stream, _is_allowed_relay_host
# Import from src.anime now exports these for backward compatibility
from src.anime import _is_allowed_anime_host, _ALLOWED_ANIME_HOSTS

@pytest.fixture
def allowed_relay_hosts():
    from src.web import _ALLOWED_RELAY_HOSTS
    return _ALLOWED_RELAY_HOSTS

@pytest.fixture
def allowed_anime_hosts():
    return _ALLOWED_ANIME_HOSTS
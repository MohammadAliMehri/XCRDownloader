"""Anime API routes."""
from flask import Blueprint, request, jsonify, current_app
from src.anime import search_anime, get_anime_episodes, get_anime_stream
from src.anime._shared import PROVIDER_LABELS
from src.config import config
import re
from urllib.parse import quote
import requests
from flask import Response, stream_with_context

# Import relay helpers from web.py (temporary)
# We'll move these to a shared module later.
from src.relay import (
    _media_url_allowed,
    _safe_fetch_url,
    _media_fetch_url,
    _rewrite_playlist,
    _strip_wrapper_stream,
    _MEDIA_UA,
    _STRIP_BYTES,
    _relay_url,
)

anime_bp = Blueprint('anime', __name__, url_prefix='/api/anime')

def error_response(message, status=400, code=None):
    return jsonify({"success": False, "error": {"code": code or "error", "message": message}}), status

@anime_bp.route('/search')
def api_anime_search():
    q = request.args.get('q', '').strip()
    provider = request.args.get('provider', 'all').strip().lower() or 'all'
    page = max(1, int(request.args.get('page', 1)))
    if not q:
        return error_response('Empty search query', 400)
    try:
        return jsonify(search_anime(q, provider=provider, page=page))
    except Exception as e:
        return error_response(str(e)[:200], 500)

@anime_bp.route('/episodes')
def api_anime_episodes():
    provider = (request.args.get('provider', 'yomi') or 'yomi').strip().lower()
    anime_id = request.args.get('anime_id', type=int)
    page_url = request.args.get('page_url', '').strip() or None
    try:
        return jsonify(get_anime_episodes(provider, anime_id=anime_id, page_url=page_url))
    except Exception as e:
        return error_response(str(e)[:200], 500)

@anime_bp.route('/stream', methods=['POST'])
def api_anime_stream():
    data = request.get_json(force=True)
    provider = (data.get('provider') or 'yomi').strip().lower()
    raw_id = data.get('anime_id')
    try:
        anime_id = int(raw_id) if raw_id not in (None, '') else None
    except (TypeError, ValueError):
        anime_id = None
    episode = int(data.get('episode', 1) or 1)
    dub = bool(data.get('dub', False))
    page_url = (data.get('page_url') or '').strip() or None
    episode_url = (data.get('episode_url') or '').strip() or None

    result = get_anime_stream(
        provider, anime_id=anime_id, episode=episode, dub=dub,
        page_url=page_url, episode_url=episode_url,
    )
    # Mint relay URLs for direct media
    if result.get('success') and result.get('stream_url') and not result.get('embed_only'):
        referer = result.get('referer') or ''
        result['stream_url'] = _relay_url(result['stream_url'], referer)
        for track in result.get('subtitles') or []:
            if track.get('file'):
                track['file'] = _relay_url(track['file'], referer)
    return jsonify(result)

@anime_bp.route('/media')
def api_anime_media():
    """Media relay: fetch upstream media with required Referer and redirect validation."""
    url = request.args.get('url', '')
    referer = request.args.get('ref', '')
    if not _media_url_allowed(url):
        return error_response('Blocked media URL', 400)
    headers = {'User-Agent': _MEDIA_UA}
    if referer.startswith('http'):
        headers['Referer'] = referer
    fetch_url, strip = _media_fetch_url(url)

    try:
        upstream = _safe_fetch_url(fetch_url, headers, timeout=30)
    except ValueError as e:
        return error_response(str(e)[:160], 400)
    except Exception as e:
        return error_response(str(e)[:160], 502)

    ctype = upstream.headers.get('Content-Type', '')
    is_playlist = (
        'mpegurl' in ctype.lower()
        or 'm3u8' in ctype.lower()
        or '.m3u8' in fetch_url.lower()
    )
    if is_playlist:
        try:
            text = upstream.text
        except Exception:
            text = upstream.content.decode('utf-8', 'replace')
        body = _rewrite_playlist(text, fetch_url, referer)
        upstream.close()
        resp = Response(body, status=upstream.status_code,
                        content_type='application/vnd.apple.mpegurl')
    elif strip:
        def _stripped():
            try:
                yield from _strip_wrapper_stream(upstream, _STRIP_BYTES)
            finally:
                upstream.close()
        resp = Response(stream_with_context(_stripped()),
                        status=upstream.status_code,
                        content_type='video/mp2t')
    else:
        def _stream():
            try:
                yield from upstream.iter_content(chunk_size=65536)
            finally:
                upstream.close()
        resp = Response(stream_with_context(_stream()),
                        status=upstream.status_code,
                        content_type=ctype or 'application/octet-stream')
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-store'
    return resp
"""Search and streaming API routes."""
from flask import Blueprint, request, jsonify, current_app
from src.search import search_music, get_stream_url
from src.utils.helpers import is_public_http_url

search_bp = Blueprint('search', __name__, url_prefix='/api')


def error_response(message, status=400, code=None):
    return jsonify({"success": False, "error": {"code": code or "error", "message": message}}), status


@search_bp.route('/search')
def api_search():
    q = request.args.get('q', '').strip()
    provider = request.args.get('provider', 'all').strip().lower()
    page = int(request.args.get('page', 0))
    if not q or len(q) > 200:
        return error_response('Provide a search query up to 200 characters', 400)
    try:
        result = search_music(q, page, provider=provider)
        return jsonify(result)
    except Exception as e:
        return error_response(str(e)[:200], 500)


@search_bp.route('/stream', methods=['POST'])
def api_stream():
    data = request.get_json(silent=True) or {}
    source_url = data.get('source_url', '').strip()
    want_video = bool(data.get('want_video', False))
    title = data.get('title', '').strip()
    artist = data.get('artist', '').strip()
    if not is_public_http_url(source_url):
        return error_response('Provide a public HTTP(S) source URL', 400)

    result = get_stream_url(
        source_url, want_video=want_video, title=title, artist=artist)
    return jsonify(result)

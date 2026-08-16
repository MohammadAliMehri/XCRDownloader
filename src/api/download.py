"""Downloader API routes."""
import threading
from flask import Blueprint, request, jsonify, current_app
from src.utils.helpers import detect_platform
from src.config import config
from src.logging import get_logger

logger = get_logger(__name__)

download_bp = Blueprint('download', __name__, url_prefix='/api')

def error_response(message, status=400, code=None):
    return jsonify({"success": False, "error": {"code": code or "error", "message": message}}), status

@download_bp.route('/detect', methods=['POST'])
def api_detect():
    data = request.get_json(force=True)
    url = data.get('url', '').strip()
    if not url:
        return error_response('No URL provided', 400)
    engine = current_app.config['engine']
    result = engine.detect(url)
    return jsonify(result)

@download_bp.route('/preview', methods=['POST'])
def api_preview():
    data = request.get_json(force=True)
    url = data.get('url', '').strip()
    if not url:
        return error_response('No URL provided', 400)
    engine = current_app.config['engine']
    result = engine.get_info(url)
    out = {
        'success': result.get('success', False),
        'platform': result.get('platform', 'generic'),
        'url': url,
        'error': result.get('error'),
    }
    preview = result.get('preview', {})
    if preview:
        out['preview'] = preview
    elif result.get('success'):
        info = result.get('info', {})
        if isinstance(info, dict):
            out['preview'] = {
                'title': info.get('title', 'Unknown'),
                'uploader': info.get('uploader') or info.get('channel', 'Unknown'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail') or (
                    info.get('thumbnails', [{}])[-1].get('url') if info.get('thumbnails') else None
                ),
                'view_count': info.get('view_count'),
            }
    return jsonify(out)

@download_bp.route('/info', methods=['POST'])
def api_info():
    data = request.get_json(force=True)
    url = data.get('url', '').strip()
    if not url:
        return error_response('No URL provided', 400)
    engine = current_app.config['engine']
    result = engine.get_info(url)
    return jsonify(result)

@download_bp.route('/download', methods=['POST'])
def api_download():
    data = request.get_json(force=True)
    url = data.get('url', '').strip()
    quality = data.get('quality', 'best')
    audio_only = data.get('audio_only', False)
    if not url:
        return error_response('No URL provided', 400)

    job_manager = current_app.config['job_manager']
    engine = current_app.config['engine']
    job_data = {
        'url': url,
        'platform': detect_platform(url),
        'quality': quality,
        'result': None,
    }
    job_id = job_manager.create_job(job_data)

    def _run():
        job_manager.update_job(job_id, status='downloading')
        try:
            kwargs = {}
            if audio_only:
                kwargs['audio_only'] = True
            result = engine.download(url, quality=quality, **kwargs)
            status = 'completed' if result.get('success') else 'failed'
            job_manager.update_job(job_id, result=result, status=status)
            logger.info(f"Download job {job_id} finished with status {status} for {url}")
        except Exception as e:
            logger.error(f"Download job {job_id} failed for {url}: {e}")
            job_manager.update_job(job_id, result={'success': False, 'error': str(e)}, status='failed')

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({'job_id': job_id, 'status': 'pending'})

@download_bp.route('/batch', methods=['POST'])
def api_batch():
    data = request.get_json(force=True)
    urls = data.get('urls', [])
    quality = data.get('quality', 'best')
    audio_only = data.get('audio_only', False)
    if not urls:
        return error_response('No URLs provided', 400)

    job_manager = current_app.config['job_manager']
    engine = current_app.config['engine']
    job_data = {
        'urls': urls,
        'count': len(urls),
        'quality': quality,
        'results': [],
    }
    job_id = job_manager.create_job(job_data)

    def _run():
        job_manager.update_job(job_id, status='downloading')
        try:
            kwargs = {}
            if audio_only:
                kwargs['audio_only'] = True
            results = engine.download_batch(urls, quality=quality, **kwargs)
            job_manager.update_job(job_id, results=results, status='completed')
        except Exception as e:
            job_manager.update_job(job_id, results=[{'success': False, 'error': str(e)}], status='failed')

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({'job_id': job_id, 'status': 'pending'})

@download_bp.route('/job/<job_id>')
def api_job_status(job_id):
    job_manager = current_app.config['job_manager']
    job = job_manager.get_job(job_id)
    if not job:
        return error_response('Job not found', 404)
    return jsonify(job)

@download_bp.route('/history')
def api_history():
    job_manager = current_app.config['job_manager']
    jobs = job_manager.list_jobs(limit=50)
    return jsonify({'jobs': jobs})

@download_bp.route('/stats')
def api_stats():
    job_manager = current_app.config['job_manager']
    jobs = job_manager.list_jobs(limit=1000)
    total = len(jobs)
    completed = sum(1 for j in jobs if j.get('status') == 'completed')
    failed = sum(1 for j in jobs if j.get('status') == 'failed')
    platforms = {}
    for j in jobs:
        p = j.get('platform', 'unknown')
        platforms[p] = platforms.get(p, 0) + 1
    return jsonify({
        'total_jobs': total,
        'completed': completed,
        'failed': failed,
        'platforms': platforms,
    })

@download_bp.route('/download-track', methods=['POST'])
def api_download_track():
    data = request.get_json(force=True)
    source_url = data.get('source_url', '').strip()
    title = data.get('title', 'Unknown')
    artist = data.get('artist', '')
    if not source_url:
        return error_response('No source URL provided', 400)

    from src.search import resolve_for_download
    download_url = resolve_for_download(source_url)
    job_manager = current_app.config['job_manager']
    engine = current_app.config['engine']
    job_data = {
        'url': download_url,
        'platform': detect_platform(download_url),
        'quality': 'best',
        'result': None,
        'track_title': title,
        'track_artist': artist,
    }
    job_id = job_manager.create_job(job_data)

    def _run():
        job_manager.update_job(job_id, status='downloading')
        try:
            result = engine.download(download_url, quality='best', audio_only=True)
            status = 'completed' if result.get('success') else 'failed'
            job_manager.update_job(job_id, result=result, status=status)
        except Exception as e:
            job_manager.update_job(job_id, result={'success': False, 'error': str(e)}, status='failed')

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return jsonify({'job_id': job_id, 'status': 'pending'})
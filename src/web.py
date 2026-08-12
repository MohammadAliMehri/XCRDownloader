"""XCRDownloader Web UI — Flask application with modern dark interface."""
import ipaddress
import os
import re
import socket
import sys
import json
import threading
import uuid
import time
from datetime import datetime
from urllib.parse import quote, urljoin, urlparse
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.engine import DownloaderEngine
from src.search import search_music, get_stream_url, resolve_for_download
from src.utils.helpers import detect_platform
from src import anime as anime_providers

import requests

_MEDIA_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

# MegaPlay stores segments on TikTok's ad CDN wrapped in a 252-byte header.
# They must be fetched through the player's proxy host and de-wrapped.
_STRIP_HOSTS = ("tiktokcdn.com", "ibyteimg.com", "ipstatp.com", "yoot.trycloud.pro")
_STRIP_BYTES = 252
_TIKTOK_PROXY_HOST = "yoot.trycloud.pro"


def _media_fetch_url(url: str) -> tuple[str, bool]:
    """Return (fetch_url, strip_first_bytes) for an upstream media URL."""
    host = urlparse(url).hostname or ""
    if any(h in host for h in _STRIP_HOSTS):
        parsed = urlparse(url)
        proxy = f"https://{_TIKTOK_PROXY_HOST}{parsed.path}"
        if parsed.query:
            proxy += "?" + parsed.query
        proxy += ("&" if "?" in proxy else "?") + f"domain={host}"
        return proxy, True
    return url, False


def _media_url_allowed(url: str) -> bool:
    """Reject non-http and private/loopback hosts (SSRF guard for the relay)."""
    if not url.startswith(("http://", "https://")):
        return False
    try:
        host = urlparse(url).hostname or ""
        ip = socket.gethostbyname(host)
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved)
    except Exception:
        return False


def _relay_url(url: str, referer: str) -> str:
    return f"/api/anime/media?url={quote(url, safe='')}&ref={quote(referer, safe='')}"


def _rewrite_playlist(text: str, base_url: str, referer: str) -> str:
    """Rewrite every URI in an HLS playlist to go through the local relay."""
    base = base_url.rsplit("/", 1)[0] + "/"
    out = []

    def relay(u: str) -> str:
        abs_url = u if u.startswith("http") else urljoin(base, u)
        return _relay_url(abs_url, referer)

    def fix_tag(match: re.Match) -> str:
        return f'URI="{relay(match.group(1))}"'

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            out.append(re.sub(r'URI="([^"]+)"', fix_tag, line))
        else:
            out.append(relay(line))
    return "\n".join(out) + "\n"


def create_app(output_dir="downloads"):
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
    )
    CORS(app)
    app.config["OUTPUT_DIR"] = output_dir
    engine = DownloaderEngine(output_dir=output_dir)

    # In-memory job tracking
    jobs = {}

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/detect", methods=["POST"])
    def api_detect():
        """Detect platform from URL."""
        data = request.get_json(force=True)
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        result = engine.detect(url)
        return jsonify(result)

    @app.route("/api/preview", methods=["POST"])
    def api_preview():
        """Auto-preview: get metadata + thumbnail for a URL."""
        data = request.get_json(force=True)
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        result = engine.get_info(url)
        # Flatten preview data for the frontend
        out = {
            "success": result.get("success", False),
            "platform": result.get("platform", "generic"),
            "url": url,
            "error": result.get("error"),
        }
        preview = result.get("preview", {})
        if preview:
            out["preview"] = preview
        elif result.get("success"):
            info = result.get("info", {})
            if isinstance(info, dict):
                out["preview"] = {
                    "title": info.get("title", "Unknown"),
                    "uploader": info.get("uploader") or info.get("channel", "Unknown"),
                    "duration": info.get("duration"),
                    "thumbnail": info.get("thumbnail") or (
                        info.get("thumbnails", [{}])[-1].get("url") if info.get("thumbnails") else None
                    ),
                    "view_count": info.get("view_count"),
                }
        return jsonify(out)

    @app.route("/api/info", methods=["POST"])
    def api_info():
        """Get info about a URL without downloading."""
        data = request.get_json(force=True)
        url = data.get("url", "").strip()
        if not url:
            return jsonify({"error": "No URL provided"}), 400
        result = engine.get_info(url)
        return jsonify(result)

    @app.route("/api/download", methods=["POST"])
    def api_download():
        """Start an async download job."""
        data = request.get_json(force=True)
        url = data.get("url", "").strip()
        quality = data.get("quality", "best")
        audio_only = data.get("audio_only", False)

        if not url:
            return jsonify({"error": "No URL provided"}), 400

        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "url": url,
            "platform": detect_platform(url),
            "quality": quality,
            "result": None,
            "created_at": datetime.now().isoformat(),
        }

        def _run():
            jobs[job_id]["status"] = "downloading"
            try:
                kwargs = {}
                if audio_only:
                    kwargs["audio_only"] = True
                result = engine.download(url, quality=quality, **kwargs)
                jobs[job_id]["result"] = result
                jobs[job_id]["status"] = "completed" if result.get("success") else "failed"
            except Exception as e:
                jobs[job_id]["result"] = {"success": False, "error": str(e)}
                jobs[job_id]["status"] = "failed"

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return jsonify({"job_id": job_id, "status": "pending"})

    @app.route("/api/batch", methods=["POST"])
    def api_batch():
        """Start a batch download job."""
        data = request.get_json(force=True)
        urls = data.get("urls", [])
        quality = data.get("quality", "best")
        audio_only = data.get("audio_only", False)

        if not urls:
            return jsonify({"error": "No URLs provided"}), 400

        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "urls": urls,
            "count": len(urls),
            "quality": quality,
            "results": [],
            "created_at": datetime.now().isoformat(),
        }

        def _run():
            jobs[job_id]["status"] = "downloading"
            try:
                kwargs = {}
                if audio_only:
                    kwargs["audio_only"] = True
                results = engine.download_batch(urls, quality=quality, **kwargs)
                jobs[job_id]["results"] = results
                jobs[job_id]["status"] = "completed"
            except Exception as e:
                jobs[job_id]["results"] = [{"success": False, "error": str(e)}]
                jobs[job_id]["status"] = "failed"

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return jsonify({"job_id": job_id, "status": "pending"})

    @app.route("/api/job/<job_id>")
    def api_job_status(job_id):
        """Get job status."""
        job = jobs.get(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify(job)

    @app.route("/api/history")
    def api_history():
        """Get download history."""
        return jsonify({"jobs": list(jobs.values())[-50:]})

    @app.route("/api/stats")
    def api_stats():
        """Get download statistics."""
        total = len(jobs)
        completed = sum(1 for j in jobs.values() if j.get("status") == "completed")
        failed = sum(1 for j in jobs.values() if j.get("status") == "failed")
        platforms = {}
        for j in jobs.values():
            p = j.get("platform", "unknown")
            platforms[p] = platforms.get(p, 0) + 1
        return jsonify({
            "total_jobs": total,
            "completed": completed,
            "failed": failed,
            "platforms": platforms,
        })

    # ---- Music Search API ----

    @app.route("/api/search")
    def api_search():
        """Search YouTube, YouTube Music, and SoundCloud."""
        q = request.args.get("q", "").strip()
        provider = request.args.get("provider", "all").strip().lower()
        page = int(request.args.get("page", 0))
        if not q:
            return jsonify({"error": "Empty search query"}), 400
        try:
            result = search_music(q, page, provider=provider)
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 500

    @app.route("/api/stream", methods=["POST"])
    def api_stream():
        """Get a playable stream URL for a track/video/podcast."""
        data = request.get_json(force=True)
        source_url = (data.get("source_url") or "").strip()
        want_video = bool(data.get("want_video", False))
        title = (data.get("title") or "").strip()
        artist = (data.get("artist") or "").strip()
        if not source_url:
            return jsonify({"error": "No source URL provided"}), 400

        result = get_stream_url(source_url, want_video=want_video, title=title, artist=artist)
        return jsonify(result)

    @app.route("/api/download-track", methods=["POST"])
    def api_download_track():
        """Download a track from search results by source_url."""
        data = request.get_json(force=True)
        source_url = data.get("source_url", "").strip()
        title = data.get("title", "Unknown")
        artist = data.get("artist", "")

        if not source_url:
            return jsonify({"error": "No source URL provided"}), 400

        download_url = resolve_for_download(source_url)
        job_id = str(uuid.uuid4())[:8]
        jobs[job_id] = {
            "id": job_id,
            "status": "pending",
            "url": download_url,
            "platform": detect_platform(download_url),
            "quality": "best",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "track_title": title,
            "track_artist": artist,
        }

        def _run():
            jobs[job_id]["status"] = "downloading"
            try:
                result = engine.download(download_url, quality="best", audio_only=True)
                jobs[job_id]["result"] = result
                jobs[job_id]["status"] = "completed" if result.get("success") else "failed"
            except Exception as e:
                jobs[job_id]["result"] = {"success": False, "error": str(e)}
                jobs[job_id]["status"] = "failed"

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return jsonify({"job_id": job_id, "status": "pending"})

    # ---- Anime Search & Stream API ----

    @app.route("/api/anime/search")
    def api_anime_search():
        """Search anime across Yomi (AniList), Film2Media, AniWatchTV and Miruro."""
        q = request.args.get("q", "").strip()
        provider = request.args.get("provider", "all").strip().lower() or "all"
        page = max(1, int(request.args.get("page", 1)))
        if not q:
            return jsonify({"error": "Empty search query"}), 400
        try:
            return jsonify(anime_providers.search_anime(q, provider=provider, page=page))
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 500

    @app.route("/api/anime/episodes")
    def api_anime_episodes():
        """List episodes for an anime (Yomi: AniList id; others: series page URL)."""
        provider = (request.args.get("provider", "yomi") or "yomi").strip().lower()
        anime_id = request.args.get("anime_id", type=int)
        page_url = request.args.get("page_url", "").strip() or None
        try:
            return jsonify(anime_providers.get_anime_episodes(provider, anime_id=anime_id, page_url=page_url))
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 500

    @app.route("/api/anime/stream", methods=["POST"])
    def api_anime_stream():
        """Return a playable stream for an episode (m3u8 + subtitles, or an embed URL).

        Direct media URLs are relayed through /api/anime/media because the
        upstream CDNs enforce a Referer header browsers cannot send.
        """
        data = request.get_json(force=True)
        provider = (data.get("provider") or "yomi").strip().lower()
        raw_id = data.get("anime_id")
        try:
            anime_id = int(raw_id) if raw_id not in (None, "") else None
        except (TypeError, ValueError):
            anime_id = None
        episode = int(data.get("episode", 1) or 1)
        dub = bool(data.get("dub", False))
        page_url = (data.get("page_url") or "").strip() or None
        episode_url = (data.get("episode_url") or "").strip() or None

        result = anime_providers.get_anime_stream(
            provider, anime_id=anime_id, episode=episode, dub=dub,
            page_url=page_url, episode_url=episode_url,
        )
        # Mint relay URLs for direct media so the browser can actually play it
        if result.get("success") and result.get("stream_url") and not result.get("embed_only"):
            referer = result.get("referer") or ""
            result["stream_url"] = _relay_url(result["stream_url"], referer)
            for track in result.get("subtitles") or []:
                if track.get("file"):
                    track["file"] = _relay_url(track["file"], referer)
        return jsonify(result)

    @app.route("/api/anime/media")
    def api_anime_media():
        """Media relay: fetch upstream media with the required Referer.

        HLS playlists are rewritten so every variant/segment/key/subtitle URI
        also flows through this relay (upstream CDNs 403 any other referer).
        """
        url = request.args.get("url", "")
        referer = request.args.get("ref", "")
        if not _media_url_allowed(url):
            return jsonify({"error": "Blocked media URL"}), 400
        headers = {"User-Agent": _MEDIA_UA}
        if referer.startswith("http"):
            headers["Referer"] = referer
        fetch_url, strip = _media_fetch_url(url)
        try:
            upstream = requests.get(fetch_url, headers=headers, stream=True, timeout=30,
                                    allow_redirects=True)
        except Exception as e:
            return jsonify({"error": str(e)[:160]}), 502

        ctype = upstream.headers.get("Content-Type", "")
        is_playlist = "mpegurl" in ctype or "m3u8" in ctype or ".m3u8" in url.lower()
        if is_playlist:
            try:
                text = upstream.text
            except Exception:
                text = upstream.content.decode("utf-8", "replace")
            body = _rewrite_playlist(text, url, referer)
            resp = Response(body, status=upstream.status_code,
                            content_type="application/vnd.apple.mpegurl")
        elif strip:
            # TikTok-CDN segments carry a 252-byte wrapper — drop it, then stream
            first = next(upstream.iter_content(chunk_size=65536), b"")
            first = first[_STRIP_BYTES:] if len(first) > _STRIP_BYTES else b""

            def _stripped():
                if first:
                    yield first
                yield from upstream.iter_content(chunk_size=65536)

            resp = Response(stream_with_context(_stripped()),
                            status=upstream.status_code,
                            content_type="video/mp2t")
        else:
            resp = Response(stream_with_context(upstream.iter_content(chunk_size=65536)),
                            status=upstream.status_code,
                            content_type=ctype or "application/octet-stream")
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)

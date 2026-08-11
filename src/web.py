"""XCRDownloader Web UI — Flask application with modern dark interface."""
import os
import sys
import json
import threading
import uuid
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.engine import DownloaderEngine
from src.search import search_music, get_stream_url, resolve_for_download
from src.utils.helpers import detect_platform


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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8080, debug=False)

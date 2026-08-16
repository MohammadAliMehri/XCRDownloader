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

# (sys.path hack removed — packaging handles imports)
from src.engine import DownloaderEngine
from src.services.jobs import JobManager
from src.config import config
from src.api.download import download_bp
from src.api.search import search_bp
from src.api.anime import anime_bp
from src.logging import setup_logging

import requests
from src.relay import (
    _MEDIA_UA,
    _STRIP_HOSTS,
    _STRIP_BYTES,
    _TIKTOK_PROXY_HOST,
    _ALLOWED_RELAY_HOSTS,
    _media_fetch_url,
    _is_allowed_relay_host,
    _media_url_allowed,
    _relay_url,
    _rewrite_playlist,
    _safe_fetch_url,
    _strip_wrapper_stream,
)

# Setup logging if not already done
setup_logging()


def create_app(output_dir=None):
    """Create and configure the Flask application."""
    if output_dir is None:
        output_dir = config.download_dir
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"),
    )
    CORS(app)
    app.config["OUTPUT_DIR"] = output_dir

    engine = DownloaderEngine(output_dir=output_dir)
    job_manager = JobManager(max_jobs=config.max_jobs, ttl_seconds=config.job_ttl_seconds)

    # Store engine and job manager in app config for blueprints
    app.config['engine'] = engine
    app.config['job_manager'] = job_manager

    # Register blueprints
    app.register_blueprint(download_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(anime_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    # API routes have been moved to blueprints in src/api/
    # Only the media relay route remains here (will be moved later)

    # The media relay route has been moved to the anime blueprint in src/api/anime.py
    # No need to define it here anymore.

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=config.server_host, port=config.server_port, debug=config.debug)

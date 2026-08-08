"""Base downloader class with yt-dlp integration."""
import os
import sys
import yt_dlp
from datetime import datetime
from src.utils.helpers import sanitize_filename, format_filesize


class BaseDownloader:
    """Base class providing yt-dlp integration and common download logic."""

    DEFAULT_OPTS = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "no_color": True,
        "prefer_free_formats": False,
        "windowsfilenames": True,
    }

    def __init__(self, output_dir: str = "downloads"):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

    def _make_opts(self, extra: dict = None) -> dict:
        opts = dict(self.DEFAULT_OPTS)
        if extra:
            opts.update(extra)
        return opts

    def _ytdlp_download(self, url: str, opts: dict = None) -> dict:
        """Download using yt-dlp and return result info."""
        merged = self._make_opts(opts)
        result = {"success": False, "files": [], "error": None, "info": {}}

        try:
            with yt_dlp.YoutubeDL(merged) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    result["error"] = "Could not extract info from URL"
                    return result

                result["info"] = {
                    "title": info.get("title", "Unknown"),
                    "uploader": info.get("uploader", "Unknown"),
                    "duration": info.get("duration"),
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "upload_date": info.get("upload_date"),
                    "platform": info.get("extractor_key", "Unknown"),
                }

                # Collect downloaded files
                if "requested_downloads" in info:
                    for dl in info["requested_downloads"]:
                        if "filepath" in dl:
                            fp = dl["filepath"]
                            if os.path.exists(fp):
                                result["files"].append({
                                    "path": os.path.abspath(fp),
                                    "size": os.path.getsize(fp),
                                    "size_human": format_filesize(os.path.getsize(fp)),
                                    "ext": os.path.splitext(fp)[1],
                                })
                elif "entries" in info:
                    for entry in info.get("entries", []) or []:
                        if entry and "requested_downloads" in entry:
                            for dl in entry["requested_downloads"]:
                                if "filepath" in dl:
                                    fp = dl["filepath"]
                                    if os.path.exists(fp):
                                        result["files"].append({
                                            "path": os.path.abspath(fp),
                                            "size": os.path.getsize(fp),
                                            "size_human": format_filesize(os.path.getsize(fp)),
                                            "ext": os.path.splitext(fp)[1],
                                        })

                result["success"] = len(result["files"]) > 0
                if not result["success"]:
                    result["error"] = "Download completed but no files were saved"

        except yt_dlp.utils.DownloadError as e:
            result["error"] = f"Download error: {str(e)}"
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"

        return result

    def _ytdlp_extract_info(self, url: str, opts: dict = None) -> dict:
        """Extract info without downloading."""
        merged = self._make_opts(opts)
        merged["skip_download"] = True
        result = {"success": False, "info": {}, "error": None}

        try:
            with yt_dlp.YoutubeDL(merged) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    result["error"] = "Could not extract info"
                    return result
                result["info"] = info
                result["success"] = True
        except Exception as e:
            result["error"] = str(e)

        return result

    def download(self, url: str, **kwargs) -> dict:
        """Override in subclasses for platform-specific logic."""
        raise NotImplementedError

    def get_info(self, url: str) -> dict:
        """Override in subclasses for platform-specific info extraction."""
        return self._ytdlp_extract_info(url)

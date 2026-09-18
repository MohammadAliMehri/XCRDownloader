"""SoundCloud downloader — tracks, playlists and albums as MP3 with cover art.

Design (rewritten 2026-09):
- one fast metadata probe decides track vs playlist (no double yt-dlp run);
- playlists download per-entry with real per-track progress and per-track
  success/failure, instead of one opaque yt-dlp playlist run;
- progress_hook feeds a listener (wired to job progress by the API layer);
- user-facing errors are clean sentences, not raw yt-dlp dumps.
"""
import os
import yt_dlp
from .base import BaseDownloader
from src.logging import get_logger

logger = get_logger(__name__)


class SoundCloudDownloader(BaseDownloader):
    """Download from SoundCloud: single tracks, playlists and albums."""

    PLATFORM = "soundcloud"

    # Map raw yt-dlp failures to clean, actionable messages.
    _ERROR_MAP = [
        ("track is not available", "This track is not available (removed or region-locked)."),
        ("private track", "This track is private — the artist has restricted access."),
        ("geo-restricted", "This track is not available in your region."),
        ("http error 429", "SoundCloud is rate-limiting this machine — wait a minute and retry."),
        ("http error 404", "Track not found — the URL may be invalid or the track was deleted."),
        ("unable to download", "SoundCloud interrupted the transfer — please retry."),
        ("no video formats", "No playable audio stream was found for this track."),
    ]

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self._ffmpeg_dir = None

    # ------------------------------------------------------------------ API

    def download(self, url: str, quality: str = "best", audio_only: bool = True,
                 progress_cb=None, **kwargs) -> dict:
        """Download a SoundCloud track or playlist.

        progress_cb: optional callable(dict) invoked with
            {"done": int, "total": int|None, "current": str, "stage": str}
        """
        self._progress_cb = progress_cb
        info = self._probe(url)
        if not info.get("success"):
            return {"success": False, "error": info.get("error"), "files": [], "info": {}}

        meta = info["info"]
        if meta.get("_type") == "playlist" or meta.get("entries"):
            return self._download_playlist(url, meta)
        return self._download_track(url, meta)

    def get_info(self, url: str) -> dict:
        """Get SoundCloud track/playlist info with a preview payload."""
        raw = self._probe(url)
        if not raw.get("success"):
            return raw

        info = raw["info"]
        if info.get("_type") == "playlist" or info.get("entries"):
            entries = [e for e in (info.get("entries") or []) if e]
            raw["preview"] = {
                "title": info.get("title", "Unknown playlist"),
                "uploader": info.get("uploader") or "SoundCloud",
                "kind": "playlist",
                "track_count": info.get("playlist_count") or len(entries),
                "thumbnail": self._best_thumb(info),
                "tracks": [
                    {
                        "title": e.get("title")
                        or str(e.get("url") or e.get("webpage_url") or "").rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
                        or "Unknown",
                        "uploader": e.get("uploader") or e.get("album_artist") or "SoundCloud",
                        "duration": e.get("duration"),
                        "url": e.get("webpage_url") or e.get("url"),
                    }
                    for e in entries[:100]
                ],
                "description": (info.get("description") or "")[:300],
            }
            return raw

        raw["preview"] = {
            "title": info.get("title", "Unknown"),
            "uploader": info.get("uploader") or info.get("artist", "Unknown"),
            "duration": info.get("duration"),
            "duration_str": self._format_duration(info.get("duration")),
            "view_count": info.get("view_count") or info.get("playback_count"),
            "like_count": info.get("like_count") or info.get("favorit_count"),
            "thumbnail": self._best_thumb(info),
            "description": (info.get("description") or "")[:300],
            "genre": info.get("genre"),
            "tag_list": info.get("tag_list"),
        }
        return raw

    # ------------------------------------------------------------- internals

    def _probe(self, url: str) -> dict:
        """Single extract_info pass: works for tracks AND playlist pages."""
        opts = self._make_opts({
            "quiet": True, "no_warnings": True, "skip_download": True,
            # Flat entries give title/uploader/duration/webpage_url cheaply;
            # enough for the playlist path and the preview payload.
            "extract_flat": "in_playlist",
        })
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if info is None:
                return {"success": False, "error": "SoundCloud returned no data for this URL."}
            return {"success": True, "info": info}
        except yt_dlp.utils.DownloadError as exc:
            return {"success": False, "error": self._humanize(str(exc))}
        except Exception as exc:  # unexpected — log it, keep the message clean
            logger.warning("SoundCloud probe failed for %s: %s", url, exc)
            return {"success": False, "error": "Could not read this SoundCloud URL."}

    def _download_track(self, url: str, meta: dict) -> dict:
        """Download one track as MP3 320k with embedded cover art."""
        uploader = meta.get("uploader") or meta.get("uploader_id") or "Unknown"
        output_tpl = os.path.join(
            self.output_dir, "soundcloud", uploader,
            "%(title).100s_%(id)s.%(ext)s",
        )
        opts = self._make_opts({
            "outtmpl": output_tpl,
            "format": "bestaudio/best",
            "postprocessors": self._build_audio_postprocessors(),
            "writethumbnail": True,
            "writeinfojson": False,
            "keepvideo": False,
            "retries": 3,
            "noprogress": True,
            "progress_hooks": [self._hook],
        })
        result = self._ytdlp_download(url, opts)
        result["files"] = self._keep_audio_only(result.get("files", []))
        if result.get("success"):
            result["info"] = {
                "title": meta.get("title", "Unknown"),
                "uploader": uploader,
                "duration": meta.get("duration"),
                "genre": meta.get("genre"),
                "thumbnail": self._best_thumb(meta),
            }
        elif not result.get("error"):
            result["error"] = "Download failed — please retry."
        return result

    def _download_playlist(self, url: str, meta: dict) -> dict:
        """Download each playlist entry individually with real progress.

        A single yt-dlp playlist run with ignoreerrors=True swallows which
        entries failed; looping per entry keeps per-track status and lets the
        UI show "3 / 25 tracks".
        """
        entries = [e for e in (meta.get("entries") or []) if e]
        total = len(entries)
        title = meta.get("title", "Unknown playlist")
        uploader = meta.get("uploader") or "SoundCloud"

        result = {
            "success": False, "files": [], "error": None,
            "info": {
                "title": title, "uploader": uploader,
                "kind": "playlist", "track_count": total,
                "thumbnail": self._best_thumb(meta),
            },
            "playlist": {"total": total, "completed": 0, "failed": 0,
                         "tracks": []},
        }

        for i, entry in enumerate(entries, 1):
            track_url = entry.get("webpage_url") or entry.get("url")
            # Flat playlist entries carry only url+id; fall back to the URL slug
            track_title = (entry.get("title")
                           or str(entry.get("url") or track_url or "").rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
                           or f"Track {i}")
            self._report({"done": i - 1, "total": total, "current": track_title,
                          "stage": "downloading"})
            if not track_url:
                result["playlist"]["failed"] += 1
                result["playlist"]["tracks"].append(
                    {"title": track_title, "success": False, "error": "No URL"})
                continue

            # Flat entries lack full metadata; re-probe the track page (also
            # serves as the cover-art source for this track).
            track_info = self._probe(track_url)
            if not track_info.get("success"):
                logger.warning("SoundCloud playlist item failed: %s (%s)",
                               track_title, track_info.get("error"))
                result["playlist"]["failed"] += 1
                result["playlist"]["tracks"].append(
                    {"title": track_title, "success": False,
                     "error": track_info.get("error") or "Probe failed"})
                continue

            dl = self._download_track(track_url, track_info["info"])
            track_title = track_info["info"].get("title") or track_title
            if dl.get("success"):
                result["files"].extend(dl.get("files", []))
                result["playlist"]["completed"] += 1
                result["playlist"]["tracks"].append(
                    {"title": track_title, "success": True})
            else:
                result["playlist"]["failed"] += 1
                result["playlist"]["tracks"].append(
                    {"title": track_title, "success": False,
                     "error": dl.get("error")})

        result["success"] = result["playlist"]["completed"] > 0
        if not result["success"]:
            result["error"] = ("None of the tracks in this playlist could be "
                               "downloaded.") if total else "Empty playlist."
        self._report({"done": total, "total": total, "current": "",
                      "stage": "finished"})
        return result

    def _hook(self, d):
        """yt-dlp progress_hook → forward a compact snapshot to the listener."""
        if not callable(getattr(self, "_progress_cb", None)):
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            got = d.get("downloaded_bytes") or 0
            self._progress_cb({
                "done": 0, "total": None, "stage": "downloading",
                "current": os.path.basename(d.get("filename") or ""),
                "pct": round(got / total * 100) if total else None,
            })
        elif status == "finished":
            self._progress_cb({"done": 0, "total": None, "stage": "processing",
                               "current": "", "pct": None})

    def _report(self, payload: dict):
        if callable(getattr(self, "_progress_cb", None)):
            try:
                self._progress_cb(payload)
            except Exception as exc:
                logger.debug("progress callback failed: %s", exc)

    @staticmethod
    def _keep_audio_only(files: list) -> list:
        """Keep audio files; delete leftover thumbnail sidecars."""
        audio_exts = (".mp3", ".m4a", ".opus", ".wav", ".flac")
        cleaned = []
        for f in files:
            if str(f.get("ext", "")).lower() in audio_exts:
                cleaned.append(f)
            else:
                try:
                    os.remove(f["path"])
                except OSError:
                    pass
        return cleaned

    @staticmethod
    def _best_thumb(info: dict) -> str | None:
        thumb = info.get("thumbnail")
        if thumb:
            return thumb
        thumbs = info.get("thumbnails") or []
        return thumbs[-1].get("url") if thumbs else None

    @classmethod
    def _humanize(cls, raw: str) -> str:
        low = raw.lower()
        for key, human in cls._ERROR_MAP:
            if key in low:
                return human
        return raw[:200]

    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return None
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"

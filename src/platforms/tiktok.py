"""TikTok downloader — Videos, Slideshows, No Watermark.

NOTE (2026-08): TikTok began serving a JS challenge / block page to
non-browser requests around 2026-08-10, breaking yt-dlp with
"Unexpected response from webpage request" (yt-dlp issue #17403, still
open). The community-confirmed workaround is a recent Chrome
User-Agent + Referer header. We apply that by default and rotate
through UA variants on failure. curl_cffi is required for the TLS
impersonation the extractor attempts (see requirements.txt).
"""
import os
import time
import requests
from .base import BaseDownloader

# TikTok now fingerprints the User-Agent on the webpage/API requests.
# Chrome 140+ is the community-confirmed fix (yt-dlp#17403); older
# Chrome 125 or the raw Android app UA trips the WAF challenge.
_CHROME_140_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
_UA_ROTATION = [
    _CHROME_140_UA,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

# Errors that indicate TikTok's WAF/challenge instead of a real failure —
# worth retrying with a different UA.
_RETRYABLE = (
    "unexpected response from webpage request",
    "unable to download api page",
    "failed to parse json",
    "http error 403",
)


class TikTokDownloader(BaseDownloader):
    """Download from TikTok: Videos without watermark, slideshows, audio."""

    PLATFORM = "tiktok"

    def __init__(self, output_dir="downloads"):
        super().__init__(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": _CHROME_140_UA,
        })

    def _make_tiktok_opts(self, base_opts: dict, user_agent: str) -> dict:
        """Inject TikTok-specific headers into yt-dlp opts."""
        opts = dict(base_opts or {})
        headers = dict(opts.get("http_headers") or {})
        headers.update({
            "User-Agent": user_agent,
            "Referer": "https://www.tiktok.com/",
        })
        opts["http_headers"] = headers
        # Keep extractor_args consistent if the caller already set some
        opts.setdefault("extractor_args", {})
        return opts

    def download(self, url: str, quality: str = "best", no_watermark: bool = True,
                 audio_only: bool = False, **kwargs) -> dict:
        """Download TikTok video without watermark."""
        output_tpl = os.path.join(
            self.output_dir,
            "tiktok",
            "%(uploader)s",
            "%(title).100s_%(id)s.%(ext)s",
        )

        if audio_only:
            format_spec = "bestaudio/best"
            opts = {
                "outtmpl": output_tpl,
                "format": format_spec,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
            }
        else:
            format_spec = "best"
            if quality == "hd":
                format_spec = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            elif quality == "sd":
                format_spec = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"

            opts = {
                "outtmpl": output_tpl,
                "format": format_spec,
                "merge_output_format": "mp4",
            }

        opts["writeinfojson"] = False
        opts["writethumbnail"] = False

        # Try the modern Chrome UA first, rotating on WAF/challenge errors.
        last_error = None
        for ua in _UA_ROTATION:
            attempt_opts = self._make_tiktok_opts(opts, ua)
            result = self._ytdlp_download(url, attempt_opts)
            if result.get("success"):
                return result
            error = (result.get("error") or "").lower()
            if not any(flag in error for flag in _RETRYABLE):
                return result  # non-WAF failure — no point rotating
            last_error = result
            # TikTok rate-limits rapid retries; back off briefly
            time.sleep(2)

        return last_error or {"success": False, "files": [], "error": "TikTok request failed", "info": {}}

    def download_audio(self, url: str, **kwargs) -> dict:
        """Extract audio only from TikTok video."""
        return self.download(url, audio_only=True, **kwargs)

    def download_batch(self, urls: list, **kwargs) -> list:
        """Download multiple TikTok URLs."""
        results = []
        for url in urls:
            results.append(self.download(url, **kwargs))
        return results

    def get_info(self, url: str) -> dict:
        """Get TikTok content info without downloading."""
        opts = self._make_tiktok_opts({}, _CHROME_140_UA)
        return self._ytdlp_extract_info(url, opts)

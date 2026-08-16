"""Configuration for XCRDownloader.

Settings are loaded from environment variables with prefix XCR_.
Defaults are provided for all settings.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Config:
    # Server
    server_host: str = "127.0.0.1"
    server_port: int = 8080
    debug: bool = False

    # Downloads
    download_dir: str = "downloads"
    max_workers: int = 3

    # Jobs
    job_ttl_seconds: int = 3600
    max_jobs: int = 100

    # Network
    connect_timeout: int = 30
    read_timeout: int = 30

    # Relay
    relay_allowed_hosts: List[str] = field(default_factory=lambda: [
        "megaplay.buzz",
        "tiktokcdn.com",
        "ibyteimg.com",
        "ipstatp.com",
        "yoot.trycloud.pro",
        "norami.top",
        "akirax.buzz",
        "shiora.",
    ])

    # Logging
    log_level: str = "INFO"

    # Anime allowed hosts (will be loaded from env or default)
    anime_allowed_hosts: dict = field(default_factory=lambda: {
        "yomi": ["anilist.co", "graphql.anilist.co", "megaplay.buzz", "yomi.to"],
        "aniwatchtv": ["aniwatchtv.com.ro", "gogoanime", "megaplay.buzz", "kwik.cx", "streamwish"],
        "f2mc": ["f2mc.top"],
        "miruro": ["miruro.ro", "megaplay.buzz", "dramastream"],
    })

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        def get_str(key: str, default: str) -> str:
            return os.getenv(f"XCR_{key}", default)

        def get_int(key: str, default: int) -> int:
            val = os.getenv(f"XCR_{key}")
            if val is None:
                return default
            try:
                return int(val)
            except ValueError:
                return default

        def get_bool(key: str, default: bool) -> bool:
            val = os.getenv(f"XCR_{key}")
            if val is None:
                return default
            return val.lower() in ("true", "1", "yes", "on")

        def get_list(key: str, default: List[str]) -> List[str]:
            val = os.getenv(f"XCR_{key}")
            if val is None:
                return default
            return [item.strip() for item in val.split(",") if item.strip()]

        return cls(
            server_host=get_str("SERVER_HOST", "127.0.0.1"),
            server_port=get_int("SERVER_PORT", 8080),
            debug=get_bool("DEBUG", False),
            download_dir=get_str("DOWNLOAD_DIR", "downloads"),
            max_workers=get_int("MAX_WORKERS", 3),
            job_ttl_seconds=get_int("JOB_TTL_SECONDS", 3600),
            max_jobs=get_int("MAX_JOBS", 100),
            connect_timeout=get_int("CONNECT_TIMEOUT", 30),
            read_timeout=get_int("READ_TIMEOUT", 30),
            relay_allowed_hosts=get_list("RELAY_ALLOWED_HOSTS", [
                "megaplay.buzz",
                "tiktokcdn.com",
                "ibyteimg.com",
                "ipstatp.com",
                "yoot.trycloud.pro",
                "norami.top",
                "akirax.buzz",
                "shiora.",
            ]),
            log_level=get_str("LOG_LEVEL", "INFO"),
            # Anime hosts are more complex; keep defaults for now.
        )

# Global configuration instance
config = Config.from_env()
"""Job manager for async download tasks."""
import threading
import uuid
import time
from datetime import datetime
from typing import Dict, Optional, Any, List

class JobManager:
    """In-memory job store with TTL, bounded size, and thread-safe operations."""

    def __init__(self, max_jobs: int = 100, ttl_seconds: int = 3600):
        self._jobs: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._max_jobs = max_jobs
        self._ttl = ttl_seconds
        self._cleanup_thread = None
        self._stop_cleanup = False
        self._start_cleanup()

    def _start_cleanup(self):
        def cleanup_loop():
            while not self._stop_cleanup:
                time.sleep(60)  # run every minute
                with self._lock:
                    now = datetime.now().isoformat()
                    expired = []
                    for job_id, job in self._jobs.items():
                        created = job.get("created_at")
                        if created:
                            try:
                                dt = datetime.fromisoformat(created)
                                age = (datetime.now() - dt).total_seconds()
                                if age > self._ttl:
                                    expired.append(job_id)
                            except Exception:
                                pass
                    for job_id in expired:
                        self._jobs.pop(job_id, None)
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def create_job(self, data: dict) -> str:
        """Create a new job and return its id."""
        job_id = str(uuid.uuid4())[:8]
        with self._lock:
            # Enforce max size
            if len(self._jobs) >= self._max_jobs:
                # Remove oldest jobs (by creation time)
                sorted_jobs = sorted(self._jobs.items(), key=lambda kv: kv[1].get("created_at", ""))
                to_remove = len(self._jobs) - self._max_jobs + 1
                for old_id, _ in sorted_jobs[:to_remove]:
                    self._jobs.pop(old_id, None)
            job = {
                "id": job_id,
                "status": "pending",
                "result": None,
                "results": None,
                "created_at": datetime.now().isoformat(),
                **data
            }
            self._jobs[job_id] = job
        return job_id

    def update_job(self, job_id: str, **updates) -> bool:
        """Update job fields."""
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._jobs[job_id].update(updates)
            return True

    def get_job(self, job_id: str) -> Optional[dict]:
        """Get a copy of the job data."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.copy() if job else None

    def list_jobs(self, limit: int = 50) -> List[dict]:
        """List recent jobs (most recent first)."""
        with self._lock:
            jobs = list(self._jobs.values())
            jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
            return jobs[:limit]

    def shutdown(self):
        """Stop the cleanup thread."""
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2.0)
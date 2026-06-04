"""Small persistent job store for the web UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import traceback
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4


@dataclass
class Job:
    id: str
    kind: str
    status: str
    created_utc: str
    started_utc: Optional[str] = None
    finished_utc: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "created_utc": self.created_utc,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "details": self.details,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Job":
        return Job(
            id=data["id"],
            kind=data["kind"],
            status=data["status"],
            created_utc=data["created_utc"],
            started_utc=data.get("started_utc"),
            finished_utc=data.get("finished_utc"),
            result=data.get("result"),
            error=data.get("error"),
            traceback=data.get("traceback"),
            details=data.get("details") or {},
        )


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def create(self, kind: str, details: Optional[Dict[str, Any]] = None) -> Job:
        job = Job(
            id=uuid4().hex,
            kind=kind,
            status="queued",
            created_utc=now_utc(),
            details=details or {},
        )
        with self.lock:
            jobs = self._read()
            jobs.append(job)
            self._write(jobs)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self.lock:
            for job in self._read():
                if job.id == job_id:
                    return job
        return None

    def list(self, limit: int = 25) -> List[Job]:
        with self.lock:
            jobs = self._read()
        return list(reversed(jobs[-limit:]))

    def update(self, job_id: str, **updates: Any) -> Job:
        with self.lock:
            jobs = self._read()
            for index, job in enumerate(jobs):
                if job.id == job_id:
                    for key, value in updates.items():
                        setattr(job, key, value)
                    jobs[index] = job
                    self._write(jobs)
                    return job
        raise KeyError(job_id)

    def start_background(self, job: Job, work: Callable[[], Dict[str, Any]]) -> None:
        thread = threading.Thread(target=self._run_job, args=(job.id, work), daemon=True)
        thread.start()

    def _run_job(self, job_id: str, work: Callable[[], Dict[str, Any]]) -> None:
        self.update(job_id, status="running", started_utc=now_utc())
        try:
            result = work()
            self.update(job_id, status="succeeded", finished_utc=now_utc(), result=result)
        except Exception as exc:  # pragma: no cover - traceback content depends on runtime
            self.update(
                job_id,
                status="failed",
                finished_utc=now_utc(),
                error=str(exc),
                traceback=traceback.format_exc(),
            )

    def _read(self) -> List[Job]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = []
        return [Job.from_dict(item) for item in data]

    def _write(self, jobs: List[Job]) -> None:
        self.path.write_text(
            json.dumps([job.to_dict() for job in jobs], indent=2, sort_keys=True),
            encoding="utf-8",
        )


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()

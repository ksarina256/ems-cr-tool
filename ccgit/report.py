"""Comparison report models and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import json
from pathlib import Path
from typing import Dict, List, Optional


STATUS_LABELS = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type-changed",
    "U": "unmerged",
    "X": "unknown",
    "B": "pairing-broken",
}


@dataclass(frozen=True)
class DiffEntry:
    status: str
    path: str
    old_path: Optional[str] = None

    @property
    def label(self) -> str:
        key = self.status[:1]
        return STATUS_LABELS.get(key, self.status)


@dataclass(frozen=True)
class CompareReport:
    base: str
    target: str
    entries: List[DiffEntry]
    stat: str = ""
    gitea_url: Optional[str] = None
    counts: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "base": self.base,
            "target": self.target,
            "counts": self.counts,
            "stat": self.stat,
            "gitea_url": self.gitea_url,
            "entries": [
                {
                    "status": entry.status,
                    "label": entry.label,
                    "path": entry.path,
                    "old_path": entry.old_path,
                }
                for entry in self.entries
            ],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def write_html(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = "\n".join(
            "<tr>"
            f"<td>{escape(entry.label)}</td>"
            f"<td>{escape(entry.old_path or '')}</td>"
            f"<td>{escape(entry.path)}</td>"
            "</tr>"
            for entry in self.entries
        )
        counts = ", ".join(f"{escape(key)}: {value}" for key, value in sorted(self.counts.items()))
        gitea = (
            f'<p><a href="{escape(self.gitea_url)}">Open full diff in Gitea</a></p>'
            if self.gitea_url
            else ""
        )
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(self.base)} vs {escape(self.target)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #18202a; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #d6dbe1; padding: 0.55rem; text-align: left; }}
    th {{ background: #f5f7f9; }}
    code {{ background: #eef1f4; padding: 0.1rem 0.25rem; border-radius: 4px; }}
    pre {{ background: #111827; color: #f9fafb; padding: 1rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{escape(self.base)} vs {escape(self.target)}</h1>
  <p>{escape(counts or 'No file changes')}</p>
  {gitea}
  <h2>Files</h2>
  <table>
    <thead><tr><th>Status</th><th>Old path</th><th>Path</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>Git Stat</h2>
  <pre>{escape(self.stat)}</pre>
</body>
</html>
"""
        path.write_text(html, encoding="utf-8")


def parse_name_status(output: str) -> List[DiffEntry]:
    entries = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") or status.startswith("C"):
            if len(parts) >= 3:
                entries.append(DiffEntry(status=status, old_path=parts[1], path=parts[2]))
            continue
        if len(parts) >= 2:
            entries.append(DiffEntry(status=status, path=parts[1]))
    return entries


def count_entries(entries: List[DiffEntry]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        counts[entry.label] = counts.get(entry.label, 0) + 1
    return counts

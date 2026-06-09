"""
EMS CR Validation Tool - Comparison Engine
Scans two directory trees, diffs files, detects CR tags, and produces a
structured JSON report consumed by the web front end.
"""

import os
import re
import hashlib
import difflib
import json
import datetime

# ---------------------------------------------------------------------------
# File types to compare as text. Everything else is flagged as binary/skipped.
# ---------------------------------------------------------------------------
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".sh", ".bash", ".ksh", ".csh",
    ".yaml", ".yml", ".json", ".xml", ".html", ".htm",
    ".css", ".scss", ".less",
    ".sql", ".pl", ".rb", ".go", ".rs",
    ".properties", ".cfg", ".conf", ".ini", ".env",
    ".md", ".txt", ".rst", ".csv",
    ".mk", ".makefile", ".cmake",
    ".groovy", ".gradle", ".bat", ".ps1",
}

# Regex to find CR identifiers anywhere in a file's content or path.
# Matches patterns like CR-1042, CR_1042, cr-1042 (case-insensitive).
CR_PATTERN = re.compile(r'\bCR[-_](\d+)\b', re.IGNORECASE)


def _is_text_file(path):
    ext = os.path.splitext(path)[1].lower()
    return ext in TEXT_EXTENSIONS


def _file_hash(path):
    """MD5 hash of file contents for quick change detection."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (IOError, OSError):
        return None


def _read_lines(path):
    """Read a file and return its lines, trying common encodings."""
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            with open(path, "r", encoding=enc, errors="replace") as f:
                return f.readlines()
        except (IOError, OSError):
            return []
    return []


def _extract_crs_from_content(lines):
    """Return a sorted list of unique CR IDs found in file lines."""
    crs = set()
    for line in lines:
        for m in CR_PATTERN.finditer(line):
            crs.add("CR-" + m.group(1))
    return sorted(crs)


def _extract_crs_from_path(path):
    """Return CR IDs found in the file path itself."""
    crs = set()
    for m in CR_PATTERN.finditer(path):
        crs.add("CR-" + m.group(1))
    return sorted(crs)


def _build_file_index(root):
    """
    Walk a directory tree and return a dict mapping
    relative_path -> absolute_path for every file found.
    """
    index = {}
    root = os.path.normpath(root)
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
            index[rel_path] = abs_path
    return index


def _make_diff(source_lines, target_lines, source_path, target_path, context=3):
    """
    Produce a list of diff line objects suitable for the front end.
    Each object has: type (added/removed/context), lineA, lineB, content.
    """
    diff_lines = []
    matcher = difflib.SequenceMatcher(
        None,
        [l.rstrip("\n") for l in source_lines],
        [l.rstrip("\n") for l in target_lines],
        autojunk=False,
    )

    for group in matcher.get_grouped_opcodes(context):
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    diff_lines.append({
                        "type": "context",
                        "lineA": i + 1,
                        "lineB": j + 1,
                        "content": source_lines[i].rstrip("\n") if i < len(source_lines) else "",
                    })
            if tag in ("replace", "delete"):
                for i in range(i1, i2):
                    diff_lines.append({
                        "type": "removed",
                        "lineA": i + 1,
                        "lineB": None,
                        "content": source_lines[i].rstrip("\n") if i < len(source_lines) else "",
                    })
            if tag in ("replace", "insert"):
                for j in range(j1, j2):
                    diff_lines.append({
                        "type": "added",
                        "lineA": None,
                        "lineB": j + 1,
                        "content": target_lines[j].rstrip("\n") if j < len(target_lines) else "",
                    })

    return diff_lines


def run_comparison(source_dir, target_dir, cr_mappings=None):
    """
    Main entry point. Compares source_dir (ClearCase) against target_dir (Gitea).

    cr_mappings: optional dict of { "CR-1042": ["path/to/file.py", ...], ... }
                 If provided, CR status is cross-checked against mapped files.

    Returns a dict with keys: meta, summary, files, cr_status
    """
    if cr_mappings is None:
        cr_mappings = {}

    source_dir = os.path.normpath(source_dir)
    target_dir = os.path.normpath(target_dir)

    # ── 1. Build file indexes ──────────────────────────────────────────────
    print("[1/6] Scanning source directory (ClearCase)...")
    source_index = _build_file_index(source_dir)

    print("[2/6] Scanning target directory (Gitea)...")
    target_index = _build_file_index(target_dir)

    all_paths = sorted(set(source_index) | set(target_index))

    # ── 2. Classify each file ──────────────────────────────────────────────
    print("[3/6] Detecting added, removed, and modified files...")
    file_results = []
    counts = {"modified": 0, "added": 0, "removed": 0, "binary": 0, "identical": 0}

    for rel_path in all_paths:
        in_source = rel_path in source_index
        in_target = rel_path in target_index

        # Determine status
        if in_source and not in_target:
            status = "removed"
        elif in_target and not in_source:
            status = "added"
        else:
            # Both exist — check if contents differ
            src_hash = _file_hash(source_index[rel_path])
            tgt_hash = _file_hash(target_index[rel_path])
            if src_hash == tgt_hash:
                counts["identical"] += 1
                continue  # skip identical files
            status = "modified"

        # ── 3. Build diff for text files ──────────────────────────────────
        print(f"[4/6] Diffing: {rel_path}")
        is_text = _is_text_file(rel_path)
        diff = []
        lines_added = 0
        lines_removed = 0
        source_crs = []
        target_crs = []

        if is_text:
            src_lines = _read_lines(source_index[rel_path]) if in_source else []
            tgt_lines = _read_lines(target_index[rel_path]) if in_target else []

            source_crs = _extract_crs_from_content(src_lines)
            target_crs = _extract_crs_from_content(tgt_lines)

            if status == "modified":
                diff = _make_diff(src_lines, tgt_lines, rel_path, rel_path)
                lines_added = sum(1 for d in diff if d["type"] == "added")
                lines_removed = sum(1 for d in diff if d["type"] == "removed")
            elif status == "added":
                lines_added = len(tgt_lines)
                diff = [{"type": "added", "lineA": None, "lineB": i+1,
                          "content": l.rstrip("\n")} for i, l in enumerate(tgt_lines)]
            elif status == "removed":
                lines_removed = len(src_lines)
                diff = [{"type": "removed", "lineA": i+1, "lineB": None,
                          "content": l.rstrip("\n")} for i, l in enumerate(src_lines)]
        else:
            counts["binary"] += 1

        # ── 4. CR detection ───────────────────────────────────────────────
        # CRs found in file content + path
        all_crs_in_file = sorted(set(source_crs + target_crs +
                                      _extract_crs_from_path(rel_path)))

        counts[status] += 1

        file_results.append({
            "id": hashlib.md5(rel_path.encode()).hexdigest()[:8],
            "path": rel_path,
            "status": status,
            "isText": is_text,
            "linesAdded": lines_added,
            "linesRemoved": lines_removed,
            "crs": all_crs_in_file,
            "cr": all_crs_in_file[0] if all_crs_in_file else None,
            "diff": diff,
        })

    # ── 5. CR status summary ───────────────────────────────────────────────
    print("[5/6] Resolving CR status...")
    cr_status = {}

    # Auto-discovered CRs from file scan
    discovered_crs = set()
    for f in file_results:
        for cr in f["crs"]:
            discovered_crs.add(cr)

    # Merge with manually mapped CRs
    all_cr_ids = sorted(set(cr_mappings.keys()) | discovered_crs)

    for cr_id in all_cr_ids:
        mapped_files = cr_mappings.get(cr_id, [])
        related_files = [f for f in file_results if cr_id in f["crs"]]

        if not mapped_files:
            # Auto-discovered only
            status = "present" if related_files else "missing"
        else:
            # Check how many mapped files actually show up in diffs
            found = [mf for mf in mapped_files
                     if any(f["path"].endswith(mf) or mf in f["path"]
                            for f in file_results)]
            if len(found) == len(mapped_files):
                status = "present"
            elif len(found) == 0:
                status = "missing"
            else:
                status = "partial"

        cr_status[cr_id] = {
            "status": status,
            "mappedFiles": mapped_files,
            "relatedFiles": [f["path"] for f in related_files],
            "totalLinesAdded": sum(f["linesAdded"] for f in related_files),
            "totalLinesRemoved": sum(f["linesRemoved"] for f in related_files),
        }

    # ── 6. Build final report ──────────────────────────────────────────────
    print("[6/6] Building report...")
    cr_counts = {"present": 0, "partial": 0, "missing": 0}
    for v in cr_status.values():
        cr_counts[v["status"]] += 1

    report = {
        "meta": {
            "sourcePath": source_dir,
            "targetPath": target_dir,
            "timestamp": datetime.datetime.now().isoformat(),
            "totalScanned": len(all_paths),
            "identicalFiles": counts["identical"],
            "binaryFilesSkipped": counts["binary"],
        },
        "summary": {
            "changed": counts["modified"],
            "added": counts["added"],
            "removed": counts["removed"],
            "total": counts["modified"] + counts["added"] + counts["removed"],
            "crs_present": cr_counts["present"],
            "crs_partial": cr_counts["partial"],
            "crs_missing": cr_counts["missing"],
        },
        "files": file_results,
        "crStatus": cr_status,
    }

    return report


if __name__ == "__main__":
    # Quick CLI test — run directly to verify engine works
    import sys
    if len(sys.argv) < 3:
        print("Usage: python compare_engine.py <source_dir> <target_dir>")
        print("Example: python compare_engine.py ../input/clearcase ../input/gitea")
        sys.exit(1)

    source = sys.argv[1]
    target = sys.argv[2]

    if not os.path.isdir(source):
        print(f"ERROR: source directory not found: {source}")
        sys.exit(1)
    if not os.path.isdir(target):
        print(f"ERROR: target directory not found: {target}")
        sys.exit(1)

    print(f"\nComparing:\n  Source: {source}\n  Target: {target}\n")
    result = run_comparison(source, target)

    out_path = "comparison_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"\nDone. Results written to {out_path}")
    print(f"  Modified : {result['summary']['changed']}")
    print(f"  Added    : {result['summary']['added']}")
    print(f"  Removed  : {result['summary']['removed']}")
    print(f"  CRs found: {len(result['crStatus'])}")

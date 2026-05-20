"""Synchronous memory file store for the Game Master.

The memory file is the single source of truth about the world state. It is a
JSON file containing a list of entries, each with:

    - id:        unique identifier (short uuid hex)
    - validated: bool. False means the label is "not validated", True means
                 the entry has already been accepted by the Arbiter.
    - author:    who produced the prompt that this entry summarises
                 (a player name, e.g. "Thorin", or "narrator")
    - content:   the summarised text written by the Memory Keeper

All operations are intentionally synchronous and serialised through plain file
I/O. The Game Master orchestrator calls every sub-agent one at a time, so no
two writes ever happen concurrently and we do not need locks.
"""

import json
import uuid
from typing import Optional


def init_memory(path: str) -> None:
    """Create or reset the memory file at the given path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"entries": [], "metadata": {"validated_since_condense": 0}},
            f,
            ensure_ascii=False,
            indent=2,
        )


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("entries", [])
    data.setdefault("metadata", {})
    data["metadata"].setdefault("validated_since_condense", 0)
    return data


def _write(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_memory(path: str) -> list[dict]:
    """Return the full list of entries currently stored on disk."""
    return _read(path)["entries"]


def append_entry(
    path: str,
    author: str,
    content: str,
    validated: bool = False,
    kind: str = "event",
) -> str:
    """Append a new entry to the memory file. Returns the entry id."""
    data = _read(path)
    entry_id = uuid.uuid4().hex[:8]
    data["entries"].append(
        {
            "id": entry_id,
            "validated": validated,
            "author": author,
            "content": content,
            "kind": kind,
        }
    )
    if validated:
        data["metadata"]["validated_since_condense"] += 1
    _write(path, data)
    return entry_id


def mark_validated(path: str, entry_id: str) -> None:
    """Flip the label of one entry to validated."""
    data = _read(path)
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            was_validated = entry["validated"]
            entry["validated"] = True
            if not was_validated:
                data["metadata"]["validated_since_condense"] += 1
            break
    _write(path, data)


def delete_entry(path: str, entry_id: str) -> None:
    """Remove a single entry by id (no-op if it does not exist)."""
    data = _read(path)
    data["entries"] = [e for e in data["entries"] if e["id"] != entry_id]
    _write(path, data)


def delete_unvalidated(path: str) -> int:
    """Remove every not-validated entry. Returns how many were deleted."""
    data = _read(path)
    before = len(data["entries"])
    data["entries"] = [e for e in data["entries"] if e["validated"]]
    removed = before - len(data["entries"])
    _write(path, data)
    return removed


def get_entry(path: str, entry_id: str) -> Optional[dict]:
    """Return a single entry by id, or None if it is gone."""
    for entry in read_memory(path):
        if entry["id"] == entry_id:
            return entry
    return None


def validated_since_condense(path: str) -> int:
    """Return how many entries were validated since the last condensation."""
    return _read(path)["metadata"]["validated_since_condense"]


def validated_entries(path: str) -> list[dict]:
    """Return the validated entries currently stored on disk."""
    return [e for e in read_memory(path) if e["validated"]]


def replace_validated_with_summary(
    path: str,
    summary: str,
    keep_recent: int,
) -> str | None:
    """Condense old validated entries into one validated summary entry."""
    data = _read(path)
    validated = [e for e in data["entries"] if e["validated"]]
    if len(validated) <= keep_recent:
        return None

    recent = validated[-keep_recent:] if keep_recent > 0 else []
    recent_ids = {e["id"] for e in recent}
    summary_id = uuid.uuid4().hex[:8]
    summary_entry = {
        "id": summary_id,
        "validated": True,
        "author": "memory_keeper",
        "content": summary,
        "kind": "summary",
    }
    kept_entries = [
        e
        for e in data["entries"]
        if not e["validated"] or e["id"] in recent_ids
    ]
    data["entries"] = [summary_entry] + kept_entries
    data["metadata"]["validated_since_condense"] = 0
    _write(path, data)
    return summary_id


def format_entries(entries: list[dict]) -> str:
    """Render entries as plain text for LLM consumption."""
    if not entries:
        return "(no entries)"
    lines = []
    for e in entries:
        label = "[validated]" if e["validated"] else "[not validated]"
        lines.append(f"{label} [{e['author']}] (id={e['id']}): {e['content']}")
    return "\n".join(lines)


def format_validated(path: str) -> str:
    """Pretty-print all validated entries (the trusted world state)."""
    return format_entries(validated_entries(path))


def format_all(path: str) -> str:
    """Pretty-print every entry (validated and not)."""
    return format_entries(read_memory(path))

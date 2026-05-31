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
    """Create or reset the memory file at the given path.

    Preserves any existing protected_player_data block across resets.
    """
    import os
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    existing_protected = None
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            existing_protected = old_data.get("protected_player_data", None)
        except (json.JSONDecodeError, OSError):
            pass

    data = {
        "entries": [],
        "metadata": {"validated_since_condense": 0}
    }
    if existing_protected:
        data["protected_player_data"] = existing_protected

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Reset uncompressed file
    import os
    base, ext = os.path.splitext(path)
    uncompressed_path = f"{base}_uncompressed.json"
    if os.path.exists(uncompressed_path):
        try:
            os.remove(uncompressed_path)
        except OSError:
            pass
    try:
        with open(uncompressed_path, "w", encoding="utf-8") as f:
            json.dump({"entries": []}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _append_to_uncompressed(path: str, entry: dict) -> None:
    """Temporarily append validated entries to an uncompressed backup file for comparison."""
    import os
    base, ext = os.path.splitext(path)
    uncompressed_path = f"{base}_uncompressed.json"
    
    try:
        if os.path.exists(uncompressed_path):
            with open(uncompressed_path, "r", encoding="utf-8") as f:
                uncompressed_data = json.load(f)
        else:
            uncompressed_data = {"entries": []}
    except (json.JSONDecodeError, OSError):
        uncompressed_data = {"entries": []}
        
    uncompressed_data.setdefault("entries", [])
    
    # Avoid duplicate appends if marked multiple times
    exists = any(e["id"] == entry["id"] for e in uncompressed_data["entries"])
    if not exists:
        uncompressed_data["entries"].append({
            "id": entry["id"],
            "validated": True,
            "author": entry["author"],
            "content": entry["content"],
            "kind": entry.get("kind", "event")
        })
        
        try:
            with open(uncompressed_path, "w", encoding="utf-8") as f:
                json.dump(uncompressed_data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass


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
    new_entry = {
        "id": entry_id,
        "validated": validated,
        "author": author,
        "content": content,
        "kind": kind,
    }
    data["entries"].append(new_entry)
    if validated:
        data["metadata"]["validated_since_condense"] += 1
        _append_to_uncompressed(path, new_entry)
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
                _append_to_uncompressed(path, entry)
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
    """Condense old validated entries into one validated summary entry.

    The protected_player_data block is NEVER touched by condensation.
    Only entries below the protected block are condensed.
    """
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
    """Pretty-print all validated entries (the trusted world state).

    Protected player data is shown first, followed by game history.
    """
    data = _read(path)
    protected = data.get("protected_player_data", "")
    result = ""
    if protected:
        result = f"[SYSTEM_PROTECTED_PLAYER_DATA]\n{protected}\n[/SYSTEM_PROTECTED_PLAYER_DATA]\n\n--- HISTORICO DE JOGO (COMPRESSIVEL) ---\n"
    result += format_entries(validated_entries(path))
    return result


def format_all(path: str) -> str:
    """Pretty-print every entry (validated and not)."""
    data = _read(path)
    protected = data.get("protected_player_data", "")
    result = ""
    if protected:
        result = f"[SYSTEM_PROTECTED_PLAYER_DATA]\n{protected}\n[/SYSTEM_PROTECTED_PLAYER_DATA]\n\n--- HISTORICO DE JOGO (COMPRESSIVEL) ---\n"
    result += format_entries(read_memory(path))
    return result


def get_protected_player_data(path: str) -> str:
    """Return the protected player data block, or empty string."""
    data = _read(path)
    return data.get("protected_player_data", "")

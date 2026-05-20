"""Memory Keeper sub-agent.

Given a raw piece of text (a player's action or a narrator's description),
the Memory Keeper:

    1. Asks the LLM to produce a CONCISE factual summary of the text.
    2. Appends the summary to the shared memory file as a new entry tagged
       "not validated" with the author's label (player name or "narrator").

The Memory Keeper does NOT decide whether the entry is true or consistent;
that is the Arbiter's job.
"""

from config import client, types, MODEL, send_chat_message
from agents.gm import memory_store


NO_RELEVANT_FACTS = "NO_RELEVANT_FACTS"
CONDENSE_AFTER_VALIDATED_ENTRIES = 10
RECENT_VALIDATED_ENTRIES_TO_KEEP = 4


SYSTEM_PROMPT = (
    "You are the Memory Keeper of a DnD Game Master. "
    "Extract only durable facts that can affect future story consistency. "
    "Keep state changes: location, party/NPC/enemy presence, objectives, "
    "inventory, consumed items, HP/conditions, discovered information, and "
    "unresolved consequences. Ignore mood, prose, repeated context, plans "
    "that were not executed, and details with no future impact. Do not write "
    "a normal paragraph just to fill space. Output terse factual lines only. "
    f"If there is no new durable fact, output exactly {NO_RELEVANT_FACTS}. "
    "Do not add commentary, opinions, narration, markdown, or labels."
)


CONDENSE_PROMPT = (
    "You condense a DnD campaign memory. Rewrite the old validated facts into "
    "a compact current-state memory. Preserve only facts still useful for "
    "future consistency: current location, active scene, living/present "
    "characters and enemies, unresolved objectives, inventory/HP/conditions, "
    "important discoveries, persistent world facts, and consequences that are "
    "still active. Remove facts that are resolved, obsolete, contradicted by "
    "newer facts, or only describe temporary intentions/actions. If an item "
    "was acquired and later consumed/lost, keep only the final state if it "
    "matters. Output terse factual lines only, no markdown or commentary."
)


def setup_mem_keeper():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )


def _has_relevant_facts(summary: str) -> bool:
    return bool(summary) and summary.strip().upper() != NO_RELEVANT_FACTS


def mem_keep(mk_chat, memory_path: str, author: str, raw_text: str) -> str | None:
    """Summarise ``raw_text`` and append a not-validated entry to memory.

    Parameters
    ----------
    mk_chat:        The Memory Keeper LLM chat.
    memory_path:    Path to the shared memory JSON file.
    author:         Label for the prompt's origin ("Thorin", "narrator", ...).
    raw_text:       The original prompt to summarise.

    Returns
    -------
    The id of the newly created entry (not yet validated).
    """
    response = send_chat_message(
        mk_chat,
        "Extract durable memory facts from the following text.\n\n"
        f"AUTHOR: {author}\n"
        f"TEXT:\n{raw_text}",
        remember=False,
    )
    summary = response.text.strip()
    print(f"Memory Keeper Summary: {summary}")
    if not _has_relevant_facts(summary):
        return None
    return memory_store.append_entry(
        path=memory_path,
        author=author,
        content=summary,
        validated=False,
    )


def should_condense(memory_path: str) -> bool:
    return (
        memory_store.validated_since_condense(memory_path)
        >= CONDENSE_AFTER_VALIDATED_ENTRIES
        and len(memory_store.validated_entries(memory_path))
        > RECENT_VALIDATED_ENTRIES_TO_KEEP
    )


def condense_memory(mk_chat, memory_path: str) -> str | None:
    entries = memory_store.validated_entries(memory_path)
    if len(entries) <= RECENT_VALIDATED_ENTRIES_TO_KEEP:
        return None

    old_entries = entries[:-RECENT_VALIDATED_ENTRIES_TO_KEEP]
    recent_entries = entries[-RECENT_VALIDATED_ENTRIES_TO_KEEP:]
    response = send_chat_message(
        mk_chat,
        f"{CONDENSE_PROMPT}\n\n"
        "OLD VALIDATED FACTS TO CONDENSE:\n"
        f"{memory_store.format_entries(old_entries)}\n\n"
        "RECENT VALIDATED FACTS TO KEEP SEPARATE FOR LOCAL CONTEXT:\n"
        f"{memory_store.format_entries(recent_entries)}\n\n"
        "Return the compact current-state memory for the old facts only.",
        remember=False,
    )
    summary = response.text.strip()
    if not _has_relevant_facts(summary):
        summary = "No older validated facts remain relevant."
    summary_id = memory_store.replace_validated_with_summary(
        memory_path,
        summary,
        keep_recent=RECENT_VALIDATED_ENTRIES_TO_KEEP,
    )
    if summary_id is not None:
        print(f"Memory condensed into summary entry: {summary_id}")
    return summary_id
"""Memory Keeper sub-agent.

Given a raw piece of text (a player's action or a narrator's description),
the Memory Keeper:

    1. Asks the LLM to produce a CONCISE factual summary of the text.
    2. Appends the summary to the shared memory file as a new entry tagged
       "not validated" with the author's label (player name or "narrator").

The Memory Keeper does NOT decide whether the entry is true or consistent;
that is the Arbiter's job.
"""

from config import client, types, MODEL
from agents.gm import memory_store


SYSTEM_PROMPT = (
    "You are the Memory Keeper of a DnD Game Master. "
    "Given a piece of text (from a player's action or the narrator's "
    "description), produce a CONCISE factual summary that keeps only the "
    "essential information: who did what, the items or weapons used, the "
    "location, who else is present, any HP or inventory changes, the enemies "
    "involved, and any other relevant world facts. "
    "Output ONLY the summary. "
    "Do not add commentary, opinions, narration, or markdown formatting."
)


def setup_mem_keeper():
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )


def mem_keep(mk_chat, memory_path: str, author: str, raw_text: str) -> str:
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
    response = mk_chat.send_message(
        "Summarise the following text, keeping only the essential facts.\n\n"
        f"AUTHOR: {author}\n"
        f"TEXT:\n{raw_text}"
    )
    summary = response.text.strip()
    return memory_store.append_entry(
        path=memory_path,
        author=author,
        content=summary,
        validated=False,
    )
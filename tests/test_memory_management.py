import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.gm import memory_store
from agents.gm.memory_keeper import (
    NO_RELEVANT_FACTS,
    condense_memory,
    mem_keep,
)


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeChat:
    def __init__(self, replies: list[str]):
        self.replies = replies
        self.messages = []

    def send_message(self, message: str, remember: bool = True):
        self.messages.append((message, remember))
        return FakeResponse(self.replies.pop(0))


def test_no_relevant_facts_are_not_written():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name

    memory_store.init_memory(path)
    chat = FakeChat([NO_RELEVANT_FACTS])

    entry_id = mem_keep(chat, path, author="party", raw_text="We wait.")

    assert entry_id is None
    assert memory_store.read_memory(path) == []
    assert chat.messages[0][1] is False


def test_condense_replaces_old_validated_entries_with_summary():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name

    memory_store.init_memory(path)
    for idx in range(6):
        memory_store.append_entry(
            path,
            author="narrator",
            content=f"fact {idx}",
            validated=True,
        )

    chat = FakeChat(["The party is in the crypt; the goblin threat is resolved."])
    summary_id = condense_memory(chat, path)
    entries = memory_store.read_memory(path)

    assert summary_id is not None
    assert len(entries) == 5
    assert entries[0]["kind"] == "summary"
    assert entries[0]["validated"] is True
    assert [e["content"] for e in entries[1:]] == [
        "fact 2",
        "fact 3",
        "fact 4",
        "fact 5",
    ]
    assert memory_store.validated_since_condense(path) == 0
    assert chat.messages[0][1] is False


def test_condense_does_not_absorb_unvalidated_entries():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name

    memory_store.init_memory(path)
    for idx in range(5):
        memory_store.append_entry(
            path,
            author="narrator",
            content=f"validated fact {idx}",
            validated=True,
        )
    pending_id = memory_store.append_entry(
        path,
        author="party",
        content="pending action",
        validated=False,
    )

    chat = FakeChat(["Only the older stable world facts remain relevant."])
    condense_memory(chat, path)
    pending = memory_store.get_entry(path, pending_id)

    assert pending is not None
    assert pending["validated"] is False
    assert pending["content"] == "pending action"


if __name__ == "__main__":
    test_no_relevant_facts_are_not_written()
    test_condense_replaces_old_validated_entries_with_summary()
    test_condense_does_not_absorb_unvalidated_entries()
    print("memory management smoke tests passed")

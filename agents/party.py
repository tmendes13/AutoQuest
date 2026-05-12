"""Party deliberation among player agents.

Whenever the Game Master emits a new message, the party runs an internal
discussion to converge on a single response before sending it back. The
algorithm is intentionally collaborative; it does not try to manufacture
conflict, only to simulate a real RPG party where members have different
ideas yet help each other.

Flow per deliberation round
---------------------------
1.  Each player independently drafts a proposal from the GM message and
    the validated memory (read-only). Players do not see each other's
    drafts at this stage.
2.  The drafts are compiled into a single labelled bundle.
3.  A random starter is picked. The starter synthesises a single starting
    group proposal from the bundle.
4.  The proposal circulates through the remaining players in an order
    that prioritises whoever has the most modification budget left (with
    random tie-breaking, so the order can vary between rounds). Each
    reviewer either:
        - APPROVES  -> the proposal stands and circulation continues.
        - MODIFIES  -> the reviewer spends one of their modification slots
                       and the proposal is replaced; circulation restarts
                       with everyone except the new modifier.
5.  The loop ends when a full circulation pass produces no modifications
    (implicit consensus) or when every eligible reviewer has run out of
    modification budget.
6.  The final proposal is returned as the party's official response to
    the GM.

Players READ the validated memory file but never write to it; only the
Memory Keeper writes.
"""

import random
from dataclasses import dataclass, field

from agents.gm import memory_store
from agents.player import APPROVE, propose, review, synthesize
from models.player import Player


MAX_MODIFICATIONS = 3


@dataclass
class DeliberationLog:
    """Transient record of one deliberation round.

    Useful for debugging, logging and (later) for evaluation. Not written
    to disk by default; the caller may persist it if they want to.
    """

    gm_message: str
    proposals: dict[str, str] = field(default_factory=dict)
    starter: str = ""
    history: list[str] = field(default_factory=list)
    final: str = ""


def _format_proposals(proposals: dict[str, str]) -> str:
    """Render the proposals bundle that the starter receives."""
    return "\n".join(f"[{name}]: {text}" for name, text in proposals.items())


def _build_queue(
    party: list[Player],
    last_modifier_name: str,
    remaining: dict[str, int],
) -> list[Player]:
    """Build the next circulation queue.

    Everyone except the last modifier, ordered by remaining budget
    descending. Ties are broken randomly so the circulation order varies
    between rounds and no single player dominates the conversation.
    """
    others = [p for p in party if p.name != last_modifier_name]
    random.shuffle(others)  # randomise ties
    others.sort(key=lambda p: -remaining[p.name])  # highest budget first
    return others


def deliberate(
    party: list[Player],
    gm_message: str,
    memory_path: str,
    max_modifications: int = MAX_MODIFICATIONS,
) -> tuple[str, DeliberationLog]:
    """Run a full party deliberation round.

    Returns ``(final_proposal_text, deliberation_log)``. The text is what
    the caller (usually the Game Master orchestrator) sends back to the
    Memory Keeper / Arbiter as the party's response.
    """
    log = DeliberationLog(gm_message=gm_message)
    validated_facts = memory_store.format_validated(memory_path)

    if not party:
        raise ValueError("Cannot deliberate with an empty party.")

    # ---- 1. Independent first drafts ------------------------------------
    print("\n--- Party deliberation: initial proposals ---")
    for player in party:
        text = propose(player, gm_message, validated_facts)
        log.proposals[player.name] = text
        print(f"  [{player.name}] proposes: {text}")

    # Corner case: only one player -> no circulation possible, their draft
    # is the final response.
    if len(party) == 1:
        only = party[0]
        log.starter = only.name
        log.final = log.proposals[only.name]
        log.history.append(f"[solo by {only.name}] {log.final}")
        print(f"\n--- Party FINAL response (solo) ---\n{log.final}\n")
        return log.final, log

    # ---- 2. Random starter synthesises ----------------------------------
    starter = random.choice(party)
    log.starter = starter.name
    print(f"\n--- Starter: {starter.name} ---")

    proposals_block = _format_proposals(log.proposals)
    current = synthesize(starter, gm_message, proposals_block, validated_facts)
    log.history.append(f"[synthesis by {starter.name}] {current}")
    print(f"\n[{starter.name} synthesises]:\n{current}\n")

    # ---- 3. Circulation -------------------------------------------------
    remaining = {p.name: max_modifications for p in party}
    last_modifier_name = starter.name
    pass_index = 0

    while True:
        pass_index += 1
        queue = _build_queue(party, last_modifier_name, remaining)
        if not queue:
            # Defensive: a fresh queue with no one is treated as consensus.
            break

        print(
            f"\n--- Circulation pass {pass_index} "
            f"(queue: {[p.name for p in queue]}, "
            f"remaining: { {p.name: remaining[p.name] for p in queue} }) ---"
        )
        modified = False

        for reviewer in queue:
            if remaining[reviewer.name] <= 0:
                print(
                    f"  [{reviewer.name}] has no modifications left "
                    "-> implicit APPROVE"
                )
                log.history.append(f"[implicit-approve by {reviewer.name}]")
                continue

            # Re-read facts every iteration in case anything changes
            # (defensive; in the synchronous flow it does not).
            validated_facts = memory_store.format_validated(memory_path)
            verdict, new_proposal = review(
                reviewer, gm_message, current, validated_facts
            )

            if verdict == APPROVE:
                print(f"  [{reviewer.name}] APPROVES")
                log.history.append(f"[approve by {reviewer.name}]")
                continue

            # MODIFY -> replace the current proposal and restart circulation.
            current = new_proposal
            remaining[reviewer.name] -= 1
            last_modifier_name = reviewer.name
            modified = True
            log.history.append(f"[modify by {reviewer.name}] {current}")
            print(
                f"  [{reviewer.name}] MODIFIES "
                f"(remaining {remaining[reviewer.name]}/{max_modifications}):"
                f"\n  {current}"
            )
            break  # restart circulation with the new modifier excluded

        if not modified:
            # A full pass without any modification = implicit consensus
            # (or everyone left in the queue was out of budget).
            break

    log.final = current
    log.history.append(f"[final] {current}")
    print(f"\n--- Party FINAL response ---\n{current}\n")
    return current, log

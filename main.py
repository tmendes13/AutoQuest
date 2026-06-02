from agents.gm.gm import (
    setup_gm,
    begin_campaign,
    run_turn,
    GMRetriesExhaustedError,
)
from agents.player import setup_agent
from agents.session_zero import run_session_zero
from models.player import Player
from models.dnd_class import Class


NUM_ROUNDS = 10


def _player_system_prompt(p: Player) -> str:
    """Common system prompt for every party member."""
    attrs_str = ", ".join(f"{k}:{v}" for k, v in p.attributes.items()) if p.attributes else ""
    attr_line = f" Attributes: {attrs_str}." if attrs_str else ""
    return (
        f"You play as {p.name}, a {p.race} {p.dnd_class.name}. "
        f"Personality: {p.personality}.{attr_line} "
        "You are part of a party of adventurers and you take part in short "
        "internal discussions before answering the Game Master. "
        "Speak in first person. Stay strictly consistent with the validated "
        "world facts you are given; only use items, weapons or abilities "
        "those facts say you have. "
        "Be concise (1 to 3 short sentences per turn). "
        "Be collaborative: do not create artificial conflict, but do speak "
        "up when you see a clearly better collective action."
    )


def main():
    # Ask user for number of players
    while True:
        try:
            num_players = int(input("Enter number of players (1-6): ").strip())
            if 1 <= num_players <= 6:
                break
            print("Please enter a number between 1 and 6.")
        except ValueError:
            print("Please enter a valid number.")

    # Create N players dynamically with placeholder info
    party = []
    for i in range(1, num_players + 1):
        p = Player(
            name=f"Player_{i}",
            race="Unknown",
            dnd_class=Class("Unknown", 10),
            personality="To be defined",
            max_hp=100,
        )
        party.append(p)

    for p in party:
        p.chat = setup_agent(_player_system_prompt(p))
        p.chat.agent_name = p.name

    # Setup GM (resets memory, creates sub-agents)
    gm = setup_gm()

    # ---- SESSION 0: Character Creation ----
    try:
        session_log = run_session_zero(party, gm, num_players)
    except RuntimeError as e:
        print(f"\n[Session 0] FAILED: {e}")
        return
    print(f"\n[Session 0 Result] Arbiter: {'VALID' if session_log.arbiter_valid else 'INVALID'}")
    print(f"[Session 0] Spokesperson: {session_log.spokesperson}")

    # Re-setup agent system prompts now that characters are defined
    for p in party:
        p.chat = setup_agent(_player_system_prompt(p))
        p.chat.agent_name = p.name

    # Begin the campaign with the opening narration
    situation = begin_campaign(gm)
    print(f"\n[GM-Narrator opening] {situation}\n")

    try:
        for round_idx in range(NUM_ROUNDS):
            print(f"\n=================== ROUND {round_idx + 1} ===================")
            situation = run_turn(gm, party, situation, turn_num=round_idx + 1)
            print(f"\n[GM-Narrator] {situation}\n")
            print("----------- END OF TURN -----------")
    except GMRetriesExhaustedError as e:
        print("\n=================== CAMPAIGN ABORTED ===================")
        print(f"[GM] {e}")
        print(f"[GM] Offending actor : {e.actor}")
        print(f"[GM] Last text       : {e.last_text}")
        print(f"[GM] Arbiter reason  : {e.last_reason}")
    finally:
        from metrics import get_metrics
        get_metrics().save()


if __name__ == "__main__":
    main()
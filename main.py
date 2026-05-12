from agents.gm.gm import (
    setup_gm,
    begin_campaign,
    run_turn,
    GMRetriesExhaustedError,
)
from agents.player import setup_agent
from models.player import Player
from models.dnd_class import Class


NUM_ROUNDS = 5


def _player_system_prompt(p: Player) -> str:
    """Common system prompt for every party member."""
    return (
        f"You play as {p.name}, a {p.race} {p.dnd_class.name}. "
        f"Personality: {p.personality}. "
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
    # Hardcoded party of two. The deliberation module is generic and scales
    # to any party size.
    thorin = Player(
        name="Thorin",
        race="Dwarf",
        dnd_class=Class("Warrior", 10),
        personality="Brave and impulsive",
        max_hp=40,
    )
    aelindra = Player(
        name="Aelindra",
        race="Elf",
        dnd_class=Class("Mage", 6),
        personality="Curious and calculative",
        max_hp=25,
    )
    party = [thorin, aelindra]

    for p in party:
        p.chat = setup_agent(_player_system_prompt(p))

    # The GM resets the shared memory file, sets up Narrator, Memory Keeper
    # and Arbiter, and seeds the memory with the validated campaign opening.
    gm = setup_gm()
    situation = begin_campaign(gm)
    print(f"\n[GM-Narrator opening] {situation}\n")

    try:
        for round_idx in range(NUM_ROUNDS):
            print(f"\n=================== ROUND {round_idx + 1} ===================")
            situation = run_turn(gm, party, situation)
            print(f"\n[GM-Narrator] {situation}\n")
            print("----------- END OF TURN -----------")
    except GMRetriesExhaustedError as e:
        print("\n=================== CAMPAIGN ABORTED ===================")
        print(f"[GM] {e}")
        print(f"[GM] Offending actor : {e.actor}")
        print(f"[GM] Last text       : {e.last_text}")
        print(f"[GM] Arbiter reason  : {e.last_reason}")


if __name__ == "__main__":
    main()
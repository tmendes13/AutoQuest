"""
Test the complete combat flow without running the full campaign.
"""

from models.creature import Creature
from models.player import Player
from models.dnd_class import Class
from agents.gm.simple_combat import (
    extract_combat_enemies,
    process_round,
    status_line,
)


def test_complete_combat_flow():
    """Test: GM creates enemies, players fight them."""
    print("=" * 60)
    print("COMBAT FLOW TEST: GM Narrates -> Enemies Appear -> Battle")
    print("=" * 60)
    
    # Setup
    thorin = Player(
        name="Thorin",
        race="Dwarf",
        dnd_class=Class("Warrior", 10),
        personality="Brave",
        max_hp=40,
    )
    aelindra = Player(
        name="Aelindra",
        race="Elf",
        dnd_class=Class("Mage", 6),
        personality="Clever",
        max_hp=25,
    )
    thorin.weapon = "1d8+1"
    aelindra.weapon = "1d6"
    party = [thorin, aelindra]
    
    # --- ROUND 1: Narrator creates enemies ---
    print("\n>>> ROUND 1: Combat Begins\n")
    narration_1 = """
    You round a corner and face a goblin encampment!
    A scarred goblin leader snarls at you, wielding a crude axe.
    Two smaller goblins draw their weapons.
    [COMBAT] Goblin Leader | 18 | 1d8+1
    [COMBAT] Goblin Scout | 10 | 1d6
    [COMBAT] Goblin Scout | 9 | 1d6
    """
    
    print(f"[Narrator]: {narration_1}\n")
    
    # Extract enemies
    enemies = extract_combat_enemies(narration_1)
    print(f"✅ {len(enemies)} enemies detected!\n")
    
    # Players attack
    print("[Players deliberate]")
    proposals = {
        "Thorin": "I charge at the leader and swing my axe!",
        "Aelindra": "I cast fireball at the scout next to him!",
    }
    
    # Combat round 1
    active_enemies = enemies
    print("\n>>> Combat Round 1\n")
    combat_log = process_round(party, active_enemies, proposals)
    print(combat_log)
    print(status_line(party, active_enemies))
    
    # Remove defeated
    active_enemies = [e for e in active_enemies if e.is_alive()]
    
    # --- ROUND 2: Remaining combat ---
    if active_enemies:
        print("\n\n>>> ROUND 2: Continuing Battle\n")
        proposals_2 = {
            "Thorin": "I keep attacking the leader!",
            "Aelindra": "I blast the scout again!",
        }
        
        combat_log = process_round(party, active_enemies, proposals_2)
        print(combat_log)
        print(status_line(party, active_enemies))
        
        active_enemies = [e for e in active_enemies if e.is_alive()]
    
    # --- ROUND 3: Final round ---
    if active_enemies:
        print("\n\n>>> ROUND 3: Finishing\n")
        proposals_3 = {
            "Thorin": "Final strike!",
            "Aelindra": "One more spell!",
        }
        
        combat_log = process_round(party, active_enemies, proposals_3)
        print(combat_log)
        print(status_line(party, active_enemies))
        
        active_enemies = [e for e in active_enemies if e.is_alive()]
    
    # Victory check
    print("\n" + "=" * 60)
    if not active_enemies:
        print("🎉 VICTORY! All goblins defeated!")
        print(f"Party survivors:")
        for p in party:
            status = "ALIVE" if p.current_hp > 0 else "DEAD"
            print(f"  {p.name}: {p.current_hp}/{p.max_hp} HP [{status}]")
    else:
        print("⚔️  BATTLE ONGOING")
        print(f"Remaining enemies: {len(active_enemies)}")
    print("=" * 60)


if __name__ == "__main__":
    test_complete_combat_flow()

"""Test combat action detection and processing."""

from agents.gm.combat_processor import (
    detect_combat_action,
    process_combat_actions,
    format_combat_status,
    find_creature_by_name,
)
from models.player import Player
from models.dnd_class import Class
from models.creature import Creature
from models.item import Item


def test_action_detection():
    """Test detecting combat actions in text."""
    print("\n=== COMBAT ACTION DETECTION ===\n")
    
    test_cases = [
        ("Thorin", "I step forward and attack the orc with my sword!"),
        ("Aelindra", "I cast a defensive spell to shield the party."),
        ("Thorin", "I'm trying to navigate the corridor carefully."),  # No combat
        ("Aelindra", "I heal Thorin's wounds with magic!"),
        ("Thorin", "I strike at the stone guardian with all my might!"),
    ]
    
    for player_name, proposal in test_cases:
        action = detect_combat_action(player_name, proposal)
        if action:
            print(f"✓ Detected: {action}")
        else:
            print(f"✗ No action: {player_name}: {proposal}")


def test_combat_processing():
    """Test full combat processing."""
    print("\n=== COMBAT PROCESSING ===\n")
    
    # Create party
    thorin = Player(
        name="Thorin",
        race="Dwarf",
        dnd_class=Class("Warrior", 10),
        personality="Brave",
        max_hp=40,
    )
    thorin.weapon = Item(name="Sword", description="Sword", damage="1d8+2")
    
    aelindra = Player(
        name="Aelindra",
        race="Elf",
        dnd_class=Class("Mage", 6),
        personality="Clever",
        max_hp=25,
    )
    
    party = [thorin, aelindra]
    
    # Create enemies
    orc = Creature(name="Orc Guard", max_hp=30)
    orc.weapon = Item(name="Axe", description="Battle axe", damage="1d8+1")
    
    enemies = [orc]
    
    # Print initial status
    print(format_combat_status(party, enemies))
    
    # Simulate 3 rounds of combat
    for round_num in range(3):
        print(f"\n--- ROUND {round_num + 1} ---\n")
        
        # Player proposals with combat actions
        proposals = {
            "Thorin": f"Round {round_num + 1}: I attack the orc with all my might!",
            "Aelindra": f"Round {round_num + 1}: I defend and prepare a spell.",
        }
        
        # Process combat
        enemies, combat_log = process_combat_actions(party, enemies, proposals)
        
        print(combat_log)
        print()
        
        if not enemies:
            print("🎉 All enemies defeated!")
            break
        
        # Enemy counterattack
        print("--- Enemy Turn ---")
        if enemies:
            # Simple: enemy attacks first party member
            from utils.combat import attack
            result = attack(enemies[0], party[0], ac=10)
            if result['hit']:
                print(f"⚔️  {result['attacker']} attacks {result['target']}: HIT! {result['damage']} damage")
            else:
                print(f"⚔️  {result['attacker']} attacks {result['target']}: MISS")
        
        print()
        print(format_combat_status(party, enemies))
        
        # Check if party is defeated
        if not any(p.is_alive() for p in party):
            print("💀 Party defeated!")
            break


def test_target_finding():
    """Test finding creatures by name."""
    print("\n=== CREATURE LOOKUP ===\n")
    
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
    
    orc = Creature(name="Orc Guard", max_hp=30)
    goblin = Creature(name="Goblin Scout", max_hp=8)
    
    party = [thorin, aelindra]
    enemies = [orc, goblin]
    
    test_names = ["thorin", "Aelindra", "orc", "goblin", "stone guardian", "unknown"]
    
    for name in test_names:
        found = find_creature_by_name(name, party, enemies)
        if found:
            print(f"✓ Found '{name}': {found.name}")
        else:
            print(f"✗ '{name}': not found")


if __name__ == "__main__":
    test_action_detection()
    test_combat_processing()
    test_target_finding()
    
    print("\n" + "="*50)
    print("✅ Combat processor tests completed!")
    print("="*50 + "\n")

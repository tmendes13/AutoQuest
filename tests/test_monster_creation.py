"""Test monster creation from GM narration."""

from agents.gm.monster_creator import extract_and_create_monster
from agents.gm.monster_validator import validate_monster, validate_monster_detailed


def test_monster_parsing():
    """Test parsing monster from text."""
    print("\n=== MONSTER PARSING ===\n")
    
    # Example GM narration with monster stats
    narration = """
    The heavy wooden door creaks open. Inside, you see an Orc Guard blocking 
    the path, eyes glowing red with rage. It hefts a large battle axe and 
    snarls at your approach.
    
    MONSTER_STATS:
    {
      "name": "Orc Guard",
      "max_hp": 28,
      "weapon_name": "Battle Axe",
      "weapon_damage": "1d10+2"
    }
    END_MONSTER_STATS
    
    What do you do?
    """
    
    success, monster, message = extract_and_create_monster(narration)
    
    print(f"[System] Parse result: {message}")
    if success:
        print(f"[System] Created: {monster.name}")
        print(f"[System]   HP: {monster.max_hp}")
        print(f"[System]   Weapon: {monster.weapon.name} ({monster.weapon.damage})")


def test_monster_validation():
    """Test monster stat validation."""
    print("\n=== MONSTER VALIDATION ===\n")
    
    # Parse and validate multiple monsters
    test_cases = [
        {
            "name": "Goblin Scout",
            "narration": """
            A small goblin jumps out from behind a crate!
            MONSTER_STATS:
            {"name": "Goblin Scout", "max_hp": 10, "weapon_name": "Dagger", "weapon_damage": "1d4+1"}
            END_MONSTER_STATS
            """,
        },
        {
            "name": "Dragon",
            "narration": """
            A MASSIVE dragon descends from the sky, wings blocking out the sun!
            MONSTER_STATS:
            {"name": "Ancient Red Dragon", "max_hp": 200, "weapon_name": "Dragon Breath", "weapon_damage": "5d8+3"}
            END_MONSTER_STATS
            """,
        },
        {
            "name": "Invalid Orc (too weak)",
            "narration": """
            An orc appears.
            MONSTER_STATS:
            {"name": "Weakling Orc", "max_hp": 3, "weapon_name": "Club", "weapon_damage": "1d6"}
            END_MONSTER_STATS
            """,
        },
        {
            "name": "Invalid Goblin (too strong weapon)",
            "narration": """
            A goblin appears.
            MONSTER_STATS:
            {"name": "Super Goblin", "max_hp": 10, "weapon_name": "Magical Sword", "weapon_damage": "3d12+5"}
            END_MONSTER_STATS
            """,
        },
    ]
    
    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")
        success, monster, msg = extract_and_create_monster(test_case['narration'])
        
        if success:
            is_valid, reason = validate_monster(monster)
            report = validate_monster_detailed(monster)
            
            print(f"  ✓ Created: {monster.name}")
            print(f"  Type: {report['creature_type']}")
            print(f"  HP: {report['hp']} (expected: {report['hp_expected_range']})")
            if 'damage_notation' in report:
                print(f"  Damage: {report['damage_notation']} (max: {report['max_damage']})")
            
            if is_valid:
                print(f"  ✓ VALID - {reason}")
            else:
                print(f"  ✗ INVALID - {reason}")
        else:
            print(f"  ✗ Failed to create: {msg}")
        
        print()


def test_full_combat_flow():
    """Test full combat with created monster."""
    print("\n=== FULL COMBAT FLOW ===\n")
    
    from models.player import Player
    from models.dnd_class import Class
    from utils.combat import attack
    
    # Parse and create monster from narration
    narration = """
    A goblin warrior emerges from the shadows!
    
    MONSTER_STATS:
    {
      "name": "Goblin Warrior",
      "max_hp": 12,
      "weapon_name": "Scimitar",
      "weapon_damage": "1d6+1"
    }
    END_MONSTER_STATS
    """
    
    success, goblin, msg = extract_and_create_monster(narration)
    print(f"[GM] {msg}\n")
    
    if not success:
        print("Failed to create monster")
        return
    
    # Validate
    is_valid, reason = validate_monster(goblin)
    if not is_valid:
        print(f"[Arbiter] Monster rejected: {reason}")
        return
    print(f"[Arbiter] {reason}\n")
    
    # Create player
    player = Player(
        name="Thorin",
        race="Dwarf",
        dnd_class=Class("Warrior", 10),
        personality="Brave",
        max_hp=40,
    )
    
    # Add weapon
    from models.item import Item
    sword = Item(name="Sword", description="Longsword", damage="1d8+2")
    player.weapon = sword
    
    print(f"[Narrator] Thorin faces {goblin.name}!\n")
    print(f"Before combat:")
    print(f"  {player.name}: {player.current_hp}/{player.max_hp} HP")
    print(f"  {goblin.name}: {goblin.current_hp}/{goblin.max_hp} HP\n")
    
    # Combat
    for round_num in range(4):
        print(f"--- ROUND {round_num + 1} ---")
        
        # Player attacks
        result = attack(player, goblin, ac=10)
        if result['hit']:
            print(f"  {player.name} attacks! Roll {result['attack_roll']}: HIT! {result['damage']} damage")
        else:
            print(f"  {player.name} attacks! Roll {result['attack_roll']}: MISS")
        
        if not goblin.is_alive():
            print(f"\n  {goblin.name} defeated!\n")
            break
        
        # Monster attacks
        result = attack(goblin, player, ac=10)
        if result['hit']:
            print(f"  {goblin.name} attacks! Roll {result['attack_roll']}: HIT! {result['damage']} damage")
        else:
            print(f"  {goblin.name} attacks! Roll {result['attack_roll']}: MISS")
        
        if not player.is_alive():
            print(f"\n  {player.name} defeated!\n")
            break
        
        print()
    
    print(f"Final state:")
    print(f"  {player.name}: {player.current_hp}/{player.max_hp} HP")
    print(f"  {goblin.name}: {goblin.current_hp}/{goblin.max_hp} HP")


if __name__ == "__main__":
    test_monster_parsing()
    test_monster_validation()
    test_full_combat_flow()
    
    print("\n" + "="*50)
    print("✅ All monster creation tests completed!")
    print("="*50 + "\n")

"""Simple example of dice rolling and combat."""

from models.player import Player
from models.creature import Creature
from models.dnd_class import Class
from models.item import Item
from utils.dice import roll, roll_attack, roll_damage
from utils.combat import attack


def example_dice_rolling():
    """Show dice rolling examples."""
    print("\n=== DICE ROLLING ===")
    print(f"1d6:     {roll('1d6')}")
    print(f"2d8+2:   {roll('2d8+2')}")
    print(f"3d6-1:   {roll('3d6-1')}")
    print(f"Attack:  {roll_attack(bonus=2)}")
    print(f"Damage:  {roll_damage('1d8+1')}")


def example_combat_player_vs_monster():
    """Show combat example: Player vs Monster created by GM."""
    print("\n=== COMBAT: PLAYER vs MONSTER ===\n")
    
    # Create a player
    warrior = Player(
        name="Thorin",
        race="Dwarf",
        dnd_class=Class("Warrior", 10),
        personality="Brave",
        max_hp=40,
    )
    
    # Create a monster dynamically (as GM would)
    # The GM can create any creature with name, max_hp, and weapon
    orc = Creature(
        name="Orc Warrior",
        max_hp=30,
    )
    
    # Add weapons
    sword = Item(name="Sword", description="A longsword", damage="1d8+2")
    warrior.weapon = sword
    
    club = Item(name="Club", description="A wooden club", damage="1d6")
    orc.weapon = club
    
    print(f"Before combat:")
    print(f"  {warrior.name}: {warrior.current_hp}/{warrior.max_hp} HP")
    print(f"  {orc.name}: {orc.current_hp}/{orc.max_hp} HP\n")
    
    # Combat rounds
    for round_num in range(5):
        print(f"--- ROUND {round_num + 1} ---")
        
        # Thorin attacks monster
        result = attack(warrior, orc, ac=10)
        if result['hit']:
            print(f"  {warrior.name} attacks! Roll {result['attack_roll']} vs AC {result['ac']}: HIT!")
            print(f"    Damage: {result['damage_roll']} = {result['damage']}")
        else:
            print(f"  {warrior.name} attacks! Roll {result['attack_roll']} vs AC {result['ac']}: MISS")
        
        if not orc.is_alive():
            print(f"\n  {orc.name} is defeated!")
            break
        
        # Monster attacks player
        result = attack(orc, warrior, ac=10)
        if result['hit']:
            print(f"  {orc.name} attacks! Roll {result['attack_roll']} vs AC {result['ac']}: HIT!")
            print(f"    Damage: {result['damage_roll']} = {result['damage']}")
        else:
            print(f"  {orc.name} attacks! Roll {result['attack_roll']} vs AC {result['ac']}: MISS")
        
        if not warrior.is_alive():
            print(f"\n  {warrior.name} is defeated!")
            break
        
        print()
    
    print(f"\nAfter combat:")
    print(f"  {warrior.name}: {warrior.current_hp}/{warrior.max_hp} HP")
    print(f"  {orc.name}: {orc.current_hp}/{orc.max_hp} HP")


def example_gm_creates_monster():
    """Example: How GM can create monsters dynamically."""
    print("\n=== HOW GM CREATES MONSTERS ===\n")
    
    # The GM (LLM) decides there's a goblin in the scene
    # It creates a simple Creature object
    goblin = Creature(
        name="Goblin Scout",
        max_hp=8,
    )
    goblin.weapon = Item(name="Dagger", description="A sharp dagger", damage="1d4+1")
    
    # The GM can also create more complex monsters
    dragon = Creature(
        name="Red Dragon",
        max_hp=150,
    )
    dragon.weapon = Item(name="Dragon's Breath", description="Magical fire breath", damage="4d6")
    
    print(f"GM created: {goblin.name} ({goblin.max_hp} HP)")
    print(f"  Weapon: {goblin.weapon.name} ({goblin.weapon.damage})")
    print()
    print(f"GM created: {dragon.name} ({dragon.max_hp} HP)")
    print(f"  Weapon: {dragon.weapon.name} ({dragon.weapon.damage})")


if __name__ == "__main__":
    example_dice_rolling()
    example_combat_player_vs_monster()
    example_gm_creates_monster()

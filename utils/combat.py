"""Simple combat system."""

from models.creature import Creature
from models.item import Item
from utils.dice import roll_attack, roll_damage


def attack(attacker: Creature, target: Creature, ac: int = 10) -> dict:
    """Resolve an attack between any two creatures (players, monsters, etc).
    
    Parameters
    ----------
    attacker : Creature
        The creature attacking (Player, Monster, NPC, etc)
    target : Creature  
        The creature being attacked
    ac : int
        Target's armor class (default 10)
    
    Returns
    -------
    dict with attack details and result
    """
    attack_roll = roll_attack(bonus=0)
    hit = attack_roll.result >= ac
    
    result = {
        'attacker': attacker.name,
        'target': target.name,
        'attack_roll': attack_roll.result,
        'ac': ac,
        'hit': hit,
        'damage_roll': None,
        'damage': 0,
    }
    
    if hit:
        # Damage from weapon or unarmed (1d4)
        weapon = attacker.weapon
        damage_notation = weapon.damage if weapon else "1d4"
        damage_roll = roll_damage(damage_notation)
        damage = damage_roll.result
        
        result['damage_roll'] = damage_roll
        result['damage'] = damage
        
        # Apply damage
        target.take_damage(damage)
    
    return result

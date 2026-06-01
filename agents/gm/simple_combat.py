"""Ultra-simple combat integration for GM.

Just detects keywords (attack, heal, defend) and resolves actions.
No validation, no extraction, no complexity.
"""

import re
from models.creature import Creature
from models.player import Player
from utils.dice import roll_attack, roll_damage


def parse_combat_line(line: str) -> tuple[bool, Creature | None]:
    """Parse a [COMBAT] line and create Creature.
    
    Format: [COMBAT] Monster_Name | HP_amount | weapon_damage
    Example: [COMBAT] Goblin | 12 | 1d6
    
    Returns: (success: bool, creature: Creature or None)
    """
    line = line.strip()
    if not line.startswith("[COMBAT]"):
        return False, None
    
    # Extract content after [COMBAT]
    content = line[8:].strip()  # Remove "[COMBAT]"
    
    # Split by |
    parts = [p.strip() for p in content.split("|")]
    if len(parts) != 3:
        return False, None
    
    name, hp_str, weapon = parts
    
    try:
        hp = int(hp_str)
    except ValueError:
        return False, None
    
    # Create Creature
    creature = Creature(name=name, max_hp=hp, weapon=weapon)
    return True, creature


def extract_combat_enemies(narration: str) -> list[Creature]:
    """Extract all [COMBAT] lines from narration and create Creatures.
    
    Returns list of Creatures found (empty if none).
    """
    enemies = []
    for line in narration.split("\n"):
        success, creature = parse_combat_line(line)
        if success:
            enemies.append(creature)
    return enemies


def resolve_player_action(player: Player, enemy: Creature, proposal: str) -> str:
    """Check if player proposed an attack/heal and resolve it.
    
    Returns description of what happened.
    """
    proposal_lower = proposal.lower()
    
    # ✨ DEAD PLAYERS CAN'T ACT
    if not player.is_alive():
        return f"{player.name} is unconscious and cannot act."
    
    # --- ATTACK ---
    if any(word in proposal_lower for word in ["attack", "strike", "hit", "swing", "slash"]):
        if not enemy.is_alive():
            return f"{player.name} tries to attack {enemy.name}, but it's already dead."
        
        # Attack roll: 1d20 + derived from hit die (d6=+1, d8=+2, d10=+3, d12=+4)
        hit_die_bonus = max(1, (player.dnd_class.hit_die - 4) // 2)
        attack_roll = roll_attack(hit_die_bonus)
        ac = 10  # Default AC
        hit = attack_roll.result >= ac
        
        if hit:
            # Roll damage from player's weapon
            damage_roll = roll_damage(player.weapon if player.weapon else "1d6")
            damage = damage_roll.result
            enemy.take_damage(damage)
            return (
                f"🗡️  {player.name} attacks {enemy.name}! "
                f"(Roll: {attack_roll.result} vs AC {ac}) HIT! "
                f"Damage: {damage} ({damage_roll.notation}). "
                f"{enemy.name} HP: {enemy.current_hp}/{enemy.max_hp}"
            )
        else:
            return (
                f"🗡️  {player.name} attacks {enemy.name}! "
                f"(Roll: {attack_roll.result} vs AC {ac}) MISS!"
            )
    
    # --- HEAL ---
    elif any(word in proposal_lower for word in ["heal", "cure", "mend", "restore"]):
        # Heal self or another party member
        heal_amount = roll_damage("1d8").result
        old_hp = player.current_hp
        player.heal(heal_amount)
        return (
            f"✨ {player.name} casts a healing spell! "
            f"Restored {player.current_hp - old_hp} HP. "
            f"Now at {player.current_hp}/{player.max_hp}"
        )
    
    # --- DEFEND ---
    elif any(word in proposal_lower for word in ["defend", "block", "shield", "parry", "dodge"]):
        return f"🛡️  {player.name} takes a defensive stance."
    
    # No combat action
    return None


def process_round(party: list[Player], enemies: list[Creature], proposals: dict[str, str]) -> str:
    """Process one round of combat.
    
    proposals is dict of {player_name: proposal_text}
    Returns combat log as string.
    """
    if not enemies:
        return ""
    
    log_lines = []
    
    # Process each player's action
    for player in party:
        proposal = proposals.get(player.name, "")
        if not proposal:
            continue
        
        # Try to attack primary enemy (first alive one)
        alive_enemies = [e for e in enemies if e.is_alive()]
        if alive_enemies:
            result = resolve_player_action(player, alive_enemies[0], proposal)
            if result:
                log_lines.append(result)
    
    # Remove defeated enemies
    alive_enemies = [e for e in enemies if e.is_alive()]
    
    # Enemies counter-attack (distribute among alive party members) ✨
    if alive_enemies:
        alive_party = [p for p in party if p.is_alive()]
        if alive_party:
            for i, enemy in enumerate(alive_enemies):
                # Rotate attacks among alive party members, not just first
                target = alive_party[i % len(alive_party)]
                damage_roll = roll_damage(enemy.weapon if enemy.weapon else "1d6")
                damage = damage_roll.result
                target.take_damage(damage)
                log_lines.append(
                    f"⚔️  {enemy.name} counter-attacks {target.name}! "
                    f"Damage: {damage}. {target.name} HP: {target.current_hp}/{target.max_hp}"
                )
    
    return "\n".join(log_lines)


def status_line(party: list[Player], enemies: list[Creature]) -> str:
    """Print current combat status."""
    lines = []
    lines.append("\n📊 COMBAT STATUS:")
    lines.append("Party:")
    for p in party:
        pct = max(0, int(100 * p.current_hp / p.max_hp))
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        status = "❌ DEAD" if not p.is_alive() else ""
        lines.append(f"  {p.name:12} [{bar}] {p.current_hp:3}/{p.max_hp:3} {status}".rstrip())
    
    lines.append("Enemies:")
    for e in enemies:
        if e.is_alive():
            pct = int(100 * e.current_hp / e.max_hp)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            lines.append(f"  {e.name:12} [{bar}] {e.current_hp:3}/{e.max_hp:3}")
        else:
            lines.append(f"  {e.name:12} [DEAD]")
    
    return "\n".join(lines)

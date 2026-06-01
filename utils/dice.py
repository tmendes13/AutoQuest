"""Simple dice rolling for D&D."""

import random
import re
from typing import Tuple


class DiceRoll:
    """Result of a dice roll."""
    
    def __init__(self, notation: str, result: int, rolls: list[int], modifier: int):
        self.notation = notation
        self.result = result
        self.rolls = rolls
        self.modifier = modifier
    
    def __str__(self) -> str:
        if self.modifier != 0:
            sign = "+" if self.modifier > 0 else "-"
            return f"{self.notation}: {self.rolls} {sign} {abs(self.modifier)} = {self.result}"
        return f"{self.notation}: {self.rolls} = {self.result}"


def parse_dice_notation(notation: str) -> Tuple[int, int, int]:
    """Parse D&D dice notation like '1d6' or '2d8+3'."""
    notation = notation.replace(" ", "").lower()
    match = re.match(r"^(\d+)d(\d+)([\+\-]\d+)?$", notation)
    if not match:
        raise ValueError(f"Invalid dice notation: {notation}")
    
    num_dice = int(match.group(1))
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    
    return num_dice, die_size, modifier


def roll(notation: str) -> DiceRoll:
    """Roll dice using D&D notation. Example: '1d6', '2d8+3', '3d6-1'."""
    num_dice, die_size, modifier = parse_dice_notation(notation)
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    
    return DiceRoll(notation, total, rolls, modifier)


def roll_attack(bonus: int = 0) -> DiceRoll:
    """Roll attack (d20 + bonus)."""
    notation = f"1d20+{bonus}" if bonus > 0 else f"1d20{bonus}" if bonus < 0 else "1d20"
    return roll(notation)


def roll_damage(notation: str) -> DiceRoll:
    """Roll damage."""
    return roll(notation)

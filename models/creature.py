"""Base creature class for both players and monsters."""

from dataclasses import dataclass, field
from typing import Optional
from models.item import Item


@dataclass
class Creature:
    """Base class for any creature (player, monster, NPC, etc)."""
    
    name: str
    max_hp: int
    current_hp: int = 0
    weapon: Optional[Item] = None
    
    def __post_init__(self):
        self.current_hp = self.max_hp
    
    def is_alive(self):
        return self.current_hp > 0
    
    def take_damage(self, amount):
        self.current_hp = max(0, self.current_hp - amount)
        print(f"{self.name} took {amount} damage. HP: {self.current_hp}/{self.max_hp}")
    
    def heal(self, amount):
        self.current_hp = min(self.current_hp + amount, self.max_hp)
        print(f"{self.name} has healed for {amount} HP. HP: {self.current_hp}/{self.max_hp}")

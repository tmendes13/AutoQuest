from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Item:
    name: str
    description: str
    damage: Optional[str] = None        # Weapons
    heal: Optional[str] = None          # Potions
    resistance: Optional[str] = None    # Armor
from dataclasses import dataclass, field
from typing import Optional
from models.item import Item
from models.dnd_class import Class
from models.creature import Creature


@dataclass
class Player(Creature):
    race: str = ""
    dnd_class: Optional[Class] = None
    personality: str = ""
    inventory: list[Item] = field(default_factory=list)
    armor: Optional[Item] = None
    chat: object = field(init=False, default=None)
    diary: str = ""

    def __post_init__(self):
        super().__post_init__()

    def add_item(self, item: Item):
        self.inventory.append(item)
        print(f"{self.name} obtained: {item.name}")

    def status(self):
        weapon = self.weapon.name if self.weapon else "None"
        armor  = self.armor.name if self.armor else "None"
        items = ", ".join(i.name for i in self.inventory) or "Empty"

        return(
            f"{self.name} ({self.race} {self.dnd_class.name}) | "
            f"HP: {self.current_hp}/{self.max_hp} | "
            #f"CA: {self.armor_class} | "
            f"Weapon: {weapon} | Armor: {armor} | "
            f"Inventory: {items}"
        )

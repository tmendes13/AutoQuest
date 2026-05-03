from dataclasses import dataclass, field
from typing import Optional
from models.item import Item
from models.dnd_class import Class


@dataclass
class Player:
    name: str
    race: str
    dnd_class: Class
    personality: str
    max_hp: int 
    current_hp: int = 0
    # armor class?
    inventory: list[Item] = field(default_factory=list)
    weapon: Optional[Item] = None
    armor: Optional[Item] = None
    chat: object = field(init=False, default=None)

    def __post_init__(self):
        self.current_hp = self.max_hp

    def is_alive(self):
        if self.current_hp > 0:
            return True

    def heal(self, amount):
        self.current_hp += amount
        print(f"{self.name} has healed for {amount} HP. HP: {self.current_hp}/{self.max_hp}")

    def take_damage(self, amount):
        self.current_hp -= amount
        print(f"{self.name} took {amount} damage. HP: {self.current_hp}/{self.max_hp}")

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
            f"Iventory: {items}"
        )

from models.item import Item
from models.dnd_class import Class
from models.player import Player

# Criar objetos de teste
espada = Item(name="Espada Longa", descripion="Uma espada afiada", damage="1d8")
guerreiro_class = Class(name="Guerreiro", hit_die=10)

# Testar Player
p = Player(name="Aragorn", race="Humano", dnd_class=guerreiro_class, 
           personality="Nobre", max_hp=20, current_hp=20)

p.add_item(espada)
print(p.status())

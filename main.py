from agents.gm import *
from agents.player import *
from google import genai
from config import client
from models.player import Player
from models.dnd_class import *

def main():
    thorin = Player(name="Thorin", race="Dwarf", dnd_class=Class("Warrior", 10), personality="Brave and impulsive", max_hp=40)
    aelindra = Player(name="Aelindra", race="Elf", dnd_class=Class("Mage", 6), personality="Curious and calculative", max_hp=25)
    players = [thorin, aelindra]

    # Dar chat a cada player
    for player in players:
        player.chat = setup_agent(
            f"You play as {player.name}, a {player.race} {player.dnd_class.name}. "
            f"Personality: {player.personality}. Answer in first person."
        )

    # Iniciar GM e campanha
    gm_chat = setup_gm()
    situation = start_campaign(gm_chat)
    print(f"\n GM: {situation}\n")

    # Game loop
    for round in range(5):
        actions = []

        for player in players:
            response = act(player, situation)
            print(f"{player.name}: {response}\n")
            actions.append(f"{player.name}: {response}")

        situation = narrate(gm_chat, actions)
        print(f"\n GM: {situation}\n")
        print("----------- END OF TURN -----------")

main()
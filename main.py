from agents.gm.narrator import *
from agents.gm.memory_keeper import *
from agents.gm.arbiter import *
from agents.player import *
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
    narrator_chat = setup_narrator()
    mem_keeper_chat = setup_mem_keeper()
    arbiter_chat = setup_arbiter()
    situation = start_campaign(narrator_chat)
    print(f"\n GM: {situation}\n")

    # Game loop
    for round in range(5):
        actions = []

        for player in players:
            response = act(player, situation)
            print(f"{player.name}: {response}\n")
            actions.append(f"{player.name}: {response}")
        print("------------------- PLAYERS ACTED -------------------")
        memory = mem_keep(mem_keeper_chat, actions)
        print(f"Memory Keeper -> Arbiter")
        decision  = decide(arbiter_chat, memory)
        print(f"Arbiter -> Narrator")
        situation = narrate(narrator_chat, memory)

        print(f"\n GM: {situation}\n")
        print("----------- END OF TURN -----------")

if __name__ == "__main__":
    main()
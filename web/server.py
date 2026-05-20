import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'autoquest-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

game_running = False

def emit_event(event_type, data):
    """Emit a game event to the frontend via WebSocket."""
    socketio.emit('game_event', {'type': event_type, **data})
    time.sleep(0.3)  # Small delay so UI can render smoothly

def run_game():
    """Run the game loop, emitting events instead of printing."""
    global game_running
    game_running = True

    from agents.gm.narrator import setup_narrator, start_campaign, narrate
    from agents.gm.memory_keeper import setup_mem_keeper, mem_keep
    from agents.gm.arbiter import setup_arbiter, decide
    from agents.player import setup_agent, act
    from models.player import Player
    from models.dnd_class import Class

    thorin = Player(name="Thorin", race="Dwarf", dnd_class=Class("Warrior", 10), personality="Brave and impulsive", max_hp=40)
    aelindra = Player(name="Aelindra", race="Elf", dnd_class=Class("Mage", 6), personality="Curious and calculative", max_hp=25)
    players = [thorin, aelindra]

    # Emit player info
    for player in players:
        emit_event('player_info', {
            'name': player.name,
            'race': player.race,
            'class': player.dnd_class.name,
            'personality': player.personality,
            'hp': player.current_hp,
            'max_hp': player.max_hp,
        })

    # Setup agents
    for player in players:
        player.chat = setup_agent(
            f"You play as {player.name}, a {player.race} {player.dnd_class.name}. "
            f"Personality: {player.personality}. Answer in first person."
        )

    narrator_chat = setup_narrator()
    mem_keeper_chat = setup_mem_keeper()
    arbiter_chat = setup_arbiter()

    emit_event('system', {'message': 'Campaign starting...'})

    situation = start_campaign(narrator_chat)
    emit_event('narration', {'message': situation})

    # Game loop
    for round_num in range(5):
        emit_event('round_start', {'round': round_num + 1})
        actions = []

        for player in players:
            emit_event('player_thinking', {'name': player.name})
            response = act(player, situation)
            emit_event('player_action', {
                'name': player.name,
                'action': response,
                'hp': player.current_hp,
                'max_hp': player.max_hp,
            })
            actions.append(f"{player.name}: {response}")

        emit_event('phase', {'phase': 'memory_keeper', 'message': 'Memory Keeper is recording events...'})
        memory = mem_keep(mem_keeper_chat, actions)
        emit_event('gm_agent', {'agent': 'Memory Keeper', 'message': memory})

        emit_event('phase', {'phase': 'arbiter', 'message': 'Arbiter is evaluating actions...'})
        decision = decide(arbiter_chat, memory)
        emit_event('gm_agent', {'agent': 'Arbiter', 'message': decision})

        emit_event('phase', {'phase': 'narrator', 'message': 'Narrator is crafting the story...'})
        situation = narrate(narrator_chat, memory)
        emit_event('narration', {'message': situation})

        emit_event('round_end', {'round': round_num + 1})

    emit_event('game_over', {'message': 'The campaign has concluded!'})
    game_running = False


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('start_game')
def handle_start_game():
    global game_running
    if not game_running:
        thread = threading.Thread(target=run_game, daemon=True)
        thread.start()
    else:
        emit('game_event', {'type': 'system', 'message': 'Game is already running!'})


if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5050, debug=False)

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time

from agents.gm.gm import (
    setup_gm,
    begin_campaign,
    run_turn,
    GMRetriesExhaustedError,
)
from agents.player import setup_agent
from agents.session_zero import run_session_zero
from models.player import Player
from models.dnd_class import Class
from main import _player_system_prompt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'autoquest-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

game_running = False
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MEMORY_PATH = os.path.join(PROJECT_ROOT, "memory", "memory.json")

def emit_event(event_type, data):
    """Emit a game event to the frontend via WebSocket."""
    socketio.emit('game_event', {'type': event_type, **data})
    time.sleep(0.3)  # Small delay so UI can render smoothly

NUM_ROUNDS = 20


def run_game(num_players):
    """Run the game loop, emitting events instead of printing."""
    global game_running
    game_running = True

    players = []
    for i in range(1, num_players + 1):
        p = Player(name=f"Player_{i}", race="Unknown", dnd_class=Class("Unknown", 10), personality="To be defined", max_hp=100)
        players.append(p)

    for player in players:
        player.chat = setup_agent(_player_system_prompt(player))
        player.chat.agent_name = player.name

    gm = setup_gm(MEMORY_PATH)

    try:
        session_log = run_session_zero(players, gm, num_players, on_event=emit_event)
    except RuntimeError as e:
        emit_event('system', {'message': f'Session 0 failed: {e}'})
        emit_event('game_over', {'message': 'Session 0 failed. Could not create valid characters.'})
        game_running = False
        return

    for player in players:
        player.chat = setup_agent(_player_system_prompt(player))
        player.chat.agent_name = player.name

    for player in players:
        emit_event('player_info', {
            'name': player.name,
            'race': player.race,
            'class': player.dnd_class.name,
            'personality': player.personality,
            'hp': player.current_hp,
            'max_hp': player.max_hp,
        })

    emit_event('system', {'message': 'Campaign starting...'})

    situation = begin_campaign(gm)
    emit_event('narration', {'message': situation})

    try:
        for round_num in range(NUM_ROUNDS):
            emit_event('round_start', {'round': round_num + 1})
            situation = run_turn(gm, players, situation, on_event=emit_event, turn_num=round_num + 1)
            emit_event('round_end', {'round': round_num + 1})
    except GMRetriesExhaustedError as e:
        emit_event('game_over', {'message': 'Campaign Aborted.'})
    finally:
        from metrics import get_metrics
        get_metrics().save()
        game_running = False
        return

    emit_event('game_over', {'message': 'The campaign has concluded!'})
    game_running = False


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('start_game')
def handle_start_game(data=None):
    global game_running
    if not game_running:
        num_players = 2
        if data and isinstance(data, dict) and 'num_players' in data:
            try:
                num_players = int(data['num_players'])
                num_players = max(1, min(6, num_players))
            except (ValueError, TypeError):
                num_players = 2
        thread = threading.Thread(target=run_game, args=(num_players,), daemon=True)
        thread.start()
    else:
        emit('game_event', {'type': 'system', 'message': 'Game is already running!'})


if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5050, debug=False)

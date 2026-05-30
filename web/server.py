import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import threading
import time

from agents.gm.narrator import setup_narrator, start_campaign, narrate
from agents.gm.memory_keeper import setup_mem_keeper, mem_keep, condense_memory
from agents.gm.arbiter import setup_arbiter, arbitrate
from agents.player import setup_agent, act, reflect
from models.player import Player
from models.dnd_class import Class
from agents.gm import memory_store
from agents.party import deliberate
from main import _player_system_prompt

app = Flask(__name__)
app.config['SECRET_KEY'] = 'autoquest-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

game_running = False
MEMORY_PATH = "web_memory.json"

def emit_event(event_type, data):
    """Emit a game event to the frontend via WebSocket."""
    socketio.emit('game_event', {'type': event_type, **data})
    time.sleep(0.3)  # Small delay so UI can render smoothly

def run_game():
    """Run the game loop, emitting events instead of printing."""
    global game_running
    game_running = True

    memory_store.init_memory(MEMORY_PATH)

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

    # Setup agents with the complete _player_system_prompt
    for player in players:
        player.chat = setup_agent(_player_system_prompt(player))

    narrator_chat = setup_narrator()
    mem_keeper_chat = setup_mem_keeper()
    arbiter_chat = setup_arbiter()

    emit_event('system', {'message': 'Campaign starting...'})

    situation = start_campaign(narrator_chat)
    entry_id = mem_keep(mem_keeper_chat, MEMORY_PATH, "narrator", situation)
    if entry_id is not None:
        memory_store.mark_validated(MEMORY_PATH, entry_id)
    emit_event('narration', {'message': situation})

    # Game loop
    for round_num in range(5):
        emit_event('round_start', {'round': round_num + 1})
        
        # ---- 1. Party deliberates (with retries on invalidation) ------------
        party_response = ""
        is_valid = False
        arbiter_text = ""
        
        for attempt in range(1, 4):
            emit_event('system', {'message': f'Party deliberation (attempt {attempt}/3)...'})
            
            party_response, log = deliberate(players, situation, MEMORY_PATH)
            
            # Animate drafts
            for p_name, draft in log.proposals.items():
                emit_event('player_thinking', {'name': p_name})
                time.sleep(0.4)
                emit_event('gm_agent', {'agent': f'{p_name} Draft', 'message': draft})
            
            # Animate deliberation steps
            for step in log.history:
                if "synthesis" in step:
                    parts = step.split("]", 1)
                    header = parts[0][1:]
                    content = parts[1].strip() if len(parts) > 1 else ""
                    emit_event('gm_agent', {'agent': header.title(), 'message': content})
                elif "modify" in step:
                    parts = step.split("]", 1)
                    header = parts[0][1:]
                    content = parts[1].strip() if len(parts) > 1 else ""
                    emit_event('gm_agent', {'agent': header.title(), 'message': content})
                elif "approve" in step:
                    header = step[1:-1]
                    emit_event('gm_agent', {'agent': header.title(), 'message': 'Proposal approved.'})
                time.sleep(0.4)
                
            emit_event('player_action', {
                'name': 'Party',
                'action': party_response,
                'hp': thorin.current_hp,
                'max_hp': thorin.max_hp,
            })
            
            emit_event('phase', {'phase': 'memory_keeper', 'message': 'Memory Keeper is recording party action...'})
            entry_id = mem_keep(mem_keeper_chat, MEMORY_PATH, "party", party_response)
            
            if entry_id is not None:
                memory_entry = memory_store.get_entry(MEMORY_PATH, entry_id)
                emit_event('gm_agent', {'agent': 'Memory Keeper', 'message': f"Recorded fact: {memory_entry['content']}"})
                
                emit_event('phase', {'phase': 'arbiter', 'message': 'Arbiter is evaluating party action...'})
                is_valid, arbiter_text = arbitrate(arbiter_chat, MEMORY_PATH, entry_id)
                emit_event('gm_agent', {'agent': 'Arbiter Decision', 'message': arbiter_text})
            else:
                emit_event('gm_agent', {'agent': 'Memory Keeper', 'message': 'No relevant facts to record.'})
                is_valid = True
                arbiter_text = "No new durable facts to validate."
                
            if is_valid:
                # Condensation check
                if memory_store.validated_since_condense(MEMORY_PATH) >= 10:
                    emit_event('phase', {'phase': 'memory_keeper', 'message': 'Memory Keeper is condensing old memories...'})
                    condense_id = condense_memory(mem_keeper_chat, MEMORY_PATH)
                    if condense_id:
                        cond_entry = memory_store.get_entry(MEMORY_PATH, condense_id)
                        emit_event('gm_agent', {'agent': 'Memory Keeper (Condensation)', 'message': f"Condensed old memories: {cond_entry['content']}"})
                break
            else:
                emit_event('system', {'message': f'Party action rejected by Arbiter: {arbiter_text.strip()}'})
                memory_store.delete_unvalidated(MEMORY_PATH)
                time.sleep(1.0)
        else:
            emit_event('system', {'message': 'Party exhausted deliberation retries due to hallucinations.'})
            emit_event('game_over', {'message': 'Campaign Aborted.'})
            game_running = False
            return
            
        # ---- 2. Narrator narrates (with retries on invalidation) ------------
        narration = ""
        is_valid_narr = False
        narr_arbiter_text = ""
        
        for attempt in range(1, 4):
            emit_event('phase', {'phase': 'narrator', 'message': f'Narrator is crafting the story (attempt {attempt}/3)...'})
            narration = narrate(narrator_chat, MEMORY_PATH)
            
            emit_event('phase', {'phase': 'memory_keeper', 'message': 'Memory Keeper is recording narration...'})
            entry_id = mem_keep(mem_keeper_chat, MEMORY_PATH, "narrator", narration)
            
            if entry_id is not None:
                memory_entry = memory_store.get_entry(MEMORY_PATH, entry_id)
                emit_event('gm_agent', {'agent': 'Memory Keeper', 'message': f"Recorded fact: {memory_entry['content']}"})
                
                emit_event('phase', {'phase': 'arbiter', 'message': 'Arbiter is evaluating narration...'})
                is_valid_narr, narr_arbiter_text = arbitrate(arbiter_chat, MEMORY_PATH, entry_id)
                emit_event('gm_agent', {'agent': 'Arbiter Decision', 'message': narr_arbiter_text})
            else:
                emit_event('gm_agent', {'agent': 'Memory Keeper', 'message': 'No relevant facts to record.'})
                is_valid_narr = True
                
            if is_valid_narr:
                # Condensation check
                if memory_store.validated_since_condense(MEMORY_PATH) >= 10:
                    emit_event('phase', {'phase': 'memory_keeper', 'message': 'Memory Keeper is condensing old memories...'})
                    condense_id = condense_memory(mem_keeper_chat, MEMORY_PATH)
                    if condense_id:
                        cond_entry = memory_store.get_entry(MEMORY_PATH, condense_id)
                        emit_event('gm_agent', {'agent': 'Memory Keeper (Condensation)', 'message': f"Condensed old memories: {cond_entry['content']}"})
                break
            else:
                emit_event('system', {'message': f'Narrator description rejected by Arbiter: {narr_arbiter_text.strip()}'})
                memory_store.delete_unvalidated(MEMORY_PATH)
                time.sleep(1.0)
        else:
            emit_event('system', {'message': 'Narrator exhausted narration retries due to hallucinations.'})
            emit_event('game_over', {'message': 'Campaign Aborted.'})
            game_running = False
            return
            
        # ---- 3. Players reflect privately on the validated turn ------------
        emit_event('phase', {'phase': 'players', 'message': 'Players are reflecting privately...'})
        validated_facts = memory_store.format_validated(MEMORY_PATH)
        for player in players:
            reflect(player, narration, validated_facts)
            emit_event('gm_agent', {'agent': f"{player.name}'s Diary", 'message': player.diary})
            time.sleep(0.4)
            
        emit_event('narration', {'message': narration})
        situation = narration
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

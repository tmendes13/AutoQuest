#!/usr/bin/env python3
"""Simple test: run campaign WITH and WITHOUT diaries, compare metrics."""

import os
import sys
import json
import shutil

def reset_state():
    """Clean up state files and metrics."""
    for f in ["memory/memory.json", "logs/metrics.json"]:
        if os.path.exists(f):
            try:
                os.remove(f)
            except:
                pass
    os.makedirs("logs", exist_ok=True)
    
    # Reset metrics singleton
    import metrics
    metrics._metrics = metrics.Metrics()

def run_campaign_direct(use_diaries, num_players=2, num_turns=10):
    """Run campaign directly in this process."""
    reset_state()
    
    # Set flag
    import agents.player
    agents.player.USE_DIARIES = use_diaries
    
    # Import main components
    from agents.gm.gm import setup_gm, begin_campaign, run_turn, GMRetriesExhaustedError
    from agents.player import setup_agent
    from agents.session_zero import run_session_zero
    from models.player import Player
    from models.dnd_class import Class
    from main import _player_system_prompt
    
    # Create players
    party = []
    for i in range(1, num_players + 1):
        p = Player(
            name=f"Player_{i}",
            race="Unknown",
            dnd_class=Class("Unknown", 10),
            personality="To be defined",
            max_hp=100,
        )
        party.append(p)

    for p in party:
        p.chat = setup_agent(_player_system_prompt(p))
        p.chat.agent_name = p.name

    gm = setup_gm()

    # Session 0
    try:
        session_log = run_session_zero(party, gm, num_players)
    except RuntimeError as e:
        print(f"Session 0 failed: {e}")
        return False

    for p in party:
        p.chat = setup_agent(_player_system_prompt(p))
        p.chat.agent_name = p.name

    situation = begin_campaign(gm)

    # Run campaign (num_turns only)
    try:
        for round_idx in range(num_turns):
            situation = run_turn(gm, party, situation, turn_num=round_idx + 1)
    except GMRetriesExhaustedError:
        pass
    finally:
        from metrics import get_metrics
        get_metrics().save()
    
    return True

print("\n=== Test 1: WITH diaries (3 turns) ===")
if run_campaign_direct(True, num_turns=10):
    if os.path.exists("logs/metrics.json"):
        shutil.copy("logs/metrics.json", "logs/metrics_with_diaries.json")
        with open("logs/metrics.json") as f:
            m_with = json.load(f)
        print(f"✓ Completed {m_with['turns']} turns")

print("\n=== Test 2: WITHOUT diaries (3 turns) ===")
if run_campaign_direct(False, num_turns=10):
    if os.path.exists("logs/metrics.json"):
        shutil.copy("logs/metrics.json", "logs/metrics_without_diaries.json")
        with open("logs/metrics.json") as f:
            m_without = json.load(f)
        print(f"✓ Completed {m_without['turns']} turns")

if 'm_with' in locals() and 'm_without' in locals():
    print("\n" + "="*60)
    print("COMPARISON")
    print("="*60)
    llm_diff = ((m_without['avg_llm_calls_per_turn'] - m_with['avg_llm_calls_per_turn']) / m_with['avg_llm_calls_per_turn'] * 100) if m_with['avg_llm_calls_per_turn'] > 0 else 0
    invalid_diff = ((m_without['avg_arbiter_invalid_rate'] - m_with['avg_arbiter_invalid_rate']) / m_with['avg_arbiter_invalid_rate'] * 100) if m_with['avg_arbiter_invalid_rate'] > 0 else 0
    modify_diff = ((m_without['avg_modify_rounds_per_turn'] - m_with['avg_modify_rounds_per_turn']) / m_with['avg_modify_rounds_per_turn'] * 100) if m_with['avg_modify_rounds_per_turn'] > 0 else 0
    
    print(f"Avg LLM calls:        {m_with['avg_llm_calls_per_turn']:.1f} → {m_without['avg_llm_calls_per_turn']:.1f} ({llm_diff:+.0f}%)")
    print(f"Arbiter INVALID rate: {m_with['avg_arbiter_invalid_rate']:.1%} → {m_without['avg_arbiter_invalid_rate']:.1%} ({invalid_diff:+.0f}%)")
    print(f"Avg MODIFY rounds:    {m_with['avg_modify_rounds_per_turn']:.1f} → {m_without['avg_modify_rounds_per_turn']:.1f} ({modify_diff:+.0f}%)")
    print("="*60)

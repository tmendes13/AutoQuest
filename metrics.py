"""Simple metrics tracker - just 3 metrics."""

import json
import os
from collections import defaultdict

class Metrics:
    def __init__(self):
        self.arbiter_invalids_per_turn = []
        self.modify_rounds_per_turn = []
        self.llm_calls_per_turn = []
        self.current_turn = 0
        self.current_turn_invalids = 0
        self.current_turn_modifies = 0
        self.last_llm_call_count = 0
    
    def start_turn(self, turn_num):
        """Start tracking a new turn."""
        self.current_turn = turn_num
        self.current_turn_invalids = 0
        self.current_turn_modifies = 0
        
        # Snapshot current LLM call count
        import config
        if config.TOKEN_PATH and os.path.exists(config.TOKEN_PATH):
            try:
                with open(config.TOKEN_PATH) as f:
                    data = json.load(f)
                self.last_llm_call_count = data.get("total_general", {}).get("calls", 0)
            except:
                self.last_llm_call_count = 0
    
    def record_arbiter_invalid(self):
        """Record an INVALID decision from arbiter."""
        self.current_turn_invalids += 1
    
    def record_modify(self):
        """Record a MODIFY round in deliberation."""
        self.current_turn_modifies += 1
    
    def end_turn(self):
        """End turn and save metrics."""
        self.arbiter_invalids_per_turn.append(self.current_turn_invalids)
        self.modify_rounds_per_turn.append(self.current_turn_modifies)
        
        # Get LLM calls delta this turn from config
        import config
        delta_calls = 0
        if config.TOKEN_PATH and os.path.exists(config.TOKEN_PATH):
            try:
                with open(config.TOKEN_PATH) as f:
                    data = json.load(f)
                current_count = data.get("total_general", {}).get("calls", 0)
                delta_calls = current_count - self.last_llm_call_count
            except:
                delta_calls = 0
        
        self.llm_calls_per_turn.append(delta_calls)
    
    def save(self):
        """Save summary to file."""
        turns_count = len(self.arbiter_invalids_per_turn)
        if turns_count == 0:
            return
        
        summary = {
            "turns": turns_count,
            "avg_llm_calls_per_turn": sum(self.llm_calls_per_turn) / turns_count,
            "avg_arbiter_invalid_rate": sum(self.arbiter_invalids_per_turn) / (turns_count * 2) if turns_count > 0 else 0,  # 2 checks per turn (party + narrator)
            "avg_modify_rounds_per_turn": sum(self.modify_rounds_per_turn) / turns_count,
            "per_turn": [
                {
                    "turn": i+1,
                    "llm_calls": self.llm_calls_per_turn[i] if i < len(self.llm_calls_per_turn) else 0,
                    "arbiter_invalids": self.arbiter_invalids_per_turn[i],
                    "modify_rounds": self.modify_rounds_per_turn[i],
                }
                for i in range(turns_count)
            ]
        }
        
        os.makedirs("logs", exist_ok=True)
        with open("logs/metrics.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print("\n" + "="*60)
        print("METRICS SUMMARY")
        print("="*60)
        print(f"Turns completed: {turns_count}")
        print(f"Avg LLM calls per turn: {summary['avg_llm_calls_per_turn']:.1f}")
        print(f"Avg Arbiter INVALID rate: {summary['avg_arbiter_invalid_rate']:.1%}")
        print(f"Avg MODIFY rounds per turn: {summary['avg_modify_rounds_per_turn']:.1f}")
        print("="*60 + "\n")


_metrics = Metrics()

def get_metrics():
    return _metrics

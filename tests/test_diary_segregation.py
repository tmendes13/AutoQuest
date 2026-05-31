import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.player import Player
from models.dnd_class import Class
from agents.player import (
    get_player_diary_path,
    init_diaries,
    save_diaries,
    load_diaries,
)

def test_diary_segregation():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        memory_path = f.name
    
    try:
        # Create test players
        thorin = Player(
            name="Thorin",
            race="Dwarf",
            dnd_class=Class("Warrior", 10),
            personality="Brave",
            max_hp=40,
        )
        aelindra = Player(
            name="Aelindra",
            race="Elf",
            dnd_class=Class("Mage", 6),
            personality="Smart",
            max_hp=25,
        )
        party = [thorin, aelindra]

        # Set unique diaries and traits
        thorin.diary = "Thorin's secret thought: I love beer."
        thorin.traits = {"mood": "eager", "trust_in_party": "high", "primary_goal": "find relic", "risk_tolerance": "high", "recent_concern": "shadows"}
        aelindra.diary = "Aelindra's secret thought: Magic is cool."
        aelindra.traits = {"mood": "curious", "trust_in_party": "neutral", "primary_goal": "study the sigils", "risk_tolerance": "low", "recent_concern": "ward stability"}

        # Verify path names
        thorin_path = get_player_diary_path(memory_path, thorin.name)
        aelindra_path = get_player_diary_path(memory_path, aelindra.name)
        
        assert "diary_Thorin.json" in thorin_path
        assert "diary_Aelindra.json" in aelindra_path
        assert thorin_path != aelindra_path

        # Save diaries
        save_diaries(memory_path, party)

        # Check files exist on disk
        assert os.path.exists(thorin_path)
        assert os.path.exists(aelindra_path)

        # Clear memory state of players in memory
        thorin.diary = ""
        thorin.traits = {}
        aelindra.diary = ""
        aelindra.traits = {}

        # Load and verify
        load_diaries(memory_path, party)
        assert thorin.diary == "Thorin's secret thought: I love beer."
        assert thorin.traits["mood"] == "eager"
        assert thorin.traits["risk_tolerance"] == "high"
        assert aelindra.diary == "Aelindra's secret thought: Magic is cool."
        assert aelindra.traits["mood"] == "curious"
        assert aelindra.traits["risk_tolerance"] == "low"

        # Init (delete) and verify deletion
        init_diaries(memory_path)
        assert not os.path.exists(thorin_path)
        assert not os.path.exists(aelindra_path)

        print("Diary segregation smoke tests passed successfully!")

    finally:
        # Clean up memory path file
        if os.path.exists(memory_path):
            os.remove(memory_path)

if __name__ == "__main__":
    test_diary_segregation()

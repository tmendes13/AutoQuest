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

        # Set unique diaries
        thorin.diary = "Thorin's secret thought: I love beer."
        aelindra.diary = "Aelindra's secret thought: Magic is cool."

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
        aelindra.diary = ""

        # Load and verify
        load_diaries(memory_path, party)
        assert thorin.diary == "Thorin's secret thought: I love beer."
        assert aelindra.diary == "Aelindra's secret thought: Magic is cool."

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

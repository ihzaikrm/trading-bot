import json
import os
from datetime import datetime
from pathlib import Path

class StateManager:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        (self.data_dir / "checkpoints").mkdir(exist_ok=True)
        self.state_file = self.data_dir / "session_state.json"
    
    def load_state(self):
        if not self.state_file.exists():
            return self._initialize_new_session()
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except:
            return self._initialize_new_session()
    
    def save_checkpoint(self, next_state, checkpoint_data):
        try:
            # Save checkpoint data
            checkpoint_file = self.data_dir / "checkpoints" / f"{next_state.lower()}_checkpoint.json"
            with open(checkpoint_file, 'w') as f:
                json.dump({"timestamp": datetime.utcnow().isoformat(), "data": checkpoint_data}, f)
            
            # Update state
            state = {
                "current_state": next_state,
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
            return True
        except Exception as e:
            print(f"Checkpoint error: {e}")
            return False
    
    def _initialize_new_session(self):
        return {
            "current_state": "COLLECT", 
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        }

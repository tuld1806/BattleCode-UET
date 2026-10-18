from engine.base import GameEngine

class SampleEngine(GameEngine):
    def get_initial_state(self, p1, p2): return {}
    def get_player_view(self, state, p): return state
    def apply_action(self, state, p, a): return state
    def check_winner(self, state): return (None, 'ongoing')
    def is_action_valid(self, state, p, a): return True
    def get_max_turns(self): return 50
    def score_for_tiebreak(self, state, p): return 0.0

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from app.models.enums import Phase
from app.models.player import PlayerState
from app.models.events import NightAction

@dataclass
class GameState:
    """ゲームセッション全体のデータ保持クラス"""
    session_id: str
    players: Dict[str, PlayerState] = field(default_factory=dict)
    phase: Phase = Phase.SETUP
    day_count: int = 1
    night_actions: Dict[str, NightAction] = field(default_factory=dict)
    votes: Dict[str, str] = field(default_factory=dict)  # voter_id -> target_id
    last_night_results: Dict[str, str] = field(default_factory=dict)
    last_exiled_player_id: Optional[str] = None
    winner_faction: Optional[str] = None

    def add_player(self, player: PlayerState):
        self.players[player.id] = player

    def get_alive_players(self) -> List[PlayerState]:
        return [p for p in self.players.values() if p.alive]

    def reset_night_data(self):
        self.night_actions.clear()
        self.votes.clear()

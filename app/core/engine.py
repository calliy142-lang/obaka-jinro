from typing import Dict, Optional, Tuple
from app.models.enums import Phase, Faction
from app.models.events import NightAction
from app.core.state import GameState
from app.core.resolver import NightResolver

class GameEngine:
    """ゲームの進行・フェーズ管理・勝敗判定を統括するメインエンジン"""

    def __init__(self, state: GameState):
        self.state = state

    def submit_night_action(self, actor_id: str, target_id: str) -> bool:
        """夜の行動を受け付ける"""
        if self.state.phase != Phase.NIGHT:
            return False
        
        actor = self.state.players.get(actor_id)
        if not actor or not actor.alive:
            return False

        self.state.night_actions[actor_id] = NightAction(actor_id=actor_id, target_id=target_id)
        return True

    def check_and_process_night_end(self) -> bool:
        """生存者全員の夜行動が揃っていたら自動で夜を解決する"""
        alive_players = self.state.get_alive_players()
        if len(self.state.night_actions) >= len(alive_players):
            self.process_night()
            return True
        return False

    def process_night(self):
        """夜の解決を実行し、昼フェーズに移行する"""
        resolver = NightResolver(self.state.players)
        results, _ = resolver.resolve(self.state.night_actions)

        self.state.last_night_results = results
        self.state.phase = Phase.DAY
        self.state.reset_night_data()

        # 勝敗チェック
        self.check_win_condition()

    def submit_vote(self, voter_id: str, target_id: str) -> bool:
        """昼の投票を受け付ける"""
        if self.state.phase != Phase.VOTE:
            return False

        voter = self.state.players.get(voter_id)
        if not voter or not voter.alive:
            return False

        self.state.votes[voter_id] = target_id
        return True

    def process_voting(self) -> Optional[str]:
        """投票を集計して最多被投票者を追放し、夜フェーズへ移行する"""
        if not self.state.votes:
            self.state.phase = Phase.NIGHT
            self.state.day_count += 1
            return None

        # 得票数集計
        vote_counts: Dict[str, int] = {}
        for target_id in self.state.votes.values():
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1

        # 最多得票者の選出
        max_votes = max(vote_counts.values())
        top_targets = [p_id for p_id, count in vote_counts.items() if count == max_votes]

        exiled_id = None
        if len(top_targets) == 1:  # 同数の場合は不発
            exiled_id = top_targets[0]
            exiled_player = self.state.players.get(exiled_id)
            if exiled_player:
                exiled_player.alive = False

        self.state.last_exiled_player_id = exiled_id
        self.state.phase = Phase.NIGHT
        self.state.day_count += 1
        self.state.reset_night_data()

        self.check_win_condition()
        return exiled_id

    def check_win_condition(self) -> Optional[str]:
        """陣営の勝利判定（イノセント vs インポスター / ニュートラル）"""
        alive = self.state.get_alive_players()
        innocents = [p for p in alive if p.role_state.current_faction == Faction.INNOCENT]
        imposters = [p for p in alive if p.role_state.current_faction == Faction.IMPOSTER]
        neutrals = [p for p in alive if p.role_state.current_faction == Faction.NEUTRAL]

        # 勝利判定ロジック
        if not imposters and not neutrals and innocents:
            self.state.winner_faction = Faction.INNOCENT.value
            self.state.phase = Phase.ENDED
        elif len(imposters) >= len(innocents) + len(neutrals) and imposters:
            self.state.winner_faction = Faction.IMPOSTER.value
            self.state.phase = Phase.ENDED
        elif len(alive) == 1 and neutrals:
            self.state.winner_faction = Faction.NEUTRAL.value
            self.state.phase = Phase.ENDED

        return self.state.winner_faction

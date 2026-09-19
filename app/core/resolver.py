import random
from typing import Dict, List, Tuple
from app.models.enums import StatusEffectType, AbilityType
from app.models.player import PlayerState
from app.models.events import NightAction, Visit, KillEvent

class NightResolver:
    """夜行動の優先順位付き解決エンジン"""

    def __init__(self, players: Dict[str, PlayerState]):
        self.players = players

    def resolve(self, actions: Dict[str, NightAction]) -> Tuple[Dict[str, str], List[KillEvent]]:
        """
        夜行動を一括受領し、優先度順に解決して結果メッセージと死亡イベントを返す
        """
        visits: List[Visit] = []
        kill_events: List[KillEvent] = []
        results: Dict[str, str] = {}

        # --------------------------------------------------
        # Step 1: 訪問の確定 (Visit Tracking)
        # --------------------------------------------------
        for actor_id, action in actions.items():
            actor = self.players.get(actor_id)
            if not actor or not actor.alive:
                continue

            # バカ（Fool）は家を出ない＆能力が発動しない
            if actor.role_state.is_fool:
                continue

            role_def = actor.role_state.true_role
            if role_def.ability_type != AbilityType.NONE:
                visits.append(Visit(
                    actor_id=actor_id,
                    target_id=action.target_id,
                    leaves_house=role_def.leaves_house
                ))

        # --------------------------------------------------
        # Step 2: 妨害処理 (Police / Blockers)
        # --------------------------------------------------
        for actor_id, action in actions.items():
            actor = self.players.get(actor_id)
            if not actor or not actor.alive or actor.role_state.is_fool:
                continue

            if actor.role_state.true_role.id == "police":
                target = self.players.get(action.target_id)
                if target and target.alive:
                    target.add_status(StatusEffectType.POLICED)

        # --------------------------------------------------
        # Step 3: 殺害処理 (Killers / Attackers)
        # --------------------------------------------------
        for actor_id, action in actions.items():
            actor = self.players.get(actor_id)
            if not actor or not actor.alive or actor.role_state.is_fool:
                continue

            # ポリスに阻害されている場合は行動不可
            if actor.has_status(StatusEffectType.POLICED):
                continue

            role_def = actor.role_state.true_role
            if role_def.ability_type == AbilityType.ATTACK:
                kill_events.append(KillEvent(
                    attacker_id=actor_id,
                    target_id=action.target_id,
                    source_role_id=role_def.id
                ))

        # --------------------------------------------------
        # Step 4: 救出・保護処理 (Doctors / Protectors)
        # --------------------------------------------------
        for actor_id, action in actions.items():
            actor = self.players.get(actor_id)
            if not actor or not actor.alive or actor.role_state.is_fool:
                continue

            if actor.has_status(StatusEffectType.POLICED):
                continue

            if actor.role_state.true_role.id == "doctor":
                # ドクターが守った対象の殺害イベントを無効化
                for kill in kill_events:
                    if kill.target_id == action.target_id and kill.can_be_saved:
                        kill.saved = True

        # --------------------------------------------------
        # Step 5: 死亡確定処理
        # --------------------------------------------------
        for kill in kill_events:
            target = self.players.get(kill.target_id)
            if target and not kill.saved:
                target.alive = False

        # --------------------------------------------------
        # Step 6 & 7: 表示用結果の生成 & バカのダミーメッセージ変換
        # --------------------------------------------------
        dummy_messages = [
            "対象の家に怪しい動きは見られませんでした。",
            "能力の実行に成功しました。",
            "静かな夜でした。何も検出されませんでした。"
        ]

        for p_id, player in self.players.items():
            if not player.alive:
                results[p_id] = "あなたは無残にも倒されました。"
                continue

            # バカ（Fool）の場合はランダムな結果を返す
            if player.role_state.is_fool:
                results[p_id] = random.choice(dummy_messages)
            else:
                # ポリスに止められた場合
                if player.has_status(StatusEffectType.POLICED):
                    results[p_id] = "昨夜はポリスによって行動を阻止されました。"
                else:
                    results[p_id] = "無事に夜を過ごしました。"

        return results, kill_events

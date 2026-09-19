from dataclasses import dataclass, field
from typing import Optional, List
from app.models.roles import RoleDefinition
from app.models.enums import Faction, WinCondition, StatusEffectType

@dataclass
class PlayerRoleState:
    """プレイヤー個別の役職・能力状態"""
    true_role: RoleDefinition
    displayed_role: RoleDefinition
    current_faction: Faction
    current_win_condition: WinCondition
    uses_remaining: Optional[int] = None

    @property
    def is_fool(self) -> bool:
        """バカかどうかを判定"""
        return self.true_role.id == "fool"

    @property
    def can_use_ability(self) -> bool:
        """実際に能力が発動可能かを判定（バカは能力なし）"""
        if self.is_fool:
            return False
        if self.uses_remaining is not None and self.uses_remaining <= 0:
            return False
        return True

@dataclass
class PlayerState:
    """ゲーム中のプレイヤー個人の状態"""
    id: str
    name: str
    role_state: PlayerRoleState
    alive: bool = True
    last_target_id: Optional[str] = None
    status_effects: List[StatusEffectType] = field(default_factory=list)

    def add_status(self, effect: StatusEffectType):
        if effect not in self.status_effects:
            self.status_effects.append(effect)

    def remove_status(self, effect: StatusEffectType):
        if effect in self.status_effects:
            self.status_effects.remove(effect)

    def has_status(self, effect: StatusEffectType) -> bool:
        return effect in self.status_effects

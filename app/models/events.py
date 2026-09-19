from dataclasses import dataclass, field
from typing import Optional, List
from app.models.enums import StatusEffectType

@dataclass
class NightAction:
    """プレイヤーが夜に提出した行動指示"""
    actor_id: str
    target_id: str
    guessed_role_id: Optional[str] = None  # 魔術師などの予想用

@dataclass
class Visit:
    """訪問イベント（ルックアウト・トラッカー検知用）"""
    actor_id: str
    target_id: str
    leaves_house: bool = True  # 家を出る行動か（魔術師等はFalse）

@dataclass
class KillEvent:
    """殺害イベント（ドクター等の保護判定用）"""
    attacker_id: str
    target_id: str
    source_role_id: str
    can_be_blocked: bool = True
    can_be_saved: bool = True
    reveal_role_on_death: bool = True
    saved: bool = False  # ドクターにより保護されたか

@dataclass
class StatusEffect:
    """プレイヤーに付与された状態変化"""
    type: StatusEffectType
    target_id: str
    source_id: Optional[str] = None

@dataclass
class AbilityResult:
    """能力処理の実行結果"""
    success: bool
    consumes_use: bool = True
    message: str = ""

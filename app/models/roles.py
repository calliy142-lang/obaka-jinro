from dataclasses import dataclass
from typing import Optional, Dict
from app.models.enums import Faction, AbilityType, WinCondition

@dataclass(frozen=True)
class RoleDefinition:
    """役職の不変定義データ"""
    id: str
    name: str
    faction: Faction
    ability_type: AbilityType
    max_uses: Optional[int] = None       # Noneは無制限
    can_be_fooled: bool = True          # バカ化の対象になり得るか
    can_be_blocked: bool = True         # ポリス等で阻止可能か
    leaves_house: bool = True           # 行動時に自宅を出るか（ルックアウト検知用）
    win_condition: WinCondition = WinCondition.FACTION

# 役職マスターデータ
ROLE_DEFINITIONS: Dict[str, RoleDefinition] = {
    "doctor": RoleDefinition(
        id="doctor",
        name="ドクター",
        faction=Faction.INNOCENT,
        ability_type=AbilityType.VISIT,
    ),
    "police": RoleDefinition(
        id="police",
        name="ポリス",
        faction=Faction.INNOCENT,
        ability_type=AbilityType.VISIT,
    ),
    "fool": RoleDefinition(
        id="fool",
        name="バカ",
        faction=Faction.INNOCENT,
        ability_type=AbilityType.NONE,
        can_be_fooled=False,
        can_be_blocked=False,
        leaves_house=False,
    ),
    "killer": RoleDefinition(
        id="killer",
        name="シリアルキラー",
        faction=Faction.NEUTRAL,
        ability_type=AbilityType.ATTACK,
        win_condition=WinCondition.SOLO_KILL,
    ),
}

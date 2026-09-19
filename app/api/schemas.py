from pydantic import BaseModel
from typing import List, Optional
from app.models.enums import Phase

class ActionRequest(BaseModel):
    """夜行動または投票の送信用リクエスト"""
    actor_id: str
    target_id: str

class TargetInfo(BaseModel):
    """行動対象として選択可能な他プレイヤー情報"""
    id: str
    name: str

class PlayerViewResponse(BaseModel):
    """クライアント（フロントエンド）に返却する表示用プレイヤー状態"""
    id: str
    name: str
    displayed_role: str        # 表示上の役職名（バカの場合もポリス等に見える）
    alive: bool
    phase: Phase
    day_count: int
    action_submitted: bool     # 行動提出済みフラグ
    message: str               # 昨夜の結果またはアナウンス
    targets: List[TargetInfo]  # 行動・投票可能な生きている他プレイヤー
    winner_faction: Optional[str] = None

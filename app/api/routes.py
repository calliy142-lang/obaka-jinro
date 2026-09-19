from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.api.schemas import ActionRequest, PlayerViewResponse, TargetInfo
from app.core.room import room_manager
from app.models.roles import ROLE_DEFINITIONS
from app.models.player import PlayerState, PlayerRoleState

router = APIRouter(prefix="/api")

class CreateRoomResponse(BaseModel):
    room_code: str

class JoinRoomRequest(BaseModel):
    room_code: str
    player_name: str

class JoinRoomResponse(BaseModel):
    player_id: str
    room_code: str

@router.post("/room/create", response_model=CreateRoomResponse)
def create_room():
    """新しい部屋を作成"""
    code = room_manager.create_room()
    return CreateRoomResponse(room_code=code)

@router.post("/room/join", response_model=JoinRoomResponse)
def join_room(req: JoinRoomRequest):
    """部屋に参加し、プレイヤーを追加"""
    state = room_manager.get_room(req.room_code)
    if not state:
        raise HTTPException(status_code=404, detail="Room not found")

    p_id = f"p{len(state.players) + 1}"
    
    # 割り当て用デフォルト役職リスト（4人用例）
    default_roles = ["doctor", "police", "fool", "killer"]
    role_idx = len(state.players) % len(default_roles)
    true_role_id = default_roles[role_idx]
    
    # バカの場合は見た目をポリスにする
    disp_role_id = "police" if true_role_id == "fool" else true_role_id

    t_role = ROLE_DEFINITIONS[true_role_id]
    d_role = ROLE_DEFINITIONS[disp_role_id]
    
    r_state = PlayerRoleState(
        true_role=t_role,
        displayed_role=d_role,
        current_faction=t_role.faction,
        current_win_condition=t_role.win_condition,
    )
    
    state.add_player(PlayerState(id=p_id, name=req.player_name, role_state=r_state))
    return JoinRoomResponse(player_id=p_id, room_code=req.room_code.upper())

@router.get("/room/{room_code}/player/{player_id}", response_model=PlayerViewResponse)
def get_player_view(room_code: str, player_id: str):
    """プレイヤー表示情報の取得"""
    state = room_manager.get_room(room_code)
    if not state:
        raise HTTPException(status_code=404, detail="Room not found")

    player = state.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    alive_others = [
        TargetInfo(id=p.id, name=p.name)
        for p in state.get_alive_players()
        if p.id != player_id
    ]

    action_submitted = (
        player_id in state.night_actions if state.phase.value == "NIGHT"
        else player_id in state.votes
    )

    return PlayerViewResponse(
        id=player.id,
        name=player.name,
        displayed_role=player.role_state.displayed_role.name,
        alive=player.alive,
        phase=state.phase,
        day_count=state.day_count,
        action_submitted=action_submitted,
        message=state.last_night_results.get(player_id, ""),
        targets=alive_others,
        winner_faction=state.winner_faction,
    )

@router.post("/room/{room_code}/action")
async def submit_night_action(room_code: str, req: ActionRequest):
    """夜行動送信"""
    engine = room_manager.get_engine(room_code)
    if not engine:
        raise HTTPException(status_code=404, detail="Room not found")

    success = engine.submit_night_action(req.actor_id, req.target_id)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid action")

    if engine.check_and_process_night_end():
        await room_manager.notify_room_update(room_code)

    return {"status": "ok"}

@router.post("/room/{room_code}/vote")
async def submit_vote(room_code: str, req: ActionRequest):
    """投票送信"""
    engine = room_manager.get_engine(room_code)
    state = room_manager.get_room(room_code)
    if not engine or not state:
        raise HTTPException(status_code=404, detail="Room not found")

    success = engine.submit_vote(req.actor_id, req.target_id)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid vote")

    if len(state.votes) >= len(state.get_alive_players()):
        engine.process_voting()
        await room_manager.notify_room_update(room_code)

    return {"status": "ok"}

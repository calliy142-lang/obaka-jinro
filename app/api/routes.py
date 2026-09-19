import string
import random
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.room import room_manager, Player

router = APIRouter(prefix="/api/room", tags=["room"])

class JoinRoomReq(BaseModel):
    player_name: str

class StartGameReq(BaseModel):
    host_player_id: str

def generate_random_code(length=4) -> str:
    return ''.join(random.choices(string.ascii_uppercase, k=length))

@router.post("/create")
async def create_room():
    code = generate_random_code()
    while room_manager.get_room(code):
        code = generate_random_code()

    room = room_manager.create_room(code=code, host_id="")
    return {"room_code": room.room_code}

@router.post("/{room_code}/join")
async def join_room(room_code: str, req: JoinRoomReq):
    room = room_manager.get_room(room_code)
    if not room:
        room = room_manager.create_room(code=room_code, host_id="")

    p_id = str(uuid.uuid4())[:8]
    is_host = (len(room.players) == 0)

    if is_host:
        room.host_id = p_id

    player = Player(id=p_id, name=req.player_name, is_host=is_host)
    room.players[p_id] = player

    return {"room_code": room.room_code, "player_id": p_id}

@router.get("/{room_code}/player/{player_id}")
async def get_player_info(room_code: str, player_id: str):
    room = room_manager.get_room(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="部屋が存在しません")
    
    player = room.players.get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="プレイヤーが存在しません")

    targets = [{"id": p.id, "name": p.name} for p in room.players.values() if p.id != player_id]

    return {
        "displayed_role": player.displayed_role or "未定",
        "phase": room.phase,
        "day_count": 1,
        "alive": player.is_alive,
        "is_host": (room.host_id == player_id),
        "message": None,
        "winner_faction": None,
        "targets": targets,
        "action_submitted": False
    }

@router.post("/{room_code}/start")
async def start_game(room_code: str, req: StartGameReq):
    room = room_manager.get_room(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")

    try:
        room.start_game(req.host_player_id)
        return {"status": "ok", "phase": room.phase}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

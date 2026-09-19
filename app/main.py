import random
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

ROLES_INFO = {
    "バカ": {"camp": "innocent", "can_be_fool": False},
    "ドクター": {"camp": "innocent", "can_be_fool": True},
    "ねずみ": {"camp": "innocent", "can_be_fool": True},
    "ポリス": {"camp": "innocent", "can_be_fool": True},
    "トラッパー": {"camp": "innocent", "can_be_fool": True},
    "ルックアウト": {"camp": "innocent", "can_be_fool": True},
    "インベスティゲーター": {"camp": "innocent", "can_be_fool": True},
    "挑発者": {"camp": "innocent", "can_be_fool": False},
    "トラッカー": {"camp": "innocent", "can_be_fool": True},
    "ブレイマー": {"camp": "impostor", "can_be_fool": False},
    "クリーナー": {"camp": "impostor", "can_be_fool": False},
    "シリアルキラー": {"camp": "neutral", "can_be_fool": False},
    "ボマー": {"camp": "neutral", "can_be_fool": False},
    "サバイバー": {"camp": "neutral", "can_be_fool": False},
    "シーフ": {"camp": "neutral", "can_be_fool": False},
    "魔術師": {"camp": "neutral", "can_be_fool": False},
    "ゴースト": {"camp": "neutral", "can_be_fool": False},
}

class Player:
    def __init__(self, player_id: str, name: str, is_host: bool = False):
        self.id = player_id
        self.name = name
        self.is_host = is_host
        self.real_role = "ドクター"
        self.displayed_role = "ドクター"
        self.camp = "innocent"
        self.is_fool = False
        self.is_alive = True
        self.role_uses = 999

class Room:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.players: Dict[str, Player] = {}
        self.phase = "lobby"
        self.day_count = 1
        self.night_actions: Dict[str, dict] = {}
        self.votes: Dict[str, str] = {}
        self.night_reports: Dict[str, List[str]] = {}
        self.last_vote_result = ""
        self.result_text = ""

rooms: Dict[str, Room] = {}

class JoinRoomRequest(BaseModel):
    player_name: str

class ActionRequest(BaseModel):
    player_id: str
    target_id: Optional[str] = None
    extra_param: Optional[str] = None

class VoteRequest(BaseModel):
    player_id: str
    target_id: str

class HostStartRequest(BaseModel):
    host_player_id: str

@app.post("/api/room/create")
def create_room():
    code = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    while code in rooms:
        code = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    rooms[code] = Room(code)
    return {"room_code": code}

@app.post("/api/room/{room_code}/join")
def join_room(room_code: str, req: JoinRoomRequest):
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    if room.phase != "lobby":
        raise HTTPException(status_code=400, detail="ゲームが既に始まっています")
    
    player_id = str(uuid.uuid4())[:8]
    is_host = (len(room.players) == 0)
    player = Player(player_id, req.player_name, is_host)
    room.players[player_id] = player
    return {"player_id": player_id, "is_host": is_host}

@app.post("/api/room/{room_code}/start")
def start_game(room_code: str, req: HostStartRequest):
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    
    if req.host_player_id not in room.players or not room.players[req.host_player_id].is_host:
        raise HTTPException(status_code=403, detail="ホストのみが開始できます")

    players_list = list(room.players.values())
    p_count = len(players_list)
    if p_count < 3:
        raise HTTPException(status_code=400, detail="最低3人のプレイヤーが必要です")

    assign_roles_feign(players_list)

    room.phase = "night"
    room.night_actions.clear()
    room.night_reports = {p.id: [] for p in players_list}
    return {"message": "ゲームを開始しました"}

def assign_roles_feign(players: List[Player]):
    innocent_pool = ["ドクター", "ねずみ", "ポリス", "トラッパー", "ルックアウト", "インベスティゲーター", "挑発者", "トラッカー"]
    impostor_pool = ["ブレイマー", "クリーナー"]
    neutral_pool = ["シリアルキラー", "ボマー", "サバイバー", "シーフ", "魔術師", "ゴースト"]

    random.shuffle(players)
    total = len(players)
    
    imp_count = 1 if total <= 5 else 2
    neu_count = 1 if total >= 6 else 0
    inn_count = total - imp_count - neu_count

    chosen_roles = []
    chosen_roles.extend(random.sample(impostor_pool, imp_count))
    if neu_count > 0:
        chosen_roles.extend(random.sample(neutral_pool, neu_count))
    chosen_roles.extend(random.sample(innocent_pool, inn_count))

    innocent_indices = [i for i, r in enumerate(chosen_roles) if ROLES_INFO[r]["camp"] == "innocent" and ROLES_INFO[r]["can_be_fool"]]
    fool_index = random.choice(innocent_indices) if innocent_indices else -1

    uses_map = {"ねずみ": 1, "挑発者": 2, "ブレイマー": 2, "サバイバー": 3}

    for idx, player in enumerate(players):
        role_name = chosen_roles[idx]
        player.real_role = role_name
        player.camp = ROLES_INFO[role_name]["camp"]
        player.is_fool = False

        if idx == fool_index:
            player.is_fool = True
            fake_roles = [r for r in innocent_pool if ROLES_INFO[r]["can_be_fool"]]
            player.displayed_role = random.choice(fake_roles)
        else:
            player.displayed_role = role_name

        player.role_uses = uses_map.get(player.displayed_role, 999)

@app.get("/api/room/{room_code}/player/{player_id}")
def get_player_info(room_code: str, player_id: str):
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が存在しません")
    
    room = rooms[room_code]
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが存在しません")
    
    me = room.players[player_id]

    all_p = [{"id": p.id, "name": p.name, "is_host": p.is_host, "is_alive": p.is_alive} for p in room.players.values()]
    other_p = [p for p in all_p if p["id"] != player_id and p["is_alive"]]

    reports = list(room.night_reports.get(player_id, []))
    if room.last_vote_result:
        reports = [f"【投票結果】 {room.last_vote_result}"] + reports

    night_report_text = "<br>".join(reports) if reports else "特に報告はありません。"

    return {
        "phase": room.phase,
        "is_host": me.is_host,
        "displayed_role": me.displayed_role,
        "is_alive": me.is_alive,
        "all_players": all_p,
        "other_players": other_p,
        "night_report": night_report_text,
        "result": getattr(room, "result_text", "")
    }

@app.post("/api/room/{room_code}/action")
def send_action(room_code: str, req: ActionRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "night":
        raise HTTPException(status_code=400, detail="現在は夜フェーズではありません")
    
    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="行動できない状態です")

    room.night_actions[req.player_id] = {
        "target_id": req.target_id,
        "extra_param": req.extra_param
    }

    alive_players = [p for p in room.players.values() if p.is_alive]
    if len(room.night_actions) >= len(alive_players):
        resolve_night_phase(room)

    return {"message": "夜の行動を受理しました"}

def resolve_night_phase(room: Room):
    actions = room.night_actions
    players = room.players
    room.night_reports = {p_id: [] for p_id in players}

    blocked_players = set()
    trapped_houses = set()
    kills = set()
    healed = set()

    for p_id, act in actions.items():
        p = players[p_id]
        if p.real_role == "トラッパー" and not p.is_fool and act["target_id"]:
            trapped_houses.add(act["target_id"])

    for p_id, act in actions.items():
        p = players[p_id]
        target_id = act["target_id"]
        
        if p.real_role == "ポリス" and not p.is_fool and target_id:
            blocked_players.add(target_id)
            room.night_reports[target_id].append("昨夜、ポリスに外出を阻止されました。")

        if target_id in trapped_houses and p.real_role != "シリアルキラー":
            blocked_players.add(p_id)
            room.night_reports[p_id].append("昨夜、トラップにかかって能力を使用できませんでした。")

    for p_id, act in actions.items():
        if p_id in blocked_players:
            continue
        
        p = players[p_id]
        target_id = act["target_id"]
        target = players.get(target_id) if target_id else None

        if p.displayed_role == "ドクター":
            if not p.is_fool and target:
                healed.add(target_id)
            if target:
                room.night_reports[target_id].append("昨夜、ドクターがあなたの家を訪問しました。")

        elif p.displayed_role == "インベスティゲーター":
            if target:
                if p.is_fool:
                    room.night_reports[p_id].append(f"調査結果: {target.name} は 「ドクター」 または 「ブレイマー」 のどちらかです。")
                else:
                    room.night_reports[p_id].append(f"調査結果: {target.name} は 「{target.real_role}」 または 「ブレイマー」 のどちらかです。")

        elif p.real_role == "シリアルキラー" and target:
            kills.add(target_id)

        elif p.real_role == "魔術師" and target:
            guess = act.get("extra_param")
            if target.real_role == guess:
                kills.add(target_id)
            else:
                kills.add(p_id)

    final_kills = kills - healed
    for k_id in final_kills:
        players[k_id].is_alive = False
        room.night_reports[k_id].append("あなたは昨夜キルされました。")

    room.phase = "vote"
    room.night_actions.clear()

@app.post("/api/room/{room_code}/vote")
def send_vote(room_code: str, req: VoteRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "vote":
        raise HTTPException(status_code=400, detail="現在は投票フェーズではありません")

    room.votes[req.player_id] = req.target_id

    alive_players = [p for p in room.players.values() if p.is_alive]
    if len(room.votes) >= len(alive_players):
        resolve_vote_phase(room)

    return {"message": "投票を受理しました"}

def resolve_vote_phase(room: Room):
    counts: Dict[str, int] = {}
    for voter_id, target_id in room.votes.items():
        if target_id:
            counts[target_id] = counts.get(target_id, 0) + 1

    if counts:
        executed_id = max(counts, key=counts.get)
        room.players[executed_id].is_alive = False
        executed_player = room.players[executed_id]
        room.last_vote_result = f"{executed_player.name} が追放されました。"
    else:
        room.last_vote_result = "誰も追放されませんでした。"

    game_over = check_win_conditions(room)

    if not game_over:
        room.phase = "night"
        room.day_count += 1
        room.night_actions.clear()
        room.votes.clear()

def check_win_conditions(room: Room) -> bool:
    alive = [p for p in room.players.values() if p.is_alive]
    innocents = [p for p in alive if p.camp == "innocent"]
    impostors = [p for p in alive if p.camp == "impostor"]
    neutrals = [p for p in alive if p.camp == "neutral"]

    if len(impostors) == 0 and len(neutrals) == 0:
        room.phase = "result"
        room.result_text = f"【結果】{room.last_vote_result}\n🎉 イノセント陣営の勝利です！"
        return True
    elif len(impostors) >= len(innocents) + len(neutrals):
        room.phase = "result"
        room.result_text = f"【結果】{room.last_vote_result}\n💀 インポスター陣営の勝利です！"
        return True
    return False

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

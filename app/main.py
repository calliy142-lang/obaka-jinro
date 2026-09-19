import random
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

ROLES_INFO = {
    "バカ": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": False},
    "ドクター": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "ねずみ": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "ポリス": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "トラッパー": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "ルックアウト": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "インベスティゲーター": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "挑発者": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": False},
    "トラッカー": {"camp": "innocent", "camp_name": "イノセント陣営", "can_be_fool": True},
    "ブレイマー": {"camp": "impostor", "camp_name": "インポスター陣営", "can_be_fool": False},
    "クリーナー": {"camp": "impostor", "camp_name": "インポスター陣営", "can_be_fool": False},
    "シリアルキラー": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
    "ボマー": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
    "サバイバー": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
    "シーフ": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
    "魔術師": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
    "ゴースト": {"camp": "neutral", "camp_name": "第三陣営", "can_be_fool": False},
}

class Player:
    def __init__(self, player_id: str, name: str, is_host: bool = False):
        self.id = player_id
        self.name = name
        self.is_host = is_host
        self.real_role = "ドクター"
        self.displayed_role = "ドクター"
        self.camp = "innocent"
        self.camp_name = "イノセント陣営"
        self.is_fool = False
        self.is_alive = True
        self.in_result_screen = False

class Room:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.players: Dict[str, Player] = {}
        self.phase = "lobby"
        self.day_count = 1
        self.night_actions: Dict[str, dict] = {}
        self.impostor_kill_target: Optional[str] = None
        self.votes: Dict[str, str] = {}
        self.night_reports: Dict[str, List[str]] = {}
        self.public_reports: List[str] = []
        self.last_vote_result = ""
        self.result_text = ""

rooms: Dict[str, Room] = {}

class JoinRoomRequest(BaseModel):
    player_name: str

class ActionRequest(BaseModel):
    player_id: str
    target_id: Optional[str] = None
    extra_param: Optional[str] = None

class KillRequest(BaseModel):
    player_id: str
    target_id: str

class VoteRequest(BaseModel):
    player_id: str
    target_id: str

class StartGameRequest(BaseModel):
    host_player_id: str
    impostor_count: int = 1
    neutral_count: int = 0
    selected_roles: Optional[List[str]] = None

class ReturnLobbyRequest(BaseModel):
    player_id: str

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

@app.post("/api/room/{room_code}/leave")
def leave_room(room_code: str, req: ActionRequest):
    if room_code in rooms and req.player_id in rooms[room_code].players:
        del rooms[room_code].players[req.player_id]
        if len(rooms[room_code].players) == 0:
            del rooms[room_code]
        else:
            next_host = list(rooms[room_code].players.values())[0]
            next_host.is_host = True
    return {"message": "退出しました"}

@app.post("/api/room/{room_code}/return_lobby")
def return_lobby(room_code: str, req: ReturnLobbyRequest):
    room = rooms.get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="部屋が存在しません")
    
    player = room.players.get(req.player_id)
    if player:
        player.in_result_screen = False

    if all(not p.in_result_screen for p in room.players.values()):
        room.phase = "lobby"

    return {"message": "ロビー画面へ戻りました"}

@app.post("/api/room/{room_code}/start")
def start_game(room_code: str, req: StartGameRequest):
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    
    if req.host_player_id not in room.players or not room.players[req.host_player_id].is_host:
        raise HTTPException(status_code=403, detail="ホストのみが開始できます")

    players_list = list(room.players.values())
    if len(players_list) < 3:
        raise HTTPException(status_code=400, detail="最低3人のプレイヤーが必要です")

    assign_roles_feign(players_list, req.impostor_count, req.neutral_count, req.selected_roles)

    room.phase = "night"
    room.day_count = 1
    room.night_actions.clear()
    room.impostor_kill_target = None
    room.votes.clear()
    room.public_reports.clear()
    room.last_vote_result = ""
    room.night_reports = {p.id: [] for p in players_list}
    return {"message": "ゲームを開始しました"}

def assign_roles_feign(players: List[Player], imp_count: int, neu_count: int, selected_roles: Optional[List[str]] = None):
    default_innocents = ["ドクター", "ねずみ", "ポリス", "トラッパー", "ルックアウト", "インベスティゲーター", "挑発者", "トラッカー"]
    innocent_pool = [r for r in (selected_roles or default_innocents) if r in default_innocents]
    if not innocent_pool:
        innocent_pool = default_innocents

    impostor_pool = ["ブレイマー", "クリーナー"]
    neutral_pool = ["シリアルキラー", "ボマー", "サバイバー", "シーフ", "魔術師", "ゴースト"]

    random.shuffle(players)
    total = len(players)

    imp_count = min(imp_count, max(1, total - 2))
    neu_count = min(neu_count, max(0, total - imp_count - 1))
    inn_count = total - imp_count - neu_count

    chosen_roles = []
    chosen_roles.extend([random.choice(impostor_pool) for _ in range(imp_count)])
    if neu_count > 0:
        chosen_roles.extend([random.choice(neutral_pool) for _ in range(neu_count)])
    
    chosen_roles.extend(random.sample(innocent_pool, min(inn_count, len(innocent_pool))))
    while len(chosen_roles) < total:
        chosen_roles.append(random.choice(innocent_pool))

    innocent_indices = [i for i, r in enumerate(chosen_roles) if ROLES_INFO[r]["camp"] == "innocent" and ROLES_INFO[r]["can_be_fool"]]
    fool_index = random.choice(innocent_indices) if innocent_indices else -1

    for idx, player in enumerate(players):
        player.is_alive = True
        player.in_result_screen = False
        role_name = chosen_roles[idx]
        player.camp = ROLES_INFO[role_name]["camp"]
        player.camp_name = ROLES_INFO[role_name]["camp_name"]

        if idx == fool_index:
            player.is_fool = True
            player.real_role = "バカ"
            fake_roles = [r for r in innocent_pool if ROLES_INFO[r]["can_be_fool"]]
            player.displayed_role = random.choice(fake_roles) if fake_roles else "ドクター"
        else:
            player.is_fool = False
            player.real_role = role_name
            player.displayed_role = role_name

@app.get("/api/room/{room_code}/player/{player_id}")
def get_player_info(room_code: str, player_id: str):
    if room_code not in rooms or player_id not in rooms[room_code].players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    
    room = rooms[room_code]
    me = room.players[player_id]

    all_p = [{"id": p.id, "name": p.name, "is_host": p.is_host, "is_alive": p.is_alive} for p in room.players.values()]
    other_p = [p for p in all_p if p["id"] != player_id and p["is_alive"]]

    reports = list(room.night_reports.get(player_id, []))
    if room.public_reports:
        reports = room.public_reports + reports

    if room.last_vote_result:
        reports = [f"【前回の投票】 {room.last_vote_result}"] + reports

    night_report_text = "<br>".join(reports) if reports else "特に報告はありません。"

    summary = []
    if room.phase == "result":
        summary = [{
            "name": p.name,
            "displayed_role": p.displayed_role,
            "real_role": p.real_role,
            "camp_name": p.camp_name
        } for p in room.players.values()]

    player_phase = "result" if (room.phase == "result" and me.in_result_screen) else room.phase

    return {
        "phase": player_phase,
        "is_host": me.is_host,
        "displayed_role": f"{me.displayed_role} ({me.camp_name})",
        "camp": me.camp,
        "is_alive": me.is_alive,
        "all_players": all_p,
        "other_players": other_p,
        "night_report": night_report_text,
        "result": getattr(room, "result_text", ""),
        "roles_summary": summary
    }

@app.post("/api/room/{room_code}/action")
def send_action(room_code: str, req: ActionRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "night":
        raise HTTPException(status_code=400, detail="夜フェーズではありません")
    
    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="死亡しているため行動できません")

    room.night_actions[req.player_id] = {
        "target_id": req.target_id,
        "extra_param": req.extra_param
    }
    check_and_resolve_night(room)
    return {"message": "行動を受理しました"}

@app.post("/api/room/{room_code}/kill")
def send_kill(room_code: str, req: KillRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "night":
        raise HTTPException(status_code=400, detail="夜フェーズではありません")
    
    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="死亡しているため行動できません")
    if player.camp != "impostor":
        raise HTTPException(status_code=403, detail="インポスターのみ指定可能です")

    room.impostor_kill_target = req.target_id
    check_and_resolve_night(room)
    return {"message": "襲撃ターゲットを設定しました"}

def check_and_resolve_night(room: Room):
    alive_players = [p for p in room.players.values() if p.is_alive]
    # 生存者の行動が全員揃ったら処理を実行
    alive_action_count = sum(1 for p_id in room.night_actions if room.players[p_id].is_alive)
    if alive_action_count >= len(alive_players):
        resolve_night_phase(room)

def resolve_night_phase(room: Room):
    actions = room.night_actions
    players = room.players
    room.night_reports = {p_id: [] for p_id in players}
    room.public_reports = []

    blocked_players = set()
    trapped_houses = set()
    kills = set()
    healed = set()

    # 1. トラッパーの仕掛け
    for p_id, act in actions.items():
        p = players[p_id]
        if p.is_alive and p.real_role == "トラッパー" and not p.is_fool and act.get("target_id"):
            trapped_houses.add(act["target_id"])

    # 2. 罠への進入・ポリスの阻止チェック
    for p_id, act in actions.items():
        p = players[p_id]
        if not p.is_alive:
            continue
        target_id = act.get("target_id")
        
        if p.real_role == "ポリス" and not p.is_fool and target_id:
            blocked_players.add(target_id)
            room.night_reports[target_id].append("昨夜、ポリスに外出を阻止されました。")

        if target_id in trapped_houses and p.real_role != "シリアルキラー":
            blocked_players.add(p_id)
            room.night_reports[p_id].append("昨夜、トラップにかかり能力失敗しました。")
            room.public_reports.append(f"【全体通知】昨夜、{players[target_id].name} の家でトラップが発動しました！")

    # 3. インポスター襲撃設定の検証
    if room.impostor_kill_target:
        if room.impostor_kill_target in trapped_houses:
            room.public_reports.append("【全体通知】昨夜、トラッパーによりインポスターの襲撃が防がれました！")
        else:
            kills.add(room.impostor_kill_target)

    # 4. 各能力処理
    for p_id, act in actions.items():
        if p_id in blocked_players or not players[p_id].is_alive:
            continue
        
        p = players[p_id]
        target_id = act.get("target_id")
        target = players.get(target_id) if target_id else None

        if p.displayed_role == "ドクター":
            if not p.is_fool and target_id:
                healed.add(target_id)
            if target_id:
                room.night_reports[target_id].append("昨夜、ドクターが治療に来ました。")

        elif p.displayed_role == "インベスティゲーター":
            if target:
                if p.is_fool:
                    room.night_reports[p_id].append(f"調査結果: {target.name} は 「ドクター」 か 「ブレイマー」 です。")
                else:
                    room.night_reports[p_id].append(f"調査結果: {target.name} は 「{target.real_role}」 か 「ブレイマー」 です。")

        elif p.real_role == "シリアルキラー" and target_id:
            kills.add(target_id)

    # 最終的な襲撃適用
    final_kills = kills - healed
    for k_id in final_kills:
        players[k_id].is_alive = False
        room.night_reports[k_id].append("あなたは昨夜死亡しました。")

    room.night_actions.clear()
    room.impostor_kill_target = None

    # ★夜の襲撃後にも勝利判定を実施★
    if not check_win_conditions(room, is_night_kill=True):
        room.phase = "vote"

@app.post("/api/room/{room_code}/vote")
def send_vote(room_code: str, req: VoteRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "vote":
        raise HTTPException(status_code=400, detail="投票フェーズではありません")

    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="死亡しているため投票できません")

    room.votes[req.player_id] = req.target_id

    alive_players = [p for p in room.players.values() if p.is_alive]
    alive_vote_count = sum(1 for p_id in room.votes if room.players[p_id].is_alive)
    
    if alive_vote_count >= len(alive_players):
        resolve_vote_phase(room)

    return {"message": "投票完了"}

def resolve_vote_phase(room: Room):
    counts: Dict[str, int] = {}
    for voter_id, target_id in room.votes.items():
        if room.players[voter_id].is_alive and target_id:
            counts[target_id] = counts.get(target_id, 0) + 1

    if counts:
        executed_id = max(counts, key=counts.get)
        room.players[executed_id].is_alive = False
        executed_player = room.players[executed_id]
        room.last_vote_result = f"{executed_player.name} が追放されました。"
    else:
        room.last_vote_result = "誰も追放されませんでした。"

    if not check_win_conditions(room):
        room.phase = "night"
        room.day_count += 1
        room.night_actions.clear()
        room.votes.clear()

def check_win_conditions(room: Room, is_night_kill: bool = False) -> bool:
    alive = [p for p in room.players.values() if p.is_alive]
    innocents = [p for p in alive if p.camp == "innocent"]
    impostors = [p for p in alive if p.camp == "impostor"]
    neutrals = [p for p in alive if p.camp == "neutral"]

    prefix = "【昨夜の襲撃結果】" if is_night_kill else f"【結果】{room.last_vote_result}\n"

    if len(impostors) == 0 and len(neutrals) == 0:
        room.phase = "result"
        room.result_text = f"{prefix}🎉 イノセント陣営の勝利！"
        for p in room.players.values():
            p.in_result_screen = True
        return True
    elif len(impostors) >= len(innocents) + len(neutrals):
        room.phase = "result"
        room.result_text = f"{prefix}💀 インポスター陣営の勝利！"
        for p in room.players.values():
            p.in_result_screen = True
        return True
    return False

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")

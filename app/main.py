import random
import uuid
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI()

# 17役職の定義と陣営情報
ROLES_INFO = {
    "バカ": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "ドクター": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "ねずみ": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "ポリス": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "トラッパー": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "ルックアウト": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "インベスティゲーター": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "挑発者": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "トラッカー": {"camp": "innocent", "camp_name": "イノセント陣営"},
    "インポスター": {"camp": "impostor", "camp_name": "インポスター陣営"},
    "ブレイマー": {"camp": "impostor", "camp_name": "インポスター陣営"},
    "クリーナー": {"camp": "impostor", "camp_name": "インポスター陣営"},
    "シリアルキラー": {"camp": "neutral", "camp_name": "第三陣営"},
    "ボマー": {"camp": "neutral", "camp_name": "第三陣営"},
    "サバイバー": {"camp": "neutral", "camp_name": "第三陣営"},
    "シーフ": {"camp": "neutral", "camp_name": "第三陣営"},
    "ゴースト": {"camp": "neutral", "camp_name": "第三陣営"},
    "魔術師": {"camp": "neutral", "camp_name": "第三陣営"},
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
        self.is_alive = True
        self.survivor_revives = 3  # サバイバーの復活残り回数
        self.last_target_id = None  # ドクター・ポリスの連続選択チェック用
        self.in_result_screen = False

class Room:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.players: Dict[str, Player] = {}
        self.phase = "lobby"
        self.day_count = 1
        self.day_timer_seconds = 60
        self.night_actions: Dict[str, dict] = {}
        self.impostor_kill_target: Optional[str] = None
        self.votes: Dict[str, str] = {}
        self.vote_weights: Dict[str, int] = {}  # 挑発者等による追加票管理
        self.night_reports: Dict[str, List[str]] = {}
        self.last_vote_result = ""
        self.result_text = ""

rooms: Dict[str, Room] = {}

class JoinRoomRequest(BaseModel):
    player_name: str

class ActionRequest(BaseModel):
    player_id: str
    target_id: Optional[str] = None
    extra_param: Optional[str] = None  # ボマーの「設置/起爆」などの分岐用

class KillRequest(BaseModel):
    player_id: str
    target_id: str

class VoteRequest(BaseModel):
    player_id: str
    target_id: str

class StartGameRequest(BaseModel):
    host_player_id: str
    day_timer_seconds: int = 60
    role_distribution: Dict[str, int] = {}  # 役職ごとのカスタム人数

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
    return {"message": "ロビーに戻りました"}

@app.post("/api/room/{room_code}/start")
def start_game(room_code: str, req: StartGameRequest):
    room = rooms.get(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    if req.host_player_id not in room.players or not room.players[req.host_player_id].is_host:
        raise HTTPException(status_code=403, detail="ホストのみ開始できます")

    players_list = list(room.players.values())
    room.day_timer_seconds = req.day_timer_seconds

    # 役職割り当ての構築
    assigned_roles = []
    for role_name, count in req.role_distribution.items():
        if role_name in ROLES_INFO:
            assigned_roles.extend([role_name] * count)

    # プレイヤー数と設定数が合わない場合のフォールバック
    while len(assigned_roles) < len(players_list):
        assigned_roles.append("ドクター")
    random.shuffle(assigned_roles)

    for idx, player in enumerate(players_list):
        player.is_alive = True
        player.survivor_revives = 3
        player.last_target_id = None
        player.in_result_screen = False
        
        role_name = assigned_roles[idx]
        player.real_role = role_name
        player.displayed_role = role_name
        player.camp = ROLES_INFO[role_name]["camp"]
        player.camp_name = ROLES_INFO[role_name]["camp_name"]

        # インポスターの偽装（ドクター以外）
        if player.camp == "impostor" and role_name == "インポスター":
            innocents_no_doc = ["ねずみ", "ポリス", "トラッパー", "ルックアウト", "インベスティゲーター", "トラッカー"]
            player.displayed_role = random.choice(innocents_no_doc)

    room.phase = "night"
    room.day_count = 1
    room.night_actions.clear()
    room.impostor_kill_target = None
    room.votes.clear()
    room.vote_weights.clear()
    room.last_vote_result = ""
    room.night_reports = {p.id: [] for p in players_list}
    return {"message": "ゲーム開始"}

@app.get("/api/room/{room_code}/player/{player_id}")
def get_player_info(room_code: str, player_id: str):
    room = rooms.get(room_code)
    if not room or player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    
    me = room.players[player_id]
    all_p = [{"id": p.id, "name": p.name, "is_host": p.is_host, "is_alive": p.is_alive} for p in room.players.values()]
    other_p = [p for p in all_p if p["id"] != player_id and p["is_alive"]]

    reports = list(room.night_reports.get(player_id, []))
    if room.last_vote_result:
        reports = [f"【前回の投票】 {room.last_vote_result}"] + reports
    night_report_text = "<br>".join(reports) if reports else "特に報告はありません。"

    summary = []
    if room.phase == "result":
        summary = [{"name": p.name, "displayed_role": p.displayed_role, "real_role": p.real_role, "camp_name": p.camp_name} for p in room.players.values()]

    player_phase = "result" if (room.phase == "result" and me.in_result_screen) else room.phase

    return {
        "phase": player_phase,
        "is_host": me.is_host,
        "displayed_role": f"{me.displayed_role} （{me.camp_name}）",
        "camp": me.camp,
        "is_alive": me.is_alive,
        "all_players": all_p,
        "other_players": other_p,
        "night_report": night_report_text,
        "result": getattr(room, "result_text", ""),
        "roles_summary": summary,
        "day_timer_seconds": room.day_timer_seconds
    }

@app.post("/api/room/{room_code}/action")
def send_action(room_code: str, req: ActionRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "night":
        raise HTTPException(status_code=400, detail="夜フェーズではありません")
    
    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="死亡しています")

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
    if not player or not player.is_alive or player.camp != "impostor":
        raise HTTPException(status_code=403, detail="権限がありません")

    room.impostor_kill_target = req.target_id
    check_and_resolve_night(room)
    return {"message": "襲撃選択完了"}

def check_and_resolve_night(room: Room):
    alive_players = [p for p in room.players.values() if p.is_alive]
    alive_action_count = sum(1 for p_id in room.night_actions if room.players[p_id].is_alive)
    if alive_action_count >= len(alive_players):
        resolve_night_phase(room)

def resolve_night_phase(room: Room):
    actions = room.night_actions
    players = room.players
    room.night_reports = {p_id: [] for p_id in players}

    blocked = set()
    trapped_houses = set()
    kills = set()
    healed = set()

    # シリアルキラーの最速キル処理
    for p_id, act in actions.items():
        p = players[p_id]
        if p.is_alive and p.real_role == "シリアルキラー" and act.get("target_id") and act.get("extra_param") != "pass":
            kills.add(act["target_id"])
            room.night_reports[act["target_id"]].append("あなたは昨夜死亡しました。（役職：わからない）")

    # 魔術師のキル処理
    for p_id, act in actions.items():
        p = players[p_id]
        if p.is_alive and p.real_role == "魔術師" and act.get("target_id") and act.get("extra_param") != "pass":
            target = players.get(act["target_id"])
            if target and target.real_role == act.get("extra_param"):  # 予測的中
                kills.add(target.id)
            else:  # 外れ
                kills.add(p.id)

    # トラッパー罠設置
    for p_id, act in actions.items():
        p = players[p_id]
        if p.is_alive and p.real_role == "トラッパー" and act.get("target_id") and act.get("extra_param") != "pass":
            trapped_houses.add(act["target_id"])

    # ポリス・トラップ妨害
    for p_id, act in actions.items():
        p = players[p_id]
        if not p.is_alive or act.get("extra_param") == "pass":
            continue
        target_id = act.get("target_id")

        if p.real_role == "ポリス" and target_id:
            if p.last_target_id == target_id:
                room.night_reports[p_id].append("同じプレイヤーを連続して選択することはできません。")
            else:
                p.last_target_id = target_id
                blocked.add(target_id)
                room.night_reports[target_id].append("昨夜、ポリスによって能力を失敗させられました。")

        if target_id and target_id in trapped_houses and target_id != p_id and p.real_role != "シリアルキラー":
            blocked.add(p_id)
            room.night_reports[p_id].append("昨夜、トラップにかかり能力が失敗しました。")

    # インポスター襲撃
    if room.impostor_kill_target and room.impostor_kill_target not in trapped_houses:
        kills.add(room.impostor_kill_target)

    # 各種能力解決
    for p_id, act in actions.items():
        if p_id in blocked or not players[p_id].is_alive or act.get("extra_param") == "pass":
            continue
        p = players[p_id]
        target_id = act.get("target_id")
        target = players.get(target_id) if target_id else None

        if p.displayed_role == "ドクター" and target_id:
            if p.last_target_id == target_id:
                room.night_reports[p_id].append("同じプレイヤーを連続して選択することはできません。")
            else:
                p.last_target_id = target_id
                healed.add(target_id)
                room.night_reports[target_id].append("昨夜、ドクターによって復活（保護）されました。")

        elif p.displayed_role == "ねずみ" and target:
            room.night_reports[p_id].append(f"調査結果: {target.name} の役職は 「{target.real_role}」、陣営は 「{target.camp_name}」 です。")
            # 全員に公表
            for other_p in players.values():
                room.night_reports[other_p.id].append(f"【情報公表】 昨夜、ねずみ が能力を使用しました！")

        elif p.real_role == "挑発者" and target_id:
            room.vote_weights[target_id] = room.vote_weights.get(target_id, 0) + 2

    # クリーナーの隠蔽処理などを反映した最終キル処理
    final_kills = kills - healed
    for k_id in final_kills:
        victim = players[k_id]
        # サバイバーの復活処理
        if victim.real_role == "サバイバー" and victim.survivor_revives > 0:
            victim.survivor_revives -= 1
            room.night_reports[k_id].append(f"あなたは致命傷を受けましたが復活しました（残り復活回数: {victim.survivor_revives}回）。")
        else:
            victim.is_alive = False
            room.night_reports[k_id].append("あなたは昨夜死亡しました。")

    room.night_actions.clear()
    room.impostor_kill_target = None

    if not check_win_conditions(room):
        room.phase = "vote"

@app.post("/api/room/{room_code}/vote")
def send_vote(room_code: str, req: VoteRequest):
    room = rooms.get(room_code)
    if not room or room.phase != "vote":
        raise HTTPException(status_code=400, detail="投票フェーズではありません")
    player = room.players.get(req.player_id)
    if not player or not player.is_alive:
        raise HTTPException(status_code=400, detail="死亡しています")

    room.votes[req.player_id] = req.target_id
    alive_count = sum(1 for p in room.players.values() if p.is_alive)
    vote_count = sum(1 for p_id in room.votes if room.players[p_id].is_alive)

    if vote_count >= alive_count:
        resolve_vote_phase(room)

    return {"message": "投票完了"}

def resolve_vote_phase(room: Room):
    counts: Dict[str, int] = {}
    for voter_id, target_id in room.votes.items():
        if room.players[voter_id].is_alive and target_id:
            weight = 1 + room.vote_weights.get(target_id, 0)
            counts[target_id] = counts.get(target_id, 0) + weight

    alive_alive_count = sum(1 for p in room.players.values() if p.is_alive)
    majority_threshold = alive_alive_count / 2

    executed_id = None
    if counts:
        top_target, max_votes = max(counts.items(), key=lambda x: x[1])
        # 過半数ルール判定
        if max_votes > majority_threshold:
            executed_id = top_target

    if executed_id:
        executed_player = room.players[executed_id]
        executed_player.is_alive = False
        room.last_vote_result = f"{executed_player.name} が過半数の票により追放されました。"
    else:
        room.last_vote_result = "過半数に達したプレイヤーがいなかったため、誰も追放されませんでした。"

    room.vote_weights.clear()
    if not check_win_conditions(room):
        room.phase = "night"
        room.day_count += 1
        room.night_actions.clear()
        room.votes.clear()

def check_win_conditions(room: Room) -> bool:
    alive = [p for p in room.players.values() if p.is_alive]
    innocents = [p for p in alive if p.camp == "innocent"]
    impostors = [p for p in alive if p.camp == "impostor"]

    if len(impostors) == 0:
        room.phase = "result"
        room.result_text = "🎉 イノセント陣営の勝利！"
        for p in room.players.values():
            p.in_result_screen = True
        return True
    elif len(impostors) >= len(innocents):
        room.phase = "result"
        room.result_text = "💀 インポスター陣営の勝利！"
        for p in room.players.values():
            p.in_result_screen = True
        return True
    return False

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")
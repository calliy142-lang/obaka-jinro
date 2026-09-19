from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import random
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

rooms = {}

ROLE_CONFIGS = {
    "fool": {"camp": "innocent", "name": "バカ"},
    "doctor": {"camp": "innocent", "name": "ドクター"},
    "mouse": {"camp": "innocent", "name": "ねずみ"},
    "police": {"camp": "innocent", "name": "ポリス"},
    "trapper": {"camp": "innocent", "name": "トラッパー"},
    "lookout": {"camp": "innocent", "name": "ルックアウト"},
    "investigator": {"camp": "innocent", "name": "インベスティゲーター"},
    "provoker": {"camp": "innocent", "name": "挑発者"},
    "tracker": {"camp": "innocent", "name": "トラッカー"},
    "imposter": {"camp": "imposter", "name": "インポスター"},
    "blaimer": {"camp": "imposter", "name": "ブレイマー"},
    "cleaner": {"camp": "imposter", "name": "クリーナー"},
    "serial_killer": {"camp": "neutral", "name": "シリアルキラー"},
    "bomber": {"camp": "neutral", "name": "ボマー"},
    "survivor": {"camp": "neutral", "name": "サバイバー"},
    "thief": {"camp": "neutral", "name": "シーフ"},
    "ghost": {"camp": "neutral", "name": "ゴースト"},
    "magician": {"camp": "neutral", "name": "魔術師"},
}

class Room:
    def __init__(self, room_code):
        self.room_code = room_code
        self.players = {}
        self.host_id = None
        self.phase = "SETUP"
        self.day_count = 1
        self.day_timer = 60
        self.role_distribution = {role: 0 for role in ROLE_CONFIGS}
        # デフォルトで割り当てる基本役職
        self.role_distribution["doctor"] = 1
        self.role_distribution["police"] = 1
        self.role_distribution["investigator"] = 1
        self.role_distribution["imposter"] = 1
        self.actions = {}
        self.votes = {}
        self.winner_faction = None
        self.message = ""

@app.get("/")
def read_index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/room/create")
def create_room():
    room_code = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    while room_code in rooms:
        room_code = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=4))
    rooms[room_code] = Room(room_code)
    return {"room_code": room_code}

@app.post("/api/room/{room_code}/join")
def join_room(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="名前が必要です")
    
    player_id = str(uuid.uuid4())
    is_host = len(room.players) == 0
    if is_host:
        room.host_id = player_id

    room.players[player_id] = {
        "id": player_id,
        "name": name,
        "role": None,
        "alive": True,
        "is_host": is_host
    }
    return {"room_code": room_code, "player_id": player_id}

@app.post("/api/room/{room_code}/settings")
def update_settings(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    if room.host_id != data.get("host_player_id"):
        raise HTTPException(status_code=403, detail="ホストのみ設定を変更できます")
    if "day_timer" in data:
        room.day_timer = int(data["day_timer"])
    if "role_distribution" in data:
        room.role_distribution = data["role_distribution"]
    return {"status": "success"}

@app.post("/api/room/{room_code}/start")
def start_game(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    if room.host_id != data.get("host_player_id"):
        raise HTTPException(status_code=403, detail="ホストのみ開始できます")
    
    player_ids = list(room.players.keys())
    total_players = len(player_ids)
    
    if total_players < 2:
        raise HTTPException(status_code=400, detail="ゲームを開始するには最低2人以上のプレイヤーが必要です。")
    
    assigned_roles = []
    for role, count in room.role_distribution.items():
        try:
            cnt = int(count)
        except (ValueError, TypeError):
            cnt = 0
        assigned_roles.extend([role] * cnt)
    
    all_role_keys = list(ROLE_CONFIGS.keys())
    while len(assigned_roles) < total_players:
        assigned_roles.append(random.choice(all_role_keys))
        
    assigned_roles = assigned_roles[:total_players]

    random.shuffle(assigned_roles)
    for idx, pid in enumerate(player_ids):
        room.players[pid]["role"] = assigned_roles[idx]
        room.players[pid]["alive"] = True

    room.phase = "NIGHT"
    room.day_count = 1
    room.actions = {}
    room.votes = {}
    room.winner_faction = None
    room.message = "ゲームが開始されました。最初の夜を迎えています。"
    return {"status": "started"}

@app.get("/api/room/{room_code}/player/{player_id}")
def get_player_info(room_code: str, player_id: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    
    player = room.players[player_id]
    targets = [{"id": p["id"], "name": p["name"]} for p in room.players.values() if p["id"] != player_id and p["alive"]]
    targets.insert(0, {"id": "pass", "name": "能力を使わない（パス）"})

    return {
        "displayed_role": ROLE_CONFIGS.get(player["role"], {}).get("name", "未割り当て"),
        "phase": room.phase,
        "day_count": room.day_count,
        "day_timer": room.day_timer,
        "alive": player["alive"],
        "targets": targets,
        "action_submitted": player_id in room.actions,
        "winner_faction": room.winner_faction,
        "message": room.message,
        "is_host": player["is_host"],
        "role_distribution": room.role_distribution
    }

@app.post("/api/room/{room_code}/action")
def send_action(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    
    player_id = data.get("player_id")
    target_id = data.get("target_id")
    room.actions[player_id] = target_id
    
    alive_players = [pid for pid, p in room.players.items() if p["alive"]]
    if all(pid in room.actions for pid in alive_players):
        resolve_night(room)
    return {"status": "success"}

def resolve_night(room):
    passed_count = sum(1 for target in room.actions.values() if target == "pass")
    room.message = f"夜が明けました。（昨晩パスしたプレイヤー数: {passed_count}人）"
    room.phase = "DAY"
    room.actions = {}

@app.post("/api/room/{room_code}/vote")
def send_vote(room_code: str, data: dict):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    room = rooms[room_code]
    
    player_id = data.get("player_id")
    target_id = data.get("target_id")
    room.votes[player_id] = target_id
    
    alive_players = [pid for pid, p in room.players.items() if p["alive"]]
    if len(room.votes) >= len(alive_players):
        resolve_voting(room)
    return {"status": "success"}

def resolve_voting(room):
    vote_counts = {}
    for target in room.votes.values():
        if target and target != "pass":
            vote_counts[target] = vote_counts.get(target, 0) + 1
        
    alive_count = sum(1 for p in room.players.values() if p["alive"])
    majority_threshold = alive_count / 2
    
    exiled = None
    if vote_counts:
        top_target, max_votes = max(vote_counts.items(), key=lambda x: x[1])
        if max_votes > majority_threshold:
            exiled = top_target
            room.players[exiled]["alive"] = False
            room.message = f"投票の結果、{room.players[exiled]['name']} が過半数の票（{max_votes}票）により追放されました。"
        else:
            room.message = f"最多得票者はいましたが、生存者の過半数（{majority_threshold}票超）に達しなかったため、誰も追放されませんでした。"
    else:
        room.message = "有効な投票がなかったため、誰も追放されませんでした。"
            
    room.votes = {}
    room.phase = "NIGHT"
    room.day_count += 1
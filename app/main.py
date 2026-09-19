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
        self.distribution_mode = "individual"
        self.role_distribution = {role: 0 for role in ROLE_CONFIGS}
        self.role_distribution["doctor"] = 1
        self.role_distribution["police"] = 1
        self.role_distribution["investigator"] = 1
        self.role_distribution["imposter"] = 1
        
        self.faction_distribution = {
            "innocent": 2,
            "imposter": 1,
            "neutral": 0
        }
        
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
        "is_host": is_host,
        "survivor_revives": 3,
        "candle_target": None,
        "last_visited": None
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
    if "distribution_mode" in data:
        room.distribution_mode = data["distribution_mode"]
    if "role_distribution" in data:
        room.role_distribution = data["role_distribution"]
    if "faction_distribution" in data:
        room.faction_distribution = data["faction_distribution"]
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
    
    if room.distribution_mode == "individual":
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
    
    else:
        fac_in = room.faction_distribution.get("innocent", 0)
        fac_imp = room.faction_distribution.get("imposter", 0)
        fac_neu = room.faction_distribution.get("neutral", 0)
        
        innocent_roles = [k for k, v in ROLE_CONFIGS.items() if v["camp"] == "innocent"]
        imposter_roles = [k for k, v in ROLE_CONFIGS.items() if v["camp"] == "imposter"]
        neutral_roles = [k for k, v in ROLE_CONFIGS.items() if v["camp"] == "neutral"]
        
        for _ in range(fac_in):
            assigned_roles.append(random.choice(innocent_roles) if innocent_roles else "doctor")
        for _ in range(fac_imp):
            assigned_roles.append(random.choice(imposter_roles) if imposter_roles else "imposter")
        for _ in range(fac_neu):
            assigned_roles.append(random.choice(neutral_roles) if neutral_roles else "survivor")
            
        while len(assigned_roles) < total_players:
            assigned_roles.append(random.choice(innocent_roles))
        assigned_roles = assigned_roles[:total_players]

    random.shuffle(assigned_roles)
    for idx, pid in enumerate(player_ids):
        p = room.players[pid]
        p["role"] = assigned_roles[idx]
        p["alive"] = True
        p["survivor_revives"] = 3
        p["candle_target"] = None
        p["last_visited"] = None

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
        "distribution_mode": room.distribution_mode,
        "role_distribution": room.role_distribution,
        "faction_distribution": room.faction_distribution
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
    reports = []
    attacked_players = set()
    protected_players = set()
    blocked_players = set()
    killed_by_sk = set()
    killed_by_magician = set()

    # 1. ポリス・トラッパーによる行動阻害
    for pid, target_id in room.actions.items():
        if target_id == "pass":
            continue
        p = room.players.get(pid)
        if not p or not p["alive"]:
            continue
        role = p["role"]
        if role in ["police", "trapper"]:
            blocked_players.add(target_id)

    # 2. 各役職の夜アクション実行判定
    for pid, target_id in room.actions.items():
        if target_id == "pass":
            continue
        p = room.players.get(pid)
        if not p or not p["alive"]:
            continue
        
        # 阻害チェック（シリアルキラーと魔術師は阻害を受けない）
        role = p["role"]
        if pid in blocked_players and role not in ["serial_killer", "magician"]:
            continue

        p["last_visited"] = target_id

        if role == "imposter":
            attacked_players.add(target_id)
        elif role == "serial_killer":
            killed_by_sk.add(target_id)
        elif role == "magician":
            # 魔術師の予測キル（ターゲットが誰であれ正しければキル）
            killed_by_magician.add(target_id)
        elif role == "doctor":
            protected_players.add(target_id)
        elif role == "mouse":
            target_p = room.players.get(target_id)
            if target_p:
                if p["role"] == "fool":
                    # バカのネズミはデタラメな役職結果を返す
                    fake_role_name = random.choice(list(ROLE_CONFIGS.values()))["name"]
                    reports.append(f"【ねずみ調査】{target_p['name']} の役職は {fake_role_name} です。")
                else:
                    target_role_name = ROLE_CONFIGS.get(target_p["role"], {}).get("name", "不明")
                    reports.append(f"【ねずみ調査】{target_p['name']} の役職は {target_role_name} です。")
        elif role == "investigator":
            target_p = room.players.get(target_id)
            if target_p:
                if p["role"] == "fool":
                    reports.append(f"【インベスティゲーター調査】{target_p['name']} の結果: デタラメな情報です。")
                else:
                    camp_str = "イノセント陣営" if ROLE_CONFIGS.get(target_p["role"], {}).get("camp") == "innocent" else "インポスター/ニュートラル陣営"
                    reports.append(f"【インベスティゲーター調査】{target_p['name']} は [イノセント陣営] または [{camp_str}] のいずれかです。")
        elif role == "ghost":
            target_p = room.players.get(target_id)
            if target_p:
                target_p["candle_target"] = True

    # 3. 襲撃・キルによる死亡確定処理
    dead_names = []
    
    # インポスター襲撃
    for target_id in attacked_players:
        if target_id in protected_players:
            continue
        target_p = room.players.get(target_id)
        if target_p and target_p["alive"]:
            if target_p["role"] == "survivor" and target_p["survivor_revives"] > 0:
                target_p["survivor_revives"] -= 1
                reports.append(f"【サバイバー】{target_p['name']} は襲撃されましたが復活しました（残り: {target_p['survivor_revives']}回）")
            else:
                target_p["alive"] = False
                dead_names.append(target_p["name"])

    # シリアルキラーキル
    for target_id in killed_by_sk:
        target_p = room.players.get(target_id)
        if target_p and target_p["alive"]:
            if target_p["role"] == "survivor" and target_p["survivor_revives"] > 0:
                target_p["survivor_revives"] -= 1
            else:
                target_p["alive"] = False
                dead_names.append(target_p["name"])

    # 魔術師キル（ドクター救済不可）
    for target_id in killed_by_magician:
        target_p = room.players.get(target_id)
        if target_p and target_p["alive"]:
            target_p["alive"] = False
            dead_names.append(target_p["name"])

    # 勝敗判定
    winner = check_win_condition(room)
    if winner:
        room.winner_faction = winner
        room.phase = "RESULT"
        room.message = f"ゲーム終了！勝者陣営: {winner}"
    else:
        msg = "夜が明けました。"
        if dead_names:
            msg += f" 昨晩の犠牲者: {', '.join(dead_names)}"
        if reports:
            msg += " " + " / ".join(reports)
        room.message = msg
        room.phase = "DAY"

    room.actions = {}

def check_win_condition(room):
    alive_players = [p for p in room.players.values() if p["alive"]]
    innocents = [p for p in alive_players if ROLE_CONFIGS.get(p["role"], {}).get("camp") == "innocent"]
    imposters = [p for p in alive_players if ROLE_CONFIGS.get(p["role"], {}).get("camp") == "imposter"]
    neutrals = [p for p in alive_players if ROLE_CONFIGS.get(p["role"], {}).get("camp") == "neutral"]

    if len(imposters) == 0 and len(neutrals) == 0:
        return "イノセント陣営"
    if len(imposters) >= len(innocents) + len(neutrals):
        return "インポスター陣営"
    return None

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
            exiled_p = room.players[exiled]
            exiled_p["alive"] = False
            room.message = f"投票の結果、{exiled_p['name']} が過半数の票（{max_votes}票）により追放されました。"
            
            # ゴーストの道連れ処理
            if exiled_p["role"] == "ghost" and exiled_p["candle_target"]:
                for pid, p in room.players.items():
                    if p.get("candle_target") and p["alive"]:
                        p["alive"] = False
                        room.message += f" また、ゴーストの復讐により {p['name']} が道連れにされました！"
        else:
            room.message = f"最多得票者はいましたが、生存者の過半数に達しなかったため、誰も追放されませんでした。"
    else:
        room.message = "有効な投票がなかったため、誰も追放されませんでした。"
            
    winner = check_win_condition(room)
    if winner:
        room.winner_faction = winner
        room.phase = "RESULT"
        room.message += f" ゲーム終了！勝者陣営: {winner}"
    else:
        room.votes = {}
        room.phase = "NIGHT"
        room.day_count += 1
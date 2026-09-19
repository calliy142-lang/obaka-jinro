from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import random
import uuid

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

rooms = {}

# ============================================================
# 役職定義
# ============================================================

ROLE_CONFIGS = {
    "fool": {"camp": "innocent", "name": "バカ"},
    "doctor": {"camp": "innocent", "name": "ドクター"},
    "mouse": {"camp": "innocent", "name": "ねずみ", "max_uses": 1},
    "police": {"camp": "innocent", "name": "ポリス"},
    "trapper": {"camp": "innocent", "name": "トラッパー"},
    "lookout": {"camp": "innocent", "name": "ルックアウト"},
    "investigator": {"camp": "innocent", "name": "インベスティゲーター"},
    "provoker": {"camp": "innocent", "name": "挑発者", "max_uses": 2},
    "tracker": {"camp": "innocent", "name": "トラッカー"},

    "imposter": {"camp": "imposter", "name": "インポスター"},
    "blaimer": {"camp": "imposter", "name": "ブレイマー", "max_uses": 2},
    "cleaner": {"camp": "imposter", "name": "クリーナー"},

    "serial_killer": {"camp": "neutral", "name": "シリアルキラー"},
    "bomber": {"camp": "neutral", "name": "ボマー"},
    "survivor": {"camp": "neutral", "name": "サバイバー"},
    "thief": {"camp": "neutral", "name": "シーフ"},
    "ghost": {"camp": "neutral", "name": "ゴースト"},
    "magician": {"camp": "neutral", "name": "魔術師"},
}

ROLE_KEYS = list(ROLE_CONFIGS.keys())


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
            "neutral": 0,
        }

        # player_id -> NightAction(dict)
        self.actions = {}

        # player_id -> target_id
        self.votes = {}

        self.winner_faction = None
        self.message = ""

        # 次の夜に実行するゴースト復讐
        self.ghost_revenge_target = None

        # その夜の公開用情報
        self.public_reports = []

        # 連続訪問禁止用の履歴は PlayerState.last_target を利用


# ============================================================
# 共通ヘルパー
# ============================================================

def get_room(room_code):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="部屋が見つかりません")
    return rooms[room_code]


def get_player(room, player_id):
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")
    return room.players[player_id]


def role_name(role):
    return ROLE_CONFIGS.get(role, {}).get("name", "不明")


def camp_name(camp):
    return {
        "innocent": "イノセント陣営",
        "imposter": "インポスター陣営",
        "neutral": "ニュートラル陣営",
    }.get(camp, "不明")


def true_role(player):
    return player.get("true_role", player.get("role"))


def actual_role(player):
    # role は内部的な真の役職として維持。
    return player.get("role")


def displayed_role_for(viewer, target):
    """
    target の「死亡時などに公表される役職」を返す。
    ブレイマー等の効果は public_role に保存。
    Cleaner は public_role = None。
    生存中の自分には fool の偽役職を表示する。
    """
    if target.get("alive"):
        return target.get("displayed_role", role_name(target.get("role")))

    public_role = target.get("public_role", role_name(target.get("role")))
    if public_role is None:
        return "不明"
    return public_role


def set_public_role(player):
    """
    死亡/追放時の公開役職を確定。
    Cleanerで掃除済みなら不明。
    """
    if player.get("cleaned"):
        player["public_role"] = None
    else:
        player["public_role"] = player.get("revealed_role", role_name(player.get("role")))


def alive_players(room):
    return [p for p in room.players.values() if p["alive"]]


def alive_ids(room):
    return [p["id"] for p in alive_players(room)]


def can_use_role(player):
    # バカは本当の能力を持たない
    return actual_role(player) != "fool"


def role_max_uses(role):
    return ROLE_CONFIGS.get(role, {}).get("max_uses")


def uses_left(player):
    return player.get("uses_remaining")


def consume_use(player):
    if player.get("uses_remaining") is not None:
        player["uses_remaining"] -= 1


def is_same_target_forbidden(player, target_id):
    return (
        actual_role(player) in {"doctor", "police"}
        and player.get("last_target") == target_id
    )


def get_fake_innocent_role():
    innocent_roles = [
        r for r, cfg in ROLE_CONFIGS.items()
        if cfg["camp"] == "innocent" and r != "fool"
    ]
    return random.choice(innocent_roles)


def fool_result_role(target_player=None):
    # Foolが見せられる偽役職。
    return random.choice([
        r for r in ROLE_KEYS if ROLE_CONFIGS[r]["camp"] == "innocent" and r != "fool"
    ])


def validate_target(room, actor_id, target_id, allow_self=False):
    if target_id == "pass":
        return None

    if target_id not in room.players:
        raise HTTPException(status_code=400, detail="対象プレイヤーが存在しません")

    target = room.players[target_id]
    if not target["alive"]:
        raise HTTPException(status_code=400, detail="死亡したプレイヤーは対象にできません")

    if not allow_self and actor_id == target_id:
        raise HTTPException(status_code=400, detail="自分自身は対象にできません")

    return target


# ============================================================
# 勝利条件
# ============================================================

def individual_win_status(room):
    """
    None / 勝利陣営名を返す。
    このゲームではニュートラルの個別勝利も存在するため、
    まず特殊役職の勝利条件を確認し、その後通常陣営を確認する。
    """
    players = list(room.players.values())
    alive = [p for p in players if p["alive"]]

    # ゴースト：追放後、次の夜に復讐を成功させた時点で勝利
    # resolve_night 側で直接終了させる。

    # サバイバー：ゲーム終了時に生存
    # 通常陣営の決着が発生したとき、aliveなら勝利扱い。

    # シリアルキラー / ボマー：自分以外が全員死亡
    for p in alive:
        r = actual_role(p)
        if r in {"serial_killer", "bomber"}:
            others = [q for q in alive if q["id"] != p["id"]]
            if not others:
                return role_name(r) + "勝利"

    # 通常インポスター勝利
    innocents = [
        p for p in alive
        if ROLE_CONFIGS.get(actual_role(p), {}).get("camp") == "innocent"
    ]
    imposters = [
        p for p in alive
        if ROLE_CONFIGS.get(actual_role(p), {}).get("camp") == "imposter"
    ]
    neutrals = [
        p for p in alive
        if ROLE_CONFIGS.get(actual_role(p), {}).get("camp") == "neutral"
    ]

    # 挑発者の特殊勝利
    for p in alive:
        if actual_role(p) == "provoker":
            target_id = p.get("provoked_target")
            if target_id and target_id in room.players:
                target = room.players[target_id]
                if (
                    target["alive"]
                    and ROLE_CONFIGS.get(actual_role(target), {}).get("camp") == "imposter"
                    and p.get("provoked_target_was_active")
                ):
                    return "挑発者勝利"

    # シーフ：盗んだ役職の勝利条件に従う
    for p in alive:
        if actual_role(p) == "thief" and p.get("stolen_role"):
            stolen = p["stolen_role"]
            if stolen in {"serial_killer", "bomber"}:
                others = [q for q in alive if q["id"] != p["id"]]
                if not others:
                    return "シーフ勝利"
            elif stolen == "survivor":
                return "シーフ勝利"
            elif ROLE_CONFIGS.get(stolen, {}).get("camp") == "imposter":
                if len(imposters) >= len(innocents) + len(neutrals):
                    return "シーフ勝利"
            elif ROLE_CONFIGS.get(stolen, {}).get("camp") == "innocent":
                if len(imposters) == 0 and len(neutrals) == 0:
                    return "シーフ勝利"

    # サバイバーは他陣営の決着時に生存なら勝利候補。
    survivor_alive = any(actual_role(p) == "survivor" for p in alive)

    if len(imposters) == 0 and len(neutrals) == 0:
        if survivor_alive:
            return "サバイバー勝利"
        return "イノセント陣営"

    if len(imposters) >= len(innocents) + len(neutrals):
        if survivor_alive:
            return "サバイバー勝利"
        return "インポスター陣営"

    return None


def check_win_condition(room):
    return individual_win_status(room)


# ============================================================
# 画面/API
# ============================================================

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
    room = get_room(room_code)

    name = data.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="名前が必要です")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="ゲーム開始後は参加できません")

    player_id = str(uuid.uuid4())
    is_host = len(room.players) == 0

    if is_host:
        room.host_id = player_id

    room.players[player_id] = {
        "id": player_id,
        "name": name,

        # 真の役職
        "role": None,
        "true_role": None,

        # 自分に表示する役職。Foolは偽のイノセント役職。
        "displayed_role": None,

        # 死亡/追放時の公開役職
        "revealed_role": None,
        "public_role": None,
        "cleaned": False,

        "alive": True,
        "is_host": is_host,

        # 特殊役職
        "survivor_revives": 3,
        "candle_target": None,
        "ghost_killed": False,
        "stolen_role": None,
        "stolen_uses_remaining": None,

        # 使用回数
        "uses_remaining": None,

        # 連続対象
        "last_target": None,

        # 今夜の訪問先
        "night_visit_target": None,

        # 今夜得た情報
        "private_reports": [],

        # 挑発
        "provoked_target": None,
        "provoked_target_was_active": False,

        # ボマー
        "bomb_target": None,

        # トラッカー
        "tracker_target": None,
    }

    return {"room_code": room.room_code, "player_id": player_id}


@app.post("/api/room/{room_code}/settings")
def update_settings(room_code: str, data: dict):
    room = get_room(room_code)

    if room.host_id != data.get("host_player_id"):
        raise HTTPException(status_code=403, detail="ホストのみ設定を変更できます")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="ゲーム開始後は設定できません")

    if "day_timer" in data:
        room.day_timer = max(10, min(300, int(data["day_timer"])))

    if "distribution_mode" in data:
        room.distribution_mode = data["distribution_mode"]

    if "role_distribution" in data:
        room.role_distribution = data["role_distribution"]

    if "faction_distribution" in data:
        room.faction_distribution = data["faction_distribution"]

    return {"status": "success"}


@app.post("/api/room/{room_code}/start")
def start_game(room_code: str, data: dict):
    room = get_room(room_code)

    if room.host_id != data.get("host_player_id"):
        raise HTTPException(status_code=403, detail="ホストのみ開始できます")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="ゲームはすでに開始されています")

    player_ids = list(room.players.keys())
    total_players = len(player_ids)

    if total_players < 2:
        raise HTTPException(status_code=400, detail="ゲームを開始するには最低2人以上のプレイヤーが必要です。")

    assigned_roles = []

    if room.distribution_mode == "individual":
        for role, count in room.role_distribution.items():
            try:
                cnt = max(0, int(count))
            except (ValueError, TypeError):
                cnt = 0
            assigned_roles.extend([role] * cnt)

        while len(assigned_roles) < total_players:
            assigned_roles.append(random.choice(ROLE_KEYS))

        assigned_roles = assigned_roles[:total_players]

    else:
        fac_in = max(0, int(room.faction_distribution.get("innocent", 0)))
        fac_imp = max(0, int(room.faction_distribution.get("imposter", 0)))
        fac_neu = max(0, int(room.faction_distribution.get("neutral", 0)))

        innocent_roles = [
            k for k, v in ROLE_CONFIGS.items() if v["camp"] == "innocent"
        ]
        imposter_roles = [
            k for k, v in ROLE_CONFIGS.items() if v["camp"] == "imposter"
        ]
        neutral_roles = [
            k for k, v in ROLE_CONFIGS.items() if v["camp"] == "neutral"
        ]

        for _ in range(fac_in):
            assigned_roles.append(random.choice(innocent_roles))
        for _ in range(fac_imp):
            assigned_roles.append(random.choice(imposter_roles))
        for _ in range(fac_neu):
            assigned_roles.append(random.choice(neutral_roles))

        while len(assigned_roles) < total_players:
            assigned_roles.append(random.choice(innocent_roles))

        assigned_roles = assigned_roles[:total_players]

    random.shuffle(assigned_roles)

    for idx, pid in enumerate(player_ids):
        p = room.players[pid]
        role = assigned_roles[idx]

        p["role"] = role
        p["true_role"] = role
        p["alive"] = True
        p["cleaned"] = False
        p["revealed_role"] = role_name(role)
        p["public_role"] = None

        p["survivor_revives"] = 3
        p["candle_target"] = None
        p["ghost_killed"] = False
        p["stolen_role"] = None
        p["stolen_uses_remaining"] = None
        p["last_target"] = None
        p["night_visit_target"] = None
        p["private_reports"] = []
        p["provoked_target"] = None
        p["provoked_target_was_active"] = False
        p["bomb_target"] = None
        p["tracker_target"] = None

        max_uses = role_max_uses(role)
        p["uses_remaining"] = max_uses

        # Foolはイノセント役職に見える。
        if role == "fool":
            p["displayed_role"] = role_name(get_fake_innocent_role())
        else:
            p["displayed_role"] = role_name(role)

    room.phase = "NIGHT"
    room.day_count = 1
    room.actions = {}
    room.votes = {}
    room.winner_faction = None
    room.message = "ゲームが開始されました。最初の夜を迎えています。"
    room.ghost_revenge_target = None
    room.public_reports = []

    return {"status": "started"}


@app.get("/api/room/{room_code}/player/{player_id}")
def get_player_info(room_code: str, player_id: str):
    room = get_room(room_code)
    player = get_player(room, player_id)

    targets = [
        {"id": p["id"], "name": p["name"]}
        for p in room.players.values()
        if p["id"] != player_id and p["alive"]
    ]
    targets.insert(0, {"id": "pass", "name": "能力を使わない（パス）"})

    # 自分だけが見る役職表示
    if player["alive"]:
        display_role = player.get("displayed_role") or role_name(player["role"])
    else:
        display_role = displayed_role_for(player, player)

    # 個別情報をその本人だけに返す
    private_reports = player.get("private_reports", [])

    return {
        "displayed_role": display_role,
        "true_role_debug": None,  # 本番では絶対に返さない
        "phase": room.phase,
        "day_count": room.day_count,
        "day_timer": room.day_timer,
        "alive": player["alive"],
        "targets": targets,
        "action_submitted": player_id in room.actions,
        "winner_faction": room.winner_faction,
        "message": room.message,
        "private_reports": private_reports,
        "is_host": player["is_host"],
        "distribution_mode": room.distribution_mode,
        "role_distribution": room.role_distribution,
        "faction_distribution": room.faction_distribution,
    }


# ============================================================
# 夜アクション
# ============================================================

@app.post("/api/room/{room_code}/action")
def send_action(room_code: str, data: dict):
    room = get_room(room_code)

    if room.phase != "NIGHT":
        raise HTTPException(status_code=400, detail="現在は夜ではありません")

    player_id = data.get("player_id")
    target_id = data.get("target_id")

    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")

    player = room.players[player_id]

    if not player["alive"]:
        raise HTTPException(status_code=400, detail="死亡中は行動できません")

    if player_id in room.actions:
        raise HTTPException(status_code=400, detail="すでに夜の行動を提出しています")

    # パス
    if target_id == "pass":
        room.actions[player_id] = {
            "type": "pass",
            "target_id": None,
        }
    else:
        validate_target(room, player_id, target_id)

        role = actual_role(player)

        # 連続対象禁止
        if is_same_target_forbidden(player, target_id):
            raise HTTPException(status_code=400, detail="前の夜と同じプレイヤーを連続して対象にはできません")

        # Foolは能力を持たない。
        # 現在のフロントAPIがtarget_idだけ送るため、
        # Foolの夜行動は「見た目の役職に応じた行動をしたように見える」ものとして
        # 実際には能力を発動しない。
        if role == "fool":
            room.actions[player_id] = {
                "type": "fool_fake",
                "target_id": target_id,
            }
        else:
            room.actions[player_id] = {
                "type": "role_action",
                "target_id": target_id,
            }

    if all(pid in room.actions for pid in alive_ids(room)):
        resolve_night(room)

    return {"status": "success"}


# ============================================================
# 夜の解決
# ============================================================

def resolve_night(room):
    reports = []
    dead_names = []

    # 各プレイヤーの今夜情報をリセット
    for p in room.players.values():
        p["private_reports"] = []
        p["night_visit_target"] = None
        p["tracker_target"] = None

    # --------------------------------------------------------
    # 0. ゴースト復讐
    # 「前の昼に追放されたゴースト」が指定した対象を次の夜に殺す
    # --------------------------------------------------------
    if room.ghost_revenge_target:
        target_id = room.ghost_revenge_target
        target = room.players.get(target_id)
        if target and target["alive"]:
            target["alive"] = False
            target["ghost_killed"] = True
            set_public_role(target)
            dead_names.append(target["name"])
        room.ghost_revenge_target = None

    # --------------------------------------------------------
    # 1. 訪問情報を構築
    # --------------------------------------------------------
    visitors = {}  # target_id -> [visitor_id]
    visit_map = {}  # actor_id -> target_id

    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p or not p["alive"]:
            continue

        if action["type"] == "pass":
            continue

        target_id = action.get("target_id")
        role = actual_role(p)

        # 魔術師は家から攻撃するため訪問しない
        if role == "magician":
            continue

        # Foolも「見た目の能力を使ったように見える」だけだが、
        # ルックアウト等の情報としては家を訪問したものとして扱う。
        visit_map[pid] = target_id
        visitors.setdefault(target_id, []).append(pid)
        p["night_visit_target"] = target_id

    # --------------------------------------------------------
    # 2. Police / Trapper
    # --------------------------------------------------------
    blocked = set()

    # Police: 対象の能力を封印
    for pid, target_id in visit_map.items():
        p = room.players[pid]
        if actual_role(p) == "police":
            blocked.add(target_id)

    # Trapper: 対象の家にいる訪問者から1人をランダム封印
    trapped_visitors = set()
    for pid, target_id in visit_map.items():
        p = room.players[pid]
        if actual_role(p) == "trapper":
            candidates = [
                v for v in visitors.get(target_id, [])
                if v != pid
            ]
            if candidates:
                trapped_visitors.add(random.choice(candidates))

    # --------------------------------------------------------
    # 3. Lookout / Tracker / Investigator / Mouse
    #    「情報系」は殺害より先に計算する
    # --------------------------------------------------------
    for pid, target_id in visit_map.items():
        p = room.players[pid]
        role = actual_role(p)

        # Lookout
        if role == "lookout" and pid not in blocked and pid not in trapped_visitors:
            names = [
                room.players[v]["name"]
                for v in visitors.get(target_id, [])
                if actual_role(room.players[v]) != "serial_killer"
                and v not in trapped_visitors
            ]
            p["private_reports"].append(
                f"【ルックアウト】{room.players[target_id]['name']} の家への訪問者: "
                + (", ".join(names) if names else "なし")
            )

        # Tracker
        if role == "tracker" and pid not in blocked and pid not in trapped_visitors:
            target = room.players[target_id]
            if actual_role(target) != "serial_killer":
                destination = target.get("night_visit_target")
                if destination and destination in room.players:
                    p["private_reports"].append(
                        f"【トラッカー】{target['name']} は "
                        f"{room.players[destination]['name']} の家を訪れました。"
                    )
                else:
                    p["private_reports"].append(
                        f"【トラッカー】{target['name']} は今夜家を出ていません。"
                    )

        # Investigator
        if role == "investigator" and pid not in blocked and pid not in trapped_visitors:
            target = room.players[target_id]
            target_role = actual_role(target)

            if role == "fool":
                fake = random.choice([
                    "イノセント陣営",
                    "インポスター/ニュートラル陣営",
                ])
                p["private_reports"].append(
                    f"【インベスティゲーター】{target['name']} の結果: {fake}"
                )
            else:
                if ROLE_CONFIGS.get(target_role, {}).get("camp") == "innocent":
                    other = random.choice(
                        [r for r in ROLE_KEYS if ROLE_CONFIGS[r]["camp"] != "innocent"]
                    )
                    result = f"{role_name(target_role)} または {role_name(other)}"
                else:
                    innocent = random.choice([
                        r for r in ROLE_KEYS
                        if ROLE_CONFIGS[r]["camp"] == "innocent"
                    ])
                    result = f"{role_name(innocent)} または {role_name(target_role)}"

                p["private_reports"].append(
                    f"【インベスティゲーター】{target['name']} は "
                    f"{result} のどちらかです。"
                )

        # Mouse
        if role == "mouse" and pid not in blocked and pid not in trapped_visitors:
            if p.get("uses_remaining") is not None and p["uses_remaining"] <= 0:
                continue

            target = room.players[target_id]
            # ねずみの調査結果は真の役職・陣営
            camp = ROLE_CONFIGS.get(actual_role(target), {}).get("camp")
            p["private_reports"].append(
                f"【ねずみ】{target['name']} の役職は "
                f"{role_name(actual_role(target))}、{camp_name(camp)}です。"
            )
            consume_use(p)

            # 次の昼に全員公開
            reports.append(
                f"【ねずみ公開】{p['name']} が {target['name']} を調査しました。"
            )

    # --------------------------------------------------------
    # 4. Provoker
    # --------------------------------------------------------
    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p or not p["alive"]:
            continue

        if actual_role(p) != "provoker":
            continue

        target_id = action.get("target_id")
        if action["type"] == "pass" or target_id is None:
            continue

        if p.get("uses_remaining") is not None and p["uses_remaining"] <= 0:
            continue

        target = room.players[target_id]
        p["provoked_target"] = target_id
        p["provoked_target_was_active"] = (
            ROLE_CONFIGS.get(actual_role(target), {}).get("camp") == "imposter"
        )
        consume_use(p)

        # +2票
        target["bonus_votes"] = target.get("bonus_votes", 0) + 2

    # --------------------------------------------------------
    # 5. Blaimer
    # --------------------------------------------------------
    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p or not p["alive"] or actual_role(p) != "blaimer":
            continue

        target_id = action.get("target_id")
        if action["type"] == "pass":
            continue

        if p.get("uses_remaining") is not None and p["uses_remaining"] <= 0:
            continue

        target = room.players[target_id]

        # 対象の役職を「インポスター役職」に見せる。
        target["revealed_role"] = "インポスター"
        target["public_role"] = "インポスター"
        target["blamed"] = True
        consume_use(p)

    # --------------------------------------------------------
    # 6. Cleaner
    #    対象が死亡/追放された時に役職を非公開にする
    # --------------------------------------------------------
    cleaner_targets = set()
    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p or not p["alive"] or actual_role(p) != "cleaner":
            continue

        if action["type"] == "pass":
            continue

        cleaner_targets.add(action["target_id"])

    # --------------------------------------------------------
    # 7. 攻撃
    # --------------------------------------------------------
    attacks = []
    doctor_targets = set()

    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p or not p["alive"]:
            continue

        role = actual_role(p)
        target_id = action.get("target_id")

        if action["type"] == "pass":
            continue

        # Police / Trapperに封印された能力は実行しない
        # Serial Killer / Magicianは例外
        if (
            pid in blocked
            or pid in trapped_visitors
        ) and role not in {"serial_killer", "magician"}:
            continue

        if role == "doctor":
            doctor_targets.add(target_id)

        elif role == "imposter":
            attacks.append(("imposter", pid, target_id))

        elif role == "serial_killer":
            attacks.append(("serial_killer", pid, target_id))

        elif role == "magician":
            # 現在のAPIは guessed_role を送っていないため、
            # フロント改修前は魔術師を正しく判定できない。
            # target_idを「対象選択」として記録するだけ。
            # ここでは誤爆を防ぐため能力を実行しない。
            p["private_reports"].append(
                "【魔術師】役職予想機能はフロント側の追加入力が必要です。"
            )

        elif role == "bomber":
            # 現在のAPIでは plant/detonate を区別できないため、
            # 初回は設置扱い。
            if p.get("bomb_target") is None:
                p["bomb_target"] = target_id
                reports.append(
                    f"【ボマー】{p['name']} が爆弾を仕掛けました。"
                )

        elif role == "thief":
            attacks.append(("thief", pid, target_id))

        elif role == "ghost":
            target = room.players[target_id]
            p["candle_target"] = target_id

        # Foolは何もしない

    # --------------------------------------------------------
    # 8. ドクター蘇生
    #    「その夜に死亡した人」を蘇生できるようにする。
    # --------------------------------------------------------
    # 現段階では死亡対象を一旦集計してから蘇生する。
    killed_ids = set()

    # インポスター
    for kind, actor_id, target_id in attacks:
        if kind != "imposter":
            continue

        target = room.players.get(target_id)
        if not target or not target["alive"]:
            continue

        # Doctorが対象を訪問していれば蘇生対象
        if target_id in doctor_targets:
            continue

        killed_ids.add(target_id)

    # Serial Killer
    for kind, actor_id, target_id in attacks:
        if kind != "serial_killer":
            continue

        target = room.players.get(target_id)
        if not target or not target["alive"]:
            continue

        # SKはDoctorでは止まらない
        killed_ids.add(target_id)

    # Thief
    for kind, actor_id, target_id in attacks:
        if kind != "thief":
            continue

        thief = room.players.get(actor_id)
        target = room.players.get(target_id)

        if not thief or not thief["alive"] or not target or not target["alive"]:
            continue

        killed_ids.add(target_id)

    # サバイバー処理
    for target_id in list(killed_ids):
        target = room.players[target_id]

        if actual_role(target) == "survivor" and target["survivor_revives"] > 0:
            target["survivor_revives"] -= 1
            killed_ids.remove(target_id)
            reports.append(
                f"【サバイバー】{target['name']} は復活しました。"
                f"（残り{target['survivor_revives']}回）"
            )

    # 実際に死亡
    for target_id in killed_ids:
        target = room.players[target_id]
        if target["alive"]:
            target["alive"] = False

            # Cleaner対象なら役職不明
            if target_id in cleaner_targets:
                target["cleaned"] = True

            set_public_role(target)
            dead_names.append(target["name"])

    # --------------------------------------------------------
    # 9. シーフの役職盗み
    # --------------------------------------------------------
    for kind, actor_id, target_id in attacks:
        if kind != "thief":
            continue

        thief = room.players.get(actor_id)
        target = room.players.get(target_id)

        if not thief or not target:
            continue

        stolen = actual_role(target)
        thief["stolen_role"] = stolen
        thief["uses_remaining"] = target.get("uses_remaining")

        # シーフ自身の真の役職はthiefのまま保持し、
        # 勝利条件・能力だけ盗んだ役職を参照する。
        reports.append(
            f"【シーフ】{thief['name']} は {target['name']} の役職を盗みました。"
        )

    # --------------------------------------------------------
    # 10. 訪問履歴を更新
    # --------------------------------------------------------
    for pid, action in room.actions.items():
        p = room.players.get(pid)
        if not p:
            continue

        target_id = action.get("target_id")
        if action["type"] != "pass" and target_id:
            p["last_target"] = target_id

    # --------------------------------------------------------
    # 11. 個別情報をまとめる
    # --------------------------------------------------------
    for p in room.players.values():
        if p["private_reports"]:
            reports.extend(
                [f"【{p['name']}への個別情報】" + r for r in p["private_reports"]]
            )

    # --------------------------------------------------------
    # 12. 勝敗判定
    # --------------------------------------------------------
    winner = check_win_condition(room)

    if winner:
        room.winner_faction = winner
        room.phase = "RESULT"
        room.message = f"ゲーム終了！勝者: {winner}"
        room.actions = {}
        return

    room.message = "夜が明けました。"
    if dead_names:
        room.message += f" 昨晩の犠牲者: {', '.join(dead_names)}"
    if reports:
        room.message += " " + " / ".join(reports)

    room.phase = "DAY"
    room.actions = {}


# ============================================================
# 投票
# ============================================================

@app.post("/api/room/{room_code}/vote")
def send_vote(room_code: str, data: dict):
    room = get_room(room_code)

    if room.phase != "DAY":
        raise HTTPException(status_code=400, detail="現在は昼ではありません")

    player_id = data.get("player_id")
    target_id = data.get("target_id")

    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="プレイヤーが見つかりません")

    if not room.players[player_id]["alive"]:
        raise HTTPException(status_code=400, detail="死亡中は投票できません")

    if target_id != "pass":
        validate_target(room, player_id, target_id)

    room.votes[player_id] = target_id

    alive = alive_ids(room)

    if all(pid in room.votes for pid in alive):
        resolve_voting(room)

    return {"status": "success"}


def resolve_voting(room):
    vote_counts = {}

    for voter_id, target in room.votes.items():
        if not target or target == "pass":
            continue

        vote_counts[target] = vote_counts.get(target, 0) + 1

    # 挑発者の+2票
    for pid, p in room.players.items():
        if not p["alive"]:
            continue

        bonus = p.get("bonus_votes", 0)
        if bonus and pid in vote_counts:
            vote_counts[pid] += bonus

    alive_count = sum(1 for p in room.players.values() if p["alive"])
    majority_threshold = alive_count / 2

    exiled = None

    if vote_counts:
        top_target, max_votes = max(vote_counts.items(), key=lambda x: x[1])

        # 同票トップは追放なし
        top_targets = [
            target for target, count in vote_counts.items()
            if count == max_votes
        ]

        if len(top_targets) == 1 and max_votes > majority_threshold:
            exiled = top_target

    if exiled:
        exiled_p = room.players[exiled]
        exiled_p["alive"] = False

        # Cleaner対象なら役職非公開
        if exiled in [
            pid for pid, action in room.actions.items()
            if action.get("type") == "cleaner"
        ]:
            exiled_p["cleaned"] = True

        set_public_role(exiled_p)

        room.message = (
            f"投票の結果、{exiled_p['name']} が "
            f"過半数の票（{vote_counts[exiled]}票）により追放されました。"
        )

        # ゴーストの復讐対象を次の夜に持ち越す
        if actual_role(exiled_p) == "ghost":
            candle = exiled_p.get("candle_target")
            if candle and candle in room.players:
                room.ghost_revenge_target = candle
                room.message += " ゴーストの復讐は次の夜に発動します。"

    else:
        if vote_counts:
            room.message = (
                "最多得票者はいましたが、過半数に達しなかったため、"
                "誰も追放されませんでした。"
            )
        else:
            room.message = "有効な投票がなかったため、誰も追放されませんでした。"

    winner = check_win_condition(room)

    if winner:
        room.winner_faction = winner
        room.phase = "RESULT"
        room.message += f" ゲーム終了！勝者: {winner}"
    else:
        room.votes = {}

        # 挑発者の一時+2票をリセット
        for p in room.players.values():
            p["bonus_votes"] = 0

        room.phase = "NIGHT"
        room.day_count += 1

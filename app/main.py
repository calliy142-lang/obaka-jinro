from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from pathlib import Path
import random
import uuid

app = FastAPI()

# main.py は obaka_jinro/app/、static は obaka_jinro/static/ にあるため、
# 起動したカレントディレクトリに依存しないパスにする。
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

    "blaimer": {"camp": "imposter", "name": "ブレイマー"},
    "cleaner": {"camp": "imposter", "name": "クリーナー"},

    "serial_killer": {"camp": "neutral", "name": "シリアルキラー"},
    "bomber": {"camp": "neutral", "name": "ボマー"},
    "survivor": {"camp": "neutral", "name": "サバイバー"},
    "thief": {"camp": "neutral", "name": "シーフ"},
    "ghost": {"camp": "neutral", "name": "ゴースト"},
    "magician": {"camp": "neutral", "name": "魔術師"},
}

ROLE_BY_NAME = {v["name"]: k for k, v in ROLE_CONFIGS.items()}

ABILITY_LIMITS = {
    "mouse": 1,
    "provoker": 2,
    "blaimer": 2,
    "survivor": 3,
}

# Fool can visually appear as an Innocent role, but not Provoker.
FOOL_FAKE_ROLES = [
    "doctor", "mouse", "police", "trapper", "lookout",
    "investigator", "tracker"
]

# インポスター陣営が持てるイノセント系役職。
# ドクターとバカはインポスター対象外。
IMPOSTER_ELIGIBLE_INNOCENT_ROLES = [
    "mouse", "police", "trapper", "lookout",
    "investigator", "provoker", "tracker"
]


class Room:
    def __init__(self, room_code):
        self.room_code = room_code
        self.players = {}
        self.host_id = None
        self.phase = "SETUP"
        self.day_count = 1
        self.day_timer = 600
        self.distribution_mode = "individual"
        self.role_distribution = {role: 0 for role in ROLE_CONFIGS}
        self.role_distribution["doctor"] = 1
        self.role_distribution["police"] = 1
        self.role_distribution["investigator"] = 1
        self.faction_distribution = {"innocent": 2, "imposter": 1, "neutral": 0}

        self.actions = {}
        self.votes = {}
        self.night_events = []
        self.public_events = []
        self.winner_faction = None
        self.winners = []
        self.last_vote_result = None
        self.message = ""

        self.pending_mouse_reports = []
        self.pending_investigator_reports = {}
        self.pending_public_reports = []

        self.ghost_revenge_pending = False
        self.ghost_revenge_target = None

        self.next_day_messages = []


class SettingsRequest(BaseModel):
    host_player_id: str
    day_timer: Optional[int] = 600
    distribution_mode: Optional[str] = "individual"
    role_distribution: Optional[Dict[str, int]] = None
    faction_distribution: Optional[Dict[str, int]] = None


class StartRequest(BaseModel):
    host_player_id: str


class ActionRequest(BaseModel):
    player_id: str
    target_id: Optional[str] = None
    guessed_role: Optional[str] = None
    bomb_action: Optional[str] = None


class VoteRequest(BaseModel):
    player_id: str
    target_id: str


def role_name(role_id):
    return ROLE_CONFIGS.get(role_id, {}).get("name", "不明")


def add_report(player, text):
    player.setdefault("private_reports", [])
    player["private_reports"].append(text)


def add_public_report(room, text):
    room.pending_public_reports.append(text)


def alive_players(room):
    return [p for p in room.players.values() if p["alive"]]


def alive_ids(room):
    return {p["id"] for p in alive_players(room)}


def get_camp(player):
    camp = player.get("camp")
    if camp:
        return camp
    role = player.get("role")
    return ROLE_CONFIGS.get(role, {}).get("camp")


def get_effective_role(player):
    return player.get("stolen_role") or player["role"]


def role_is(player, role):
    return get_effective_role(player) == role


def is_visiting_role(role):
    return role in {
        "doctor", "mouse", "police", "trapper", "lookout",
        "investigator", "provoker", "tracker",
        "blaimer", "cleaner", "serial_killer", "bomber",
        "thief", "ghost"
    }


def is_attack_role(role):
    return role in {"serial_killer", "thief"}


def public_role_for(room, target):
    if target.get("public_role_unknown"):
        return "不明"

    if target.get("cleaned"):
        return "不明"

    return role_name(target["role"])


def display_role_for(player):
    if player["role"] == "fool":
        return role_name(player["displayed_role"])
    return role_name(player.get("stolen_role") or player["role"])


def camp_name(camp):
    return {"innocent": "イノセント", "imposter": "インポスター", "neutral": "ニュートラル"}.get(camp, "不明")


def create_player(name, player_id, is_host=False):
    return {
        "id": player_id,
        "name": name,
        "role": None,
        "camp": None,
        "displayed_role": None,
        "stolen_role": None,
        "alive": True,
        "is_host": is_host,

        "ability_uses_remaining": {},
        "last_target": None,

        "survivor_revives": 3,

        "candle_target_id": None,
        "ghost_revenge_pending": False,

        "bomb_targets": [],
        "bomb_planted": False,

        "cleaned": False,
        "public_role_unknown": False,

        "private_reports": [],
        "day_announcements": [],

        "investigator_results": [],
        "mouse_results": [],

        "provoked_bonus": 0,
        "provoked_target_id": None,

        "visited_last_night": None,
        "visited_by": [],

        "alive_at_start_of_game": True,
    }


def assign_role(player, role):
    player["role"] = role
    player["camp"] = ROLE_CONFIGS[role]["camp"]
    player["displayed_role"] = role

    if role == "fool":
        fake = random.choice(FOOL_FAKE_ROLES)
        player["displayed_role"] = fake

    for ability, uses in ABILITY_LIMITS.items():
        if role == ability:
            player["ability_uses_remaining"][ability] = uses


def _role_is_impostor_eligible(role):
    return role in IMPOSTER_ELIGIBLE_INNOCENT_ROLES


def _role_allowed_in_camp(role, camp):
    if role not in ROLE_CONFIGS:
        return False
    base_camp = ROLE_CONFIGS[role]["camp"]
    if camp == "neutral":
        return base_camp == "neutral"
    if camp == "imposter":
        # インポスターは独立役職ではない。対象イノセント系役職だけを持つ。
        return _role_is_impostor_eligible(role) or base_camp == "imposter"
    # innocent
    return base_camp == "innocent"


def _validate_distribution(room):
    player_count = len(room.players)
    faction = {c: max(0, int(room.faction_distribution.get(c, 0)))
               for c in ["innocent", "imposter", "neutral"]}

    if sum(faction.values()) != player_count:
        raise HTTPException(
            status_code=400,
            detail=f"陣営人数の合計を参加人数({player_count}人)に合わせてください。現在は{sum(faction.values())}人です。"
        )

    role_counts = {role: max(0, int(room.role_distribution.get(role, 0)))
                   for role in ROLE_CONFIGS}

    # 個別指定は「第2優先」。指定役職が陣営枠を超える場合は開始不可。
    fixed_by_camp = {"innocent": 0, "imposter": 0, "neutral": 0}
    flexible_counts = []
    for role, count in role_counts.items():
        if count <= 0:
            continue
        base = ROLE_CONFIGS[role]["camp"]
        if base == "neutral":
            fixed_by_camp["neutral"] += count
        elif base == "imposter":
            fixed_by_camp["imposter"] += count
        elif role in IMPOSTER_ELIGIBLE_INNOCENT_ROLES:
            flexible_counts.append((role, count))
        else:
            fixed_by_camp["innocent"] += count

    for camp in fixed_by_camp:
        if fixed_by_camp[camp] > faction[camp]:
            raise HTTPException(
                status_code=400,
                detail=f"{camp}陣営の個別役職指定が陣営人数を超えています。"
            )

    # 柔軟役職（ねずみ等）は、まずイノセント枠、足りなければインポスター枠へ。
    remaining = {c: faction[c] - fixed_by_camp[c] for c in faction}
    for role, count in flexible_counts:
        if count > remaining["innocent"] + remaining["imposter"]:
            raise HTTPException(
                status_code=400,
                detail=f"役職「{role_name(role)}」の個別指定数が残りの陣営枠を超えています。"
            )
        use_innocent = min(count, remaining["innocent"])
        remaining["innocent"] -= use_innocent
        remaining["imposter"] -= count - use_innocent


def choose_roles_combined(room):
    """陣営人数を最優先し、個別役職指定を次に反映、残りを0指定役職からランダム補充する。"""
    _validate_distribution(room)

    players = list(room.players.values())
    random.shuffle(players)

    faction_counts = {c: int(room.faction_distribution.get(c, 0))
                      for c in ["innocent", "imposter", "neutral"]}
    faction_players = {}
    cursor = 0
    for camp in ["innocent", "imposter", "neutral"]:
        faction_players[camp] = players[cursor:cursor + faction_counts[camp]]
        cursor += faction_counts[camp]

    role_counts = {role: max(0, int(room.role_distribution.get(role, 0)))
                   for role in ROLE_CONFIGS}
    assigned = {camp: [] for camp in faction_players}

    # 1) 固定陣営の個別指定。
    for role, count in role_counts.items():
        if count <= 0:
            continue
        base = ROLE_CONFIGS[role]["camp"]
        if base == "neutral":
            target_camp = "neutral"
        elif base == "imposter":
            target_camp = "imposter"
        elif role in IMPOSTER_ELIGIBLE_INNOCENT_ROLES:
            continue
        else:
            target_camp = "innocent"
        assigned[target_camp].extend([role] * count)

    # 2) 柔軟なイノセント系役職は、空いているイノセント枠を優先。
    for role, count in role_counts.items():
        if count <= 0 or role not in IMPOSTER_ELIGIBLE_INNOCENT_ROLES:
            continue
        available_i = faction_counts["innocent"] - len(assigned["innocent"])
        take_i = min(count, max(0, available_i))
        assigned["innocent"].extend([role] * take_i)
        assigned["imposter"].extend([role] * (count - take_i))

    # 3) 残り枠は「個別指定0」の役職からランダム。
    zero_roles = [r for r, n in role_counts.items() if n == 0]
    pools = {
        "innocent": [r for r in zero_roles if _role_allowed_in_camp(r, "innocent")],
        "imposter": [r for r in zero_roles if _role_allowed_in_camp(r, "imposter")],
        "neutral": [r for r in zero_roles if _role_allowed_in_camp(r, "neutral")],
    }

    for camp in ["innocent", "imposter", "neutral"]:
        need = faction_counts[camp] - len(assigned[camp])
        if need < 0:
            raise HTTPException(status_code=400, detail=f"{camp}陣営の役職指定が人数を超えています。")
        if need and not pools[camp]:
            raise HTTPException(status_code=400, detail=f"{camp}陣営の残り枠に割り当て可能な役職がありません。")
        assigned[camp].extend(random.choices(pools[camp], k=need))

    # 4) 実プレイヤーへ割り当て。
    for camp in ["innocent", "imposter", "neutral"]:
        random.shuffle(assigned[camp])
        if len(assigned[camp]) != faction_counts[camp]:
            raise HTTPException(status_code=500, detail="役職配分の内部計算に失敗しました。")
        for player, role in zip(faction_players[camp], assigned[camp]):
            assign_role(player, role)
            if camp == "imposter" and role not in IMPOSTER_ELIGIBLE_INNOCENT_ROLES and role not in {"blaimer", "cleaner"}:
                raise HTTPException(status_code=500, detail="不正なインポスター役職が割り当てられました。")
            player["camp"] = camp


def validate_target(room, player_id, target_id, allow_self=False):
    if not target_id or target_id == "pass":
        return None

    if target_id not in room.players:
        raise HTTPException(status_code=400, detail="対象プレイヤーが存在しません")

    target = room.players[target_id]

    if not target["alive"]:
        raise HTTPException(status_code=400, detail="死亡しているプレイヤーは対象にできません")

    if not allow_self and target_id == player_id:
        raise HTTPException(status_code=400, detail="自分自身は対象にできません")

    return target


def can_use_limited(player, role):
    if role not in ABILITY_LIMITS:
        return True
    return player["ability_uses_remaining"].get(role, 0) > 0


def consume_use(player, role):
    if role in ABILITY_LIMITS:
        player["ability_uses_remaining"][role] = max(
            0, player["ability_uses_remaining"].get(role, 0) - 1
        )


def check_role_action_valid(room, player, target, action):
    role = get_effective_role(player)

    if role == "survivor":
        return

    if role == "magician":
        if not target:
            raise HTTPException(status_code=400, detail="魔術師は対象を選んでください")
        if not action.get("guessed_role"):
            raise HTTPException(status_code=400, detail="予想役職を選んでください")
        return

    if role == "bomber":
        bomb_action = action.get("bomb_action", "plant")

        if bomb_action == "detonate":
            if not player.get("bomb_targets"):
                raise HTTPException(status_code=400, detail="仕掛けた爆弾がありません")
            return

        if not target:
            raise HTTPException(status_code=400, detail="爆弾を仕掛ける家を選んでください")
        return

    if role in {
        "doctor", "police"
    }:
        if not target:
            raise HTTPException(status_code=400, detail="対象を選んでください")

        if player.get("last_target") == target["id"]:
            raise HTTPException(
                status_code=400,
                detail="同じ対象を2夜連続で選ぶことはできません"
            )
        return

    if role in {
        "mouse", "trapper", "lookout", "investigator",
        "provoker", "tracker", "blaimer",
        "cleaner", "serial_killer", "thief", "ghost"
    }:
        if not target:
            raise HTTPException(status_code=400, detail="対象を選んでください")

    if role == "provoker" and player["role"] == "fool":
        raise HTTPException(status_code=400, detail="バカは挑発者の能力を使用できません")

    if not can_use_limited(player, role):
        raise HTTPException(status_code=400, detail="この能力はもう使用できません")


def record_visit(room, actor, target_id):
    target = room.players.get(target_id)
    if not target:
        return

    target.setdefault("visited_by", []).append(actor["id"])
    actor["visited_last_night"] = target_id


def reveal_public_death(room, player):
    role_text = public_role_for(room, player)
    add_public_report(
        room,
        f"{player['name']} が死亡しました。役職: {role_text}"
    )


def kill_player(room, player, cause="unknown", reveal=True):
    if not player["alive"]:
        return False

    player["alive"] = False

    if reveal:
        reveal_public_death(room, player)

    return True


def try_survivor_revive(player):
    if player["role"] != "survivor":
        return False

    if player["survivor_revives"] <= 0:
        return False

    player["survivor_revives"] -= 1
    player["alive"] = True
    return True


def resolve_night(room):
    actions = dict(room.actions)

    # Start-of-night state.
    for p in room.players.values():
        p["visited_by"] = []
        p["visited_last_night"] = None

    blocked_by_police = set()
    trapped_houses = set()
    trapped_actor_ids = set()
    doctor_targets = set()

    visitors_by_house = {}

    # 1) Register ordinary visits.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        role = get_effective_role(actor)

        if role == "magician":
            continue

        if role == "bomber" and action.get("bomb_action") == "detonate":
            continue

        target_id = action.get("target_id")
        if target_id and target_id != "pass":
            record_visit(room, actor, target_id)
            visitors_by_house.setdefault(target_id, []).append(actor)

    # 2) Police blocks.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        if get_effective_role(actor) != "police":
            continue

        target_id = action.get("target_id")
        target = room.players.get(target_id)

        if not target:
            continue

        target_role = get_effective_role(target)

        # SK cannot be stopped by Police.
        if target_role == "serial_killer":
            add_report(actor, f"{target['name']} はポリスでは止められませんでした。")
            continue

        blocked_by_police.add(target_id)
        add_report(target, "ポリスによって今夜の能力を封じられました。")

    # Police knows if target did not go out/use ability.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue
        if get_effective_role(actor) != "police":
            continue

        target_id = action.get("target_id")
        target = room.players.get(target_id)
        if not target:
            continue

        if target_id not in visitors_by_house:
            add_report(actor, f"{target['name']} は今夜、家を出ませんでした。")

    # 3) Trapper: choose one random visitor to the trapped house.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue
        if get_effective_role(actor) != "trapper":
            continue

        target_id = action.get("target_id")
        if not target_id:
            continue

        trapped_houses.add(target_id)

        candidates = [
            v for v in visitors_by_house.get(target_id, [])
            if v["id"] != actor["id"]
            and get_effective_role(v) != "serial_killer"
            and get_effective_role(v) != "magician"
        ]

        if candidates:
            victim = random.choice(candidates)
            trapped_actor_ids.add(victim["id"])
            add_report(victim, "今夜、罠にかかって能力を封じられました。")

    # 4) Doctor protection.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        if get_effective_role(actor) != "doctor":
            continue

        target = room.players.get(action.get("target_id"))
        if not target:
            continue

        if pid in blocked_by_police or pid in trapped_actor_ids:
            continue

        doctor_targets.add(target["id"])
        add_report(target, "ドクターがあなたを訪問しました。")

    # 5) Resolve informational abilities.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        role = get_effective_role(actor)

        if pid in blocked_by_police or pid in trapped_actor_ids:
            continue

        target = room.players.get(action.get("target_id"))
        if not target and role not in {"bomber"}:
            continue

        if role == "mouse":
            actual_role = target["role"]
            actual_camp = get_camp(target)

            # Fool displayed as Mouse still gets a random result.
            if actor["role"] == "fool":
                fake_role = random.choice(list(ROLE_CONFIGS.keys()))
                fake_camp = ROLE_CONFIGS[fake_role]["camp"]
                result = f"{target['name']} は {role_name(fake_role)} / {fake_camp}"
            else:
                result = f"{target['name']} は {role_name(actual_role)} / {actual_camp}"

            actor["mouse_results"].append(result)
            room.pending_mouse_reports.append(
                f"{actor['name']} がねずみの調査を使用しました: {result}"
            )

        elif role == "investigator":
            target_role = target["role"]
            target_camp = get_camp(target)

            if target_camp == "innocent":
                wrong_pool = [
                    r for r in ROLE_CONFIGS
                    if ROLE_CONFIGS[r]["camp"] in {"imposter", "neutral"}
                ]
            else:
                wrong_pool = [
                    r for r in ROLE_CONFIGS
                    if ROLE_CONFIGS[r]["camp"] == "innocent"
                    and r != "fool"
                ]

            wrong = random.choice(wrong_pool)
            choices = [target_role, wrong]
            random.shuffle(choices)

            result = " / ".join(role_name(r) for r in choices)
            actor["investigator_results"].append(
                f"{target['name']} の役職候補: {result}"
            )

        elif role == "lookout":
            visitors = []

            for visitor in visitors_by_house.get(target["id"], []):
                visitor_role = get_effective_role(visitor)

                if visitor_role == "serial_killer":
                    continue

                if visitor["id"] in trapped_actor_ids:
                    continue

                visitors.append(visitor["name"])

            if visitors:
                add_report(
                    actor,
                    f"{target['name']} の家を訪れたのは: {', '.join(visitors)}"
                )
            else:
                add_report(
                    actor,
                    f"{target['name']} の家を訪れた人はいませんでした。"
                )

        elif role == "tracker":
            target_role = get_effective_role(target)

            if target_role == "serial_killer":
                add_report(
                    actor,
                    f"{target['name']} の足跡は追跡できませんでした。"
                )
            else:
                visited = target.get("visited_last_night")
                if visited and visited in room.players:
                    add_report(
                        actor,
                        f"{target['name']} は {room.players[visited]['name']} の家を訪れました。"
                    )
                else:
                    add_report(
                        actor,
                        f"{target['name']} は今夜、家を出ませんでした。"
                    )

        elif role == "provoker":
            target["provoked_bonus"] = 2
            target["provoked_target_id"] = actor["id"]

            if actor["role"] != "fool":
                consume_use(actor, "provoker")

        elif role == "blaimer":
            target["cleaned_by_blaimer"] = True
            consume_use(actor, "blaimer")

        elif role == "cleaner":
            target["cleaned_by_cleaner"] = True

        elif role == "trapper":
            pass

        elif role == "ghost":
            actor["candle_target_id"] = target["id"]

    # 6) Bomb planting/detonation.
    bomb_detonations = set()

    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        role = get_effective_role(actor)

        if role != "bomber":
            continue

        if pid in blocked_by_police or pid in trapped_actor_ids:
            continue

        bomb_action = action.get("bomb_action", "plant")

        if bomb_action == "detonate":
            bomb_detonations.update(actor.get("bomb_targets", []))
            actor["bomb_targets"] = []
            actor["bomb_planted"] = False
        else:
            target_id = action.get("target_id")
            if target_id:
                actor.setdefault("bomb_targets", []).append(target_id)
                actor["bomb_planted"] = True

    # 7) Attacks.
    attacks = []

    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        role = get_effective_role(actor)

        if role == "serial_killer":
            target = room.players.get(action.get("target_id"))
            if target:
                attacks.append({
                    "attacker": actor,
                    "target": target,
                    "cause": "serial_killer",
                    "doctor_savable": True
                })

        elif role == "thief":
            if pid in blocked_by_police or pid in trapped_actor_ids:
                continue

            target = room.players.get(action.get("target_id"))
            if target:
                attacks.append({
                    "attacker": actor,
                    "target": target,
                    "cause": "thief",
                    "doctor_savable": True
                })

    # Wizard attack does not visit and cannot be stopped.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor or not actor["alive"]:
            continue

        if get_effective_role(actor) != "magician":
            continue

        target = room.players.get(action.get("target_id"))
        if not target:
            continue

        guessed = action.get("guessed_role")

        if guessed == target["role"]:
            attacks.append({
                "attacker": actor,
                "target": target,
                "cause": "magician",
                "doctor_savable": False
            })
        else:
            attacks.append({
                "attacker": actor,
                "target": actor,
                "cause": "magician_wrong_guess",
                "doctor_savable": False
            })

    # Bomb detonation cannot be stopped by Police.
    for house_id in bomb_detonations:
        target = room.players.get(house_id)
        if target and target["alive"]:
            attacks.append({
                "attacker": None,
                "target": target,
                "cause": "bomber",
                "doctor_savable": False
            })

    # Ghost revenge occurs on the night after Ghost was voted out.
    if room.ghost_revenge_pending and room.ghost_revenge_target:
        target = room.players.get(room.ghost_revenge_target)

        if target and target["alive"]:
            attacks.append({
                "attacker": None,
                "target": target,
                "cause": "ghost_revenge",
                "doctor_savable": False
            })

        room.ghost_revenge_pending = False
        room.ghost_revenge_target = None

    # 8) Resolve deaths.
    death_causes = {}

    for attack in attacks:
        target = attack["target"]

        if not target["alive"]:
            continue

        cause = attack["cause"]

        # Survivor can self-revive against night attacks.
        if target["role"] == "survivor" and cause not in {
            "ghost_revenge"
        }:
            if try_survivor_revive(target):
                add_public_report(
                    room,
                    f"{target['name']} はサバイバーの能力で生き残りました。"
                )
                continue

        # Doctor saves attacks that are doctor-savable.
        if (
            attack["doctor_savable"]
            and target["id"] in doctor_targets
            and cause not in {"serial_killer"}
        ):
            add_public_report(
                room,
                f"{target['name']} はドクターによって救われました。"
            )
            continue

        if cause == "serial_killer":
            kill_player(
                room,
                target,
                cause=cause,
                reveal=False
            )
            target["public_role_unknown"] = True

        elif cause == "ghost_revenge":
            kill_player(
                room,
                target,
                cause=cause,
                reveal=False
            )
            target["public_role_unknown"] = True

        else:
            kill_player(
                room,
                target,
                cause=cause,
                reveal=True
            )

        death_causes[target["id"]] = cause

    # 9) Apply Cleaner / Blamer public role effects.
    for player in room.players.values():
        if not player["alive"]:
            if player.get("cleaned_by_cleaner") or player.get("cleaned_by_blaimer"):
                player["cleaned"] = True
                player["public_role_unknown"] = True

    # 10) Thief steals the first successfully killed target.
    for pid, action in actions.items():
        thief = room.players.get(pid)

        if not thief or not thief["alive"]:
            continue

        if get_effective_role(thief) != "thief":
            continue

        target = room.players.get(action.get("target_id"))

        if target and not target["alive"] and target["id"] in death_causes:
            thief["stolen_role"] = target["role"]
            thief["camp"] = get_camp(target)

            if target["role"] == "bomber":
                thief["bomb_targets"] = list(target.get("bomb_targets", []))

            add_public_report(
                room,
                f"{thief['name']} が役職を奪いました。"
            )

    # 11) Consume uses after successful actions.
    for pid, action in actions.items():
        actor = room.players.get(pid)
        if not actor:
            continue

        role = get_effective_role(actor)

        if role == "mouse" and actor["alive"]:
            if actor["role"] != "fool":
                consume_use(actor, "mouse")

        if role == "doctor":
            actor["last_target"] = action.get("target_id")

        if role == "police":
            actor["last_target"] = action.get("target_id")

    # Public reports from mouse.
    for report in room.pending_mouse_reports:
        add_public_report(room, report)
    room.pending_mouse_reports.clear()

    # Investigator reports are private.
    for player in room.players.values():
        if player["investigator_results"]:
            for result in player["investigator_results"][-1:]:
                add_report(player, result)

    # Clear temporary vote bonuses only after the relevant day has happened.
    # Current night's Provoker bonuses are intended for the following day.

    room.actions = {}
    room.phase = "DAY"

    room.next_day_messages = list(room.pending_public_reports)
    room.pending_public_reports.clear()

    room.message = "\n".join(room.next_day_messages)

    if check_win_condition(room):
        return

    room.day_count += 1


def check_win_condition(room):
    alive = alive_players(room)

    if not alive:
        room.phase = "RESULT"
        room.winner_faction = "draw"
        room.winners = []
        room.message = "全員死亡しました。"
        return True

    # Ghost: once its revenge kill succeeds, Ghost wins.
    if room.ghost_revenge_target:
        pass

    imposters = [
        p for p in alive
        if get_camp(p) == "imposter"
    ]
    innocents = [
        p for p in alive
        if get_camp(p) == "innocent"
    ]
    neutrals = [
        p for p in alive
        if get_camp(p) == "neutral"
    ]

    # Serial Killer wins when everyone else is dead.
    sks = [p for p in neutrals if get_effective_role(p) == "serial_killer"]
    if sks and len(alive) == len(sks):
        room.phase = "RESULT"
        room.winner_faction = "serial_killer"
        room.winners = [p["name"] for p in sks]
        room.message = "シリアルキラーの勝利！"
        return True

    # Bomber wins when everyone else is dead.
    bombers = [p for p in neutrals if get_effective_role(p) == "bomber"]
    if bombers and len(alive) == len(bombers):
        room.phase = "RESULT"
        room.winner_faction = "bomber"
        room.winners = [p["name"] for p in bombers]
        room.message = "ボマーの勝利！"
        return True

    # Ghost revenge kill is a special victory.
    if room.message.startswith("GHOST_WIN:"):
        room.phase = "RESULT"
        room.winner_faction = "ghost"
        room.winners = [room.message.split(":", 1)[1]]
        room.message = "ゴーストの勝利！"
        return True

    # Normal faction win.
    if not imposters and not neutrals:
        room.phase = "RESULT"
        room.winner_faction = "innocent"
        room.winners = [p["name"] for p in alive]
        room.message = "イノセント陣営の勝利！"
        return True

    if imposters and len(imposters) >= len(innocents) + len(neutrals):
        room.phase = "RESULT"
        room.winner_faction = "imposter"
        room.winners = [p["name"] for p in imposters]
        room.message = "インポスター陣営の勝利！"
        return True

    # Survivor wins if alive at game end.
    # We only end here if a faction already ended the game, so this is
    # checked when resolving a vote below as well.
    return False



def reset_room_for_rematch(room):
    """ゲーム終了後、同じメンバー・同じルームで再戦できる状態に戻す。"""
    room.phase = "SETUP"
    room.day_count = 1
    room.actions = {}
    room.votes = {}
    room.night_events = []
    room.public_events = []
    room.pending_mouse_reports = []
    room.pending_investigator_reports = {}
    room.pending_public_reports = []
    room.next_day_messages = []

    room.winner_faction = None
    room.winners = []
    room.last_vote_result = None
    room.message = "再戦準備完了。ホストがゲームを開始できます。"

    room.ghost_revenge_pending = False
    room.ghost_revenge_target = None

    for player in room.players.values():
        # 前ゲームの役職・能力状態を完全に消す。
        player["role"] = None
        player["camp"] = None
        player["displayed_role"] = None
        player["stolen_role"] = None
        player["alive"] = True
        player["ability_uses_remaining"] = {}
        player["last_target"] = None
        player["survivor_revives"] = 3
        player["candle_target_id"] = None
        player["ghost_revenge_pending"] = False
        player["bomb_targets"] = []
        player["bomb_planted"] = False
        player["cleaned"] = False
        player["public_role_unknown"] = False
        player["private_reports"] = []
        player["day_announcements"] = []
        player["investigator_results"] = []
        player["mouse_results"] = []
        player["provoked_bonus"] = 0
        player["provoked_target_id"] = None
        player["visited_last_night"] = None
        player["visited_by"] = []
        player["alive_at_start_of_game"] = True

    # ホストはそのまま。プレイヤーも同じIDのまま残す。
    return room


@app.get("/", response_class=HTMLResponse)
async def index():
    try:
        with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>index.html がありません</h1>", status_code=404)


@app.post("/api/room/create")
async def create_room():
    room_code = uuid.uuid4().hex[:6].upper()
    room = Room(room_code)
    rooms[room_code] = room

    return {
        "room_code": room_code
    }


@app.post("/api/room/{room_code}/join")
async def join_room(room_code: str, data: Dict[str, Any]):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="ゲームはすでに開始されています")

    name = str(data.get("name", "")).strip()

    if not name:
        raise HTTPException(status_code=400, detail="プレイヤー名を入力してください")

    if any(p["name"] == name for p in room.players.values()):
        raise HTTPException(status_code=400, detail="同じ名前のプレイヤーがいます")

    player_id = uuid.uuid4().hex

    is_host = room.host_id is None

    player = create_player(
        name,
        player_id,
        is_host=is_host
    )

    room.players[player_id] = player

    if room.host_id is None:
        room.host_id = player_id

    return {
        "room_code": room.room_code,
        "player_id": player_id,
        "is_host": is_host
    }


@app.post("/api/room/{room_code}/settings")
async def update_settings(room_code: str, req: SettingsRequest):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    if room.host_id != req.host_player_id:
        raise HTTPException(status_code=403, detail="ホストのみ設定できます")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="ゲーム開始後は設定できません")

    room.day_timer = max(10, min(3600, int(req.day_timer or 600)))
    room.distribution_mode = req.distribution_mode or "individual"

    if req.role_distribution is not None:
        for role in ROLE_CONFIGS:
            room.role_distribution[role] = max(
                0,
                int(req.role_distribution.get(role, 0))
            )

    if req.faction_distribution is not None:
        for camp in ["innocent", "imposter", "neutral"]:
            room.faction_distribution[camp] = max(
                0,
                int(req.faction_distribution.get(camp, 0))
            )

    return {
        "ok": True
    }


@app.post("/api/room/{room_code}/start")
async def start_game(room_code: str, req: StartRequest):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    if room.host_id != req.host_player_id:
        raise HTTPException(status_code=403, detail="ホストのみ開始できます")

    if room.phase != "SETUP":
        raise HTTPException(status_code=400, detail="すでにゲーム中です")

    if len(room.players) < 2:
        raise HTTPException(status_code=400, detail="2人以上必要です")

    # 陣営人数を最優先し、個別役職指定を次に反映する統合方式。
    choose_roles_combined(room)

    room.phase = "NIGHT"
    room.day_count = 1
    room.message = "ゲーム開始。夜の行動を選択してください。"

    return {
        "ok": True,
        "phase": room.phase
    }



@app.post("/api/room/{room_code}/rematch")
async def rematch_room(room_code: str, req: StartRequest):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    if room.host_id != req.host_player_id:
        raise HTTPException(status_code=403, detail="ホストのみ再戦を開始できます")

    if room.phase != "RESULT":
        raise HTTPException(status_code=400, detail="ゲーム終了後のみ再戦できます")

    if len(room.players) < 2:
        raise HTTPException(status_code=400, detail="2人以上必要です")

    reset_room_for_rematch(room)

    return {
        "ok": True,
        "phase": room.phase,
        "room_code": room.room_code,
        "player_count": len(room.players),
    }


@app.get("/api/room/{room_code}/player/{player_id}")
async def get_player_info(room_code: str, player_id: str):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    player = room.players.get(player_id)

    if not player:
        raise HTTPException(status_code=404, detail="プレイヤーが存在しません")

    targets = []

    for p in alive_players(room):
        if p["id"] != player_id:
            targets.append({
                "id": p["id"],
                "name": p["name"]
            })

    if room.phase == "NIGHT":
        targets.insert(
            0,
            {
                "id": "pass",
                "name": "何もしない"
            }
        )

    # During day, pass is also available.
    if room.phase == "DAY":
        targets.insert(
            0,
            {
                "id": "pass",
                "name": "棄権"
            }
        )

    role = player["role"]

    return {
        "room_code": room.room_code,
        "player_id": player_id,
        "name": player["name"],
        "is_host": player["is_host"],

        "phase": room.phase,
        "day_count": room.day_count,
        "day_timer": room.day_timer,

        "participants": [
            {
                "id": p["id"],
                "name": p["name"],
                "alive": p["alive"],
                "is_host": p["is_host"],
            }
            for p in room.players.values()
        ],

        "alive": player["alive"],

        "displayed_role": display_role_for(player),
        "camp": get_camp(player) if room.phase != "SETUP" else None,
        "camp_name": camp_name(get_camp(player)) if room.phase != "SETUP" else None,

        "targets": targets,

        "action_submitted": player_id in room.actions,
        "vote_submitted": player_id in room.votes,

        "message": room.message,

        "private_reports": list(player.get("private_reports", [])),

        "ability_uses_remaining": dict(
            player.get("ability_uses_remaining", {})
        ),

        "winner_faction": room.winner_faction,
        "winners": list(room.winners),
        "last_vote_result": room.last_vote_result,
        "result_players": ([{"id": p["id"], "name": p["name"], "role": role_name(p.get("role")), "camp": camp_name(p.get("camp")), "alive": p["alive"]} for p in room.players.values()] if room.phase == "RESULT" else []),
    }


@app.post("/api/room/{room_code}/action")
async def send_action(room_code: str, req: ActionRequest):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    player = room.players.get(req.player_id)

    if not player:
        raise HTTPException(status_code=404, detail="プレイヤーが存在しません")

    if not player["alive"]:
        raise HTTPException(status_code=400, detail="死亡しているプレイヤーは行動できません")

    if room.phase != "NIGHT":
        raise HTTPException(status_code=400, detail="現在は夜ではありません")

    if req.player_id in room.actions:
        raise HTTPException(status_code=400, detail="すでに行動を選択しています")

    action = {
        "target_id": req.target_id,
        "guessed_role": req.guessed_role,
        "bomb_action": req.bomb_action,
    }

    role = get_effective_role(player)

    # 「何もしない」は全役職で有効な夜アクション。
    # 対象が必要な役職でも、パスを選んだ場合は能力を使わず夜を待てる。
    is_pass = req.target_id in (None, "", "pass")

    target = None

    if not is_pass:
        target = validate_target(
            room,
            req.player_id,
            req.target_id,
            allow_self=(role == "bomber")
        )

    # Fool has no real ability.
    if player["role"] == "fool":
        # Fool can submit a fake-looking action, but it has no effect.
        room.actions[req.player_id] = action
    else:
        # パスなら役職固有の「対象必須」チェックを行わない。
        if not is_pass:
            check_role_action_valid(room, player, target, action)
        room.actions[req.player_id] = action

    if len(room.actions) >= len(alive_players(room)):
        resolve_night(room)

    return {
        "ok": True,
        "phase": room.phase,
        "resolved": room.phase != "NIGHT"
    }


@app.post("/api/room/{room_code}/night/end")
async def end_night(room_code: str, req: StartRequest):
    """ホストが夜を強制終了する。未提出者は何もしない扱いで解決する。"""
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    if room.host_id != req.host_player_id:
        raise HTTPException(status_code=403, detail="ホストのみ夜を終了できます")

    if room.phase != "NIGHT":
        raise HTTPException(status_code=400, detail="現在は夜ではありません")

    resolve_night(room)

    return {
        "ok": True,
        "phase": room.phase,
        "resolved": True
    }


@app.post("/api/room/{room_code}/vote")
async def send_vote(room_code: str, req: VoteRequest):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    player = room.players.get(req.player_id)

    if not player:
        raise HTTPException(status_code=404, detail="プレイヤーが存在しません")

    if not player["alive"]:
        raise HTTPException(status_code=400, detail="死亡しているプレイヤーは投票できません")

    if room.phase != "DAY":
        raise HTTPException(status_code=400, detail="現在は昼ではありません")

    if req.player_id in room.votes:
        raise HTTPException(status_code=400, detail="すでに投票しています")

    if req.target_id != "pass":
        validate_target(
            room,
            req.player_id,
            req.target_id,
            allow_self=False
        )

    room.votes[req.player_id] = req.target_id

    if len(room.votes) >= len(alive_players(room)):
        resolve_voting(room)

    return {
        "ok": True,
        "phase": room.phase,
        "resolved": room.phase != "DAY"
    }


def resolve_voting(room):
    alive = alive_players(room)

    weighted_votes = {}

    for voter_id, target_id in room.votes.items():
        if target_id == "pass":
            continue

        if target_id not in room.players:
            continue

        target = room.players[target_id]

        if not target["alive"]:
            continue

        weighted_votes[target_id] = weighted_votes.get(target_id, 0) + 1

    # Apply Provoker's +2 bonus.
    for target in alive:
        bonus = target.get("provoked_bonus", 0)
        if bonus:
            weighted_votes[target["id"]] = (
                weighted_votes.get(target["id"], 0) + bonus
            )

    raw_votes = []
    for voter_id, target_id in room.votes.items():
        voter = room.players.get(voter_id)
        target = room.players.get(target_id) if target_id in room.players else None
        raw_votes.append({"voter": voter["name"] if voter else voter_id, "target": target["name"] if target else ("棄権" if target_id == "pass" else str(target_id))})
    room.last_vote_result = {
        "votes": raw_votes,
        "weighted_votes": [{"name": room.players[pid]["name"], "votes": count} for pid, count in weighted_votes.items() if pid in room.players],
        "expelled": None,
        "status": "pending",
    }
    room.votes = {}

    if not weighted_votes:
        room.last_vote_result["status"] = "no_exile"
        room.message = "投票は棄権されました。追放者はいません。"
        for p in alive:
            p["provoked_bonus"] = 0
            p["provoked_target_id"] = None

        room.phase = "NIGHT"
        return

    max_votes = max(weighted_votes.values())
    leaders = [
        pid for pid, count in weighted_votes.items()
        if count == max_votes
    ]

    # Tie => nobody is expelled.
    if len(leaders) != 1:
        room.last_vote_result["status"] = "tie"
        room.message = "最多票が同数だったため、誰も追放されませんでした。"

        for p in alive:
            p["provoked_bonus"] = 0
            p["provoked_target_id"] = None

        if check_win_condition(room):
            return

        room.phase = "NIGHT"
        return

    expelled = room.players[leaders[0]]
    room.last_vote_result["status"] = "expelled"
    room.last_vote_result["expelled"] = {"id": expelled["id"], "name": expelled["name"]}

    # Ghost special handling.
    if expelled["role"] == "ghost":
        expelled["alive"] = False

        target_id = expelled.get("candle_target_id")

        if target_id and target_id in room.players:
            room.ghost_revenge_pending = True
            room.ghost_revenge_target = target_id

        room.message = (
            f"{expelled['name']} が追放されました。"
            "ゴーストの復讐は次の夜に発生します。"
        )
    else:
        expelled["alive"] = False

        if expelled.get("cleaned_by_cleaner") or expelled.get("cleaned_by_blaimer"):
            expelled["public_role_unknown"] = True

        room.message = (
            f"{expelled['name']} が追放されました。"
            f"役職: {public_role_for(room, expelled)}"
        )

    # Ghost revenge target dies on next night, not immediately.
    # If the candle target has already died, revenge does not occur.
    if room.ghost_revenge_pending:
        target = room.players.get(room.ghost_revenge_target)
        if not target or not target["alive"]:
            room.ghost_revenge_pending = False
            room.ghost_revenge_target = None

    # Clear one-day provocation bonus.
    for p in room.players.values():
        p["provoked_bonus"] = 0
        p["provoked_target_id"] = None

    # Check normal end condition.
    if check_win_condition(room):
        return

    # If Ghost revenge was scheduled, go to night.
    room.phase = "NIGHT"

    # If no alive players, finish.
    if not alive_players(room):
        room.phase = "RESULT"
        room.winner_faction = "draw"
        room.message = "全員死亡しました。"


# Development helper.
@app.get("/api/room/{room_code}/debug")
async def debug_room(room_code: str):
    room = rooms.get(room_code.upper())

    if not room:
        raise HTTPException(status_code=404, detail="部屋がありません")

    # Intentionally useful during local development.
    # Do not expose this endpoint publicly in a production deployment.
    return {
        "room_code": room.room_code,
        "phase": room.phase,
        "day_count": room.day_count,
        "players": [
            {
                "id": p["id"],
                "name": p["name"],
                "role": p["role"],
                "camp": p["camp"],
                "alive": p["alive"],
                "displayed_role": p["displayed_role"],
            }
            for p in room.players.values()
        ]
    }

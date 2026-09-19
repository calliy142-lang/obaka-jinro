import random
from typing import Dict, Optional
from pydantic import BaseModel

# 人数別の配役設定（真の役職）
ROLE_TABLES = {
    3: ["IMPOSTER", "DOCTOR", "CITIZEN"],
    4: ["IMPOSTER", "DOCTOR", "POLICE", "CITIZEN"],
    5: ["IMPOSTER", "SERIAL_KILLER", "DOCTOR", "POLICE", "CITIZEN"],
    6: ["IMPOSTER", "SERIAL_KILLER", "DOCTOR", "POLICE", "CITIZEN", "CITIZEN"]
}

# 偽装（見た目）用役職リスト
DISGUISED_ROLES = ["DOCTOR", "POLICE", "CITIZEN", "INVESTIGATOR", "TRAPPER"]

class Player(BaseModel):
    id: str
    name: str
    role: Optional[str] = None           # 本来の役職
    displayed_role: Optional[str] = None # 見た目の役職
    is_alive: bool = True
    is_host: bool = False

class Room(BaseModel):
    room_code: str
    host_id: str
    players: Dict[str, Player] = {}
    phase: str = "SETUP"

    def start_game(self, requesting_player_id: str):
        if requesting_player_id != self.host_id:
            raise ValueError("ゲームを開始できるのはホストのみです")

        count = len(self.players)
        if count < 3:
            raise ValueError("ゲームを開始するには最低3名必要です")

        base_roles = ROLE_TABLES.get(count, ROLE_TABLES[6] + ["CITIZEN"] * (count - 6))
        
        shuffled_roles = base_roles.copy()
        random.shuffle(shuffled_roles)

        for idx, player in enumerate(self.players.values()):
            real_role = shuffled_roles[idx]
            player.role = real_role
            
            if real_role == "IMPOSTER":
                player.displayed_role = random.choice(DISGUISED_ROLES)
            else:
                player.displayed_role = real_role

        self.phase = "NIGHT"

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def get_room(self, code: str) -> Optional[Room]:
        return self.rooms.get(code)

    def create_room(self, code: str, host_id: str) -> Room:
        room = Room(room_code=code, host_id=host_id)
        self.rooms[code] = room
        return room

# 他のモジュールから参照されるシングルトンインスタンス
room_manager = RoomManager()
import uuid
import random
import string
from typing import Dict, Optional, List

class Player:
    def __init__(self, player_id: str, name: str, is_host: bool = False):
        self.player_id = player_id
        self.name = name
        self.is_host = is_host
        self.role = None
        self.alive = True
        self.action_submitted = False
        self.target_id = None
        self.vote_target_id = None
        self.message = ""

class Room:
    def __init__(self, room_code: str):
        self.room_code = room_code
        self.players: Dict[str, Player] = {}
        self.phase = "SETUP"  # SETUP, NIGHT, DAY, VOTE, ENDED
        self.day_count = 1
        self.winner_faction = None

class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def generate_room_code(self) -> str:
        """6桁の英大文字ランダムコードを生成"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase, k=6))
            if code not in self.rooms:
                return code

    def create_room((self) -> str:
        """部屋を新規作成して部屋コードを返す"""
        code = self.generate_room_code()
        self.rooms[code] = Room(room_code=code)
        return code

    def get_room(self, room_code: str) -> Optional[Room]:
        return self.rooms.get(room_code.upper())

    def delete_room(self, room_code: str) -> bool:
        code = room_code.upper()
        if code in self.rooms:
            del self.rooms[code]
            return True
        return False

room_manager = RoomManager()
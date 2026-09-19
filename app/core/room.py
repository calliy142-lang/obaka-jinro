import random
import string
from typing import Dict, List, Optional
from fastapi import WebSocket
from app.core.state import GameState
from app.core.engine import GameEngine

class RoomManager:
    """ルーム全体の管理とWebSocket通信のブロードキャスト制御"""

    def __init__(self):
        self.rooms: Dict[str, GameState] = {}
        self.engines: Dict[str, GameEngine] = {}
        self.connections: Dict[str, Dict[str, WebSocket]] = {}  # room_code -> {player_id: websocket}

    def generate_room_code(self) -> str:
        """4桁の英大文字ルームコードを生成"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase, k=4))
            if code not in self.rooms:
                return code

    def create_room(self) -> str:
        code = self.generate_room_code()
        state = GameState(session_id=code)
        self.rooms[code] = state
        self.engines[code] = GameEngine(state)
        self.connections[code] = {}
        return code

    def get_room(self, code: str) -> Optional[GameState]:
        return self.rooms.get(code.upper())

    def get_engine(self, code: str) -> Optional[GameEngine]:
        return self.engines.get(code.upper())

    async def connect(self, room_code: str, player_id: str, websocket: WebSocket):
        await websocket.accept()
        room_code = room_code.upper()
        if room_code not in self.connections:
            self.connections[room_code] = {}
        self.connections[room_code][player_id] = websocket

    def disconnect(self, room_code: str, player_id: str):
        room_code = room_code.upper()
        if room_code in self.connections and player_id in self.connections[room_code]:
            del self.connections[room_code][player_id]

    async def notify_room_update(self, room_code: str):
        """部屋に参加している全プレイヤーに状態更新通知を送信"""
        room_code = room_code.upper()
        if room_code in self.connections:
            for player_id, ws in list(self.connections[room_code].items()):
                try:
                    await ws.send_json({"type": "UPDATE"})
                except Exception:
                    pass

room_manager = RoomManager()

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.room import room_manager

ws_router = APIRouter()

@ws_router.websocket("/ws/{room_code}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, player_id: str):
    await room_manager.connect(room_code, player_id, websocket)
    try:
        while True:
            # 接続維持用 ping/pong 受信待機
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        room_manager.disconnect(room_code, player_id)

let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;

async function handleCreateRoom() {
    const nameInput = document.getElementById('player-name').value.trim();
    if (!nameInput) {
        alert("名前を入力してください");
        return;
    }

    try {
        const createRes = await API.createRoom();
        currentRoomCode = createRes.room_code;

        const joinRes = await API.joinRoom(currentRoomCode, nameInput);
        currentPlayerId = joinRes.player_id;

        showLobbyScreen();
        startPolling();
    } catch (err) {
        alert("エラーが発生しました: " + err.message);
    }
}

function showLobbyScreen() {
    document.getElementById('setup-screen').classList.add('hidden');
    document.getElementById('lobby-screen').classList.remove('hidden');
    document.getElementById('room-code-display').textContent = currentRoomCode;
}

async function fetchGameStatus() {
    if (!currentRoomCode || !currentPlayerId) return;

    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        
        document.getElementById('displayed-role').textContent = info.displayed_role || "未定";

        const hostControls = document.getElementById('host-controls');
        const waitingMessage = document.getElementById('waiting-message');

        if (info.is_host) {
            hostControls.classList.remove('hidden');
            waitingMessage.classList.add('hidden');
        } else {
            hostControls.classList.add('hidden');
            waitingMessage.classList.remove('hidden');
        }
    } catch (err) {
        console.error("ステータス更新失敗:", err);
    }
}

function startPolling() {
    fetchGameStatus();
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchGameStatus, 3000);
}

async function handleStartGame() {
    try {
        const res = await fetch(`/api/room/${currentRoomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId })
        });

        const data = await res.json();
        if (!res.ok) {
            alert(data.detail || "ゲーム開始に失敗しました");
            return;
        }

        alert("ゲームがスタートしました！");
        fetchGameStatus();
    } catch (err) {
        alert("通信エラーが発生しました: " + err.message);
    }
}
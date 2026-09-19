let currentState = {
    roomCode: localStorage.getItem('roomCode') || null,
    playerId: localStorage.getItem('playerId') || null,
    isHost: false,
    phase: 'lobby',
    displayedRole: '',
    isAlive: true
};

let pollInterval = null;

const createRoomBtn = document.getElementById('create-room-btn');
const joinRoomBtn = document.getElementById('join-room-btn');
const roomCodeInput = document.getElementById('room-code-input');
const playerNameInput = document.getElementById('player-name-input');
const startBtn = document.getElementById('start-game-btn');
const actionBtn = document.getElementById('send-action-btn');
const voteBtn = document.getElementById('send-vote-btn');

document.addEventListener('DOMContentLoaded', () => {
    if (createRoomBtn) createRoomBtn.addEventListener('click', handleCreateRoom);
    if (joinRoomBtn) joinRoomBtn.addEventListener('click', handleJoinRoom);
    if (startBtn) startBtn.addEventListener('click', handleStartGame);
    if (actionBtn) actionBtn.addEventListener('click', handleSendAction);
    if (voteBtn) voteBtn.addEventListener('click', handleSendVote);

    // ブラウザのリロード時、保存されたIDがあれば復元ポーリングを開始
    if (currentState.roomCode && currentState.playerId) {
        startPolling();
    } else {
        showScreen('setup-screen');
    }
});

async function handleCreateRoom() {
    const playerName = playerNameInput ? playerNameInput.value.trim() : "";
    if (!playerName) {
        alert("プレイヤー名を入力してください");
        return;
    }

    try {
        const createRes = await API.createRoom();
        currentState.roomCode = createRes.room_code;
        
        const joinRes = await API.joinRoom(currentState.roomCode, playerName);
        currentState.playerId = joinRes.player_id;
        currentState.isHost = joinRes.is_host;

        saveStateToStorage();
        startPolling();
    } catch (err) {
        alert(err.message);
    }
}

async function handleJoinRoom() {
    const roomCode = roomCodeInput ? roomCodeInput.value.trim().toUpperCase() : "";
    const playerName = playerNameInput ? playerNameInput.value.trim() : "";

    if (!roomCode || !playerName) {
        alert("部屋コードとプレイヤー名を入力してください");
        return;
    }

    try {
        const joinRes = await API.joinRoom(roomCode, playerName);
        currentState.roomCode = roomCode;
        currentState.playerId = joinRes.player_id;
        currentState.isHost = joinRes.is_host;

        saveStateToStorage();
        startPolling();
    } catch (err) {
        alert(err.message);
    }
}

function saveStateToStorage() {
    if (currentState.roomCode) localStorage.setItem('roomCode', currentState.roomCode);
    if (currentState.playerId) localStorage.setItem('playerId', currentState.playerId);
}

function clearStateStorage() {
    localStorage.removeItem('roomCode');
    localStorage.removeItem('playerId');
    currentState.roomCode = null;
    currentState.playerId = null;
}

async function handleStartGame() {
    try {
        const res = await fetch(`/api/room/${currentState.roomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentState.playerId })
        });
        if (!res.ok) {
            const data = await res.json();
            alert(data.detail || "開始に失敗しました");
        }
    } catch (err) {
        alert(err.message);
    }
}

async function handleSendAction() {
    const targetSelect = document.getElementById('action-target-select');
    const extraInput = document.getElementById('action-extra-input');
    
    const targetId = targetSelect ? targetSelect.value : null;
    const extraParam = extraInput ? extraInput.value : null;

    try {
        await API.sendAction(currentState.roomCode, currentState.playerId, targetId, extraParam);
        alert("行動を送信しました");
    } catch (err) {
        alert(err.message);
    }
}

async function handleSendVote() {
    const voteSelect = document.getElementById('vote-target-select');
    const targetId = voteSelect ? voteSelect.value : null;

    if (!targetId) {
        alert("投票先を選択してください");
        return;
    }

    try {
        await API.sendVote(currentState.roomCode, currentState.playerId, targetId);
        alert("投票を完了しました");
    } catch (err) {
        alert(err.message);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    updateGameStatus();
    pollInterval = setInterval(updateGameStatus, 2000);
}

async function updateGameStatus() {
    if (!currentState.roomCode || !currentState.playerId) return;

    try {
        const data = await API.getPlayerInfo(currentState.roomCode, currentState.playerId);
        
        currentState.phase = data.phase;
        currentState.displayedRole = data.displayed_role;
        currentState.isAlive = data.is_alive;

        renderUI(data);
    } catch (err) {
        console.error("情報更新エラー:", err);
        // サーバーが再起動された等で部屋自体が消滅している場合のみクリアして初期化
        if (err.message && err.message.includes("404")) {
            clearStateStorage();
            if (pollInterval) clearInterval(pollInterval);
            showScreen('setup-screen');
        }
    }
}

function renderUI(data) {
    const screens = ['setup-screen', 'lobby-screen', 'night-screen', 'day-screen', 'result-screen'];
    screens.forEach(s => {
        const el = document.getElementById(s);
        if (el) el.style.display = 'none';
    });

    if (data.phase === 'lobby') {
        showScreen('lobby-screen');
        updateLobbyUI(data);
    } else if (data.phase === 'night') {
        showScreen('night-screen');
        updateNightUI(data);
    } else if (data.phase === 'day' || data.phase === 'vote') {
        showScreen('day-screen');
        updateDayUI(data);
    } else if (data.phase === 'result') {
        showScreen('result-screen');
        updateResultUI(data);
    }
}

function showScreen(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
}

function updateLobbyUI(data) {
    const codeEl = document.getElementById('display-room-code');
    if (codeEl) codeEl.innerText = currentState.roomCode;

    const listEl = document.getElementById('player-list');
    if (listEl) {
        listEl.innerHTML = data.all_players.map(p => `<li>${p.name} ${p.is_host ? '(ホスト)' : ''}</li>`).join('');
    }

    if (startBtn) {
        startBtn.style.display = data.is_host ? 'block' : 'none';
    }
}

function updateNightUI(data) {
    const roleEl = document.getElementById('my-role-display');
    if (roleEl) roleEl.innerText = data.displayed_role;

    const selectEl = document.getElementById('action-target-select');
    if (selectEl) {
        selectEl.innerHTML = data.other_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    }
}

function updateDayUI(data) {
    const reportEl = document.getElementById('night-report-box');
    if (reportEl) reportEl.innerHTML = data.night_report || "昨夜は特に報告はありませんでした。";

    const selectEl = document.getElementById('vote-target-select');
    if (selectEl) {
        selectEl.innerHTML = data.other_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    }
}

function updateResultUI(data) {
    const resEl = document.getElementById('game-result-text');
    if (resEl) resEl.innerText = data.result;
    clearStateStorage(); // ゲーム決着時のみストレージ破棄
}
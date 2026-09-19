let currentRoomCode = localStorage.getItem('feign_room_code') || null;
let currentPlayerId = localStorage.getItem('feign_player_id') || null;
let pollInterval = null;
let currentPhase = null;

// 起動時にセッションがあれば自動読み込み
window.addEventListener('DOMContentLoaded', () => {
    if (currentRoomCode && currentPlayerId) {
        showGameScreen();
        startPolling();
    }
});

// 部屋作成
async function handleCreateRoom() {
    const nameInput = document.getElementById('player-name').value.trim();
    if (!nameInput) return alert("名前を入力してください");

    try {
        const createRes = await API.createRoom();
        currentRoomCode = createRes.room_code;

        const joinRes = await API.joinRoom(currentRoomCode, nameInput);
        currentPlayerId = joinRes.player_id;

        localStorage.setItem('feign_room_code', currentRoomCode);
        localStorage.setItem('feign_player_id', currentPlayerId);

        showGameScreen();
        startPolling();
    } catch (err) {
        alert("エラー: " + err.message);
    }
}

// 部屋参加
async function handleJoinRoom() {
    const nameInput = document.getElementById('player-name').value.trim();
    const roomCodeInput = document.getElementById('room-code-input').value.trim().toUpperCase();

    if (!nameInput) return alert("名前を入力してください");
    if (!roomCodeInput) return alert("部屋コードを入力してください");

    try {
        currentRoomCode = roomCodeInput;
        const joinRes = await API.joinRoom(currentRoomCode, nameInput);
        currentPlayerId = joinRes.player_id;

        localStorage.setItem('feign_room_code', currentRoomCode);
        localStorage.setItem('feign_player_id', currentPlayerId);

        showGameScreen();
        startPolling();
    } catch (err) {
        alert("参加失敗: " + err.message);
    }
}

// 部屋を出る / リセット
function handleLeaveRoom() {
    localStorage.removeItem('feign_room_code');
    localStorage.removeItem('feign_player_id');
    location.reload();
}

function showGameScreen() {
    document.getElementById('setup-screen').classList.add('hidden');
    document.getElementById('game-screen').classList.remove('hidden');
    document.getElementById('room-code-display').textContent = currentRoomCode;
}

function startPolling() {
    fetchGameStatus();
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchGameStatus, 2000);
}

// 定期ステータス取得
async function fetchGameStatus() {
    if (!currentRoomCode || !currentPlayerId) return;

    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        
        // 役職・フェーズ名表示
        document.getElementById('displayed-role').textContent = info.displayed_role || "未定";
        document.getElementById('phase-display').textContent = getPhaseName(info.phase);

        // ホスト/ゲストのボタン制御
        const hostControls = document.getElementById('host-controls');
        const waitingMessage = document.getElementById('waiting-message');

        if (info.is_host) {
            hostControls.classList.remove('hidden');
            waitingMessage.classList.add('hidden');
        } else {
            hostControls.classList.add('hidden');
            waitingMessage.classList.remove('hidden');
        }

        // ロビー参加者リスト更新
        if (info.all_players) {
            renderLobbyPlayers(info.all_players);
        }

        // フェーズが変わった時だけ画面切り替え
        const rawPhase = (info.phase || 'lobby').toLowerCase();
        if (currentPhase !== rawPhase) {
            currentPhase = rawPhase;
            updatePhaseUI(rawPhase, info);
        }

    } catch (err) {
        console.error("更新エラー:", err);
    }
}

function getPhaseName(phase) {
    if (!phase) return 'ロビー待機中';
    const p = phase.toLowerCase();
    if (p === 'setup' || p === 'lobby') return 'ロビー待機中';
    if (p === 'night') return '夜（行動選択）';
    if (p === 'day') return '昼（話し合い）';
    if (p === 'vote') return '追放投票中';
    if (p === 'result') return '勝敗発表';
    return phase;
}

// フェーズごとのUI切り替え
function updatePhaseUI(phase, info) {
    // 全フェーズ要素を一旦隠す
    document.querySelectorAll('.phase-section').forEach(el => el.classList.add('hidden'));

    if (phase === 'setup' || phase === 'lobby') {
        document.getElementById('lobby-phase').classList.remove('hidden');
    } else if (phase === 'night') {
        document.getElementById('night-phase').classList.remove('hidden');
        document.getElementById('action-btn').disabled = false;
        document.getElementById('action-status-msg').textContent = "";
        
        populatePlayerDropdown('night-target-select', info.other_players);
        
        if (info.displayed_role === '魔術師') {
            document.getElementById('extra-action-input').classList.remove('hidden');
        } else {
            document.getElementById('extra-action-input').classList.add('hidden');
        }

    } else if (phase === 'day') {
        document.getElementById('day-phase').classList.remove('hidden');
        renderLivingPlayers(info.other_players);
        
        const nightResults = document.getElementById('night-results');
        if (info.night_report) {
            nightResults.innerHTML = info.night_report;
        } else {
            nightResults.innerHTML = "昨夜の特別な通知はありません。";
        }

    } else if (phase === 'vote') {
        document.getElementById('vote-phase').classList.remove('hidden');
        document.getElementById('vote-btn').disabled = false;
        document.getElementById('vote-status-msg').textContent = "";
        populatePlayerDropdown('vote-target-select', info.other_players);

    } else if (phase === 'result') {
        document.getElementById('result-phase').classList.remove('hidden');
        if (info.result) {
            document.getElementById('result-content').innerHTML = info.result;
        }
    }
}

function populatePlayerDropdown(selectId, players) {
    const select = document.getElementById(selectId);
    select.innerHTML = '';
    if (!players || players.length === 0) return;

    players.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        select.appendChild(opt);
    });
}

function renderLobbyPlayers(players) {
    const container = document.getElementById('lobby-players-list');
    if (!container || !players) return;
    
    container.innerHTML = '';
    players.forEach(p => {
        const div = document.createElement('div');
        div.className = 'player-item';
        div.textContent = p.name + (p.is_host ? " (ホスト)" : "");
        container.appendChild(div);
    });
}

function renderLivingPlayers(players) {
    const container = document.getElementById('living-players-list');
    if (!container) return;
    
    container.innerHTML = '<strong>生存プレイヤー:</strong>';
    if (!players) return;

    players.forEach(p => {
        const div = document.createElement('div');
        div.className = 'player-item';
        div.textContent = p.name;
        container.appendChild(div);
    });
}

async function handleStartGame() {
    try {
        const res = await fetch(`/api/room/${currentRoomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId })
        });
        const data = await res.json();
        if (!res.ok) return alert(data.detail || "スタートできません");
        fetchGameStatus();
    } catch (err) {
        alert("通信エラー: " + err.message);
    }
}

async function handleSendAction() {
    const targetId = document.getElementById('night-target-select').value;
    if (!targetId) return alert("対象を選択してください");

    const guessedRole = document.getElementById('guess-role-select').value;

    try {
        const res = await API.sendAction(currentRoomCode, currentPlayerId, targetId, guessedRole);
        document.getElementById('action-status-msg').textContent = res.message || "行動を決定しました";
        document.getElementById('action-btn').disabled = true;
    } catch (err) {
        alert("送信失敗: " + err.message);
    }
}

async function handleSendVote() {
    const targetId = document.getElementById('vote-target-select').value;
    if (!targetId) return alert("対象を選択してください");

    try {
        const res = await API.sendVote(currentRoomCode, currentPlayerId, targetId);
        document.getElementById('vote-status-msg').textContent = res.message || "投票完了";
        document.getElementById('vote-btn').disabled = true;
    } catch (err) {
        alert("投票失敗: " + err.message);
    }
}
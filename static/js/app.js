let currentRoomCode = localStorage.getItem('feign_room_code') || null;
let currentPlayerId = localStorage.getItem('feign_player_id') || null;
let pollInterval = null;
let currentPhase = null;

// ページ読み込み時にセッションが残っていれば自動復帰
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

        // ブラウザ更新対策に保存
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

        // ブラウザ更新対策に保存
        localStorage.setItem('feign_room_code', currentRoomCode);
        localStorage.setItem('feign_player_id', currentPlayerId);

        showGameScreen();
        startPolling();
    } catch (err) {
        alert("参加失敗: " + err.message);
    }
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

// ステータス更新処理
async function fetchGameStatus() {
    if (!currentRoomCode || !currentPlayerId) return;

    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        
        // 1. 見た目の役職表示
        document.getElementById('displayed-role').textContent = info.displayed_role || "未定";
        document.getElementById('phase-display').textContent = getPhaseName(info.phase);

        // 2. ホストボタンの制御
        const hostControls = document.getElementById('host-controls');
        const waitingMessage = document.getElementById('waiting-message');

        if (info.is_host) {
            hostControls.classList.remove('hidden');
            waitingMessage.classList.add('hidden');
        } else {
            hostControls.classList.add('hidden');
            waitingMessage.classList.remove('hidden');
        }

        // 3. 待機中のプレイヤー一覧
        if ((info.phase === 'lobby' || info.phase === 'setup' || !info.phase) && info.all_players) {
            renderLobbyPlayers(info.all_players);
        }

        // 4. フェーズ変更検知
        if (currentPhase !== info.phase) {
            currentPhase = info.phase;
            updatePhaseUI(info);
        }

    } catch (err) {
        console.error("更新エラー:", err);
    }
}

function getPhaseName(phase) {
    const phaseNames = {
        'setup': 'ロビー待機中',
        'lobby': 'ロビー待機中',
        'night': '夜（行動選択）',
        'day': '昼（話し合い）',
        'vote': '投票中',
        'result': '勝敗発表'
    };
    return phaseNames[phase] || phase || 'ロビー待機中';
}

// 各フェーズ画面の表示切り替え
function updatePhaseUI(info) {
    const phase = info.phase || 'setup';

    // 一旦すべてのフェーズ要素を隠す
    document.querySelectorAll('.phase-section').forEach(el => el.classList.add('hidden'));

    // setup もしくは lobby の場合はロビー画面を表示
    if (phase === 'lobby' || phase === 'setup') {
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
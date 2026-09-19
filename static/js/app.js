let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;
let currentPhase = null;

// 部屋作成
async function handleCreateRoom() {
    const nameInput = document.getElementById('player-name').value.trim();
    if (!nameInput) return alert("名前を入力してください");

    try {
        const createRes = await API.createRoom();
        currentRoomCode = createRes.room_code;

        const joinRes = await API.joinRoom(currentRoomCode, nameInput);
        currentPlayerId = joinRes.player_id;

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

// 定期取得（ポーリング）
function startPolling() {
    fetchGameStatus();
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(fetchGameStatus, 2000);
}

// ゲーム状態の更新とフェーズ制御
async function fetchGameStatus() {
    if (!currentRoomCode || !currentPlayerId) return;

    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        
        // 役職とフェーズの更新
        document.getElementById('displayed-role').textContent = info.displayed_role || "未定";
        document.getElementById('phase-display').textContent = getPhaseName(info.phase);

        // ホスト判定とボタン制御
        const hostControls = document.getElementById('host-controls');
        const waitingMessage = document.getElementById('waiting-message');

        if (info.is_host) {
            hostControls.classList.remove('hidden');
            waitingMessage.classList.add('hidden');
        } else {
            hostControls.classList.add('hidden');
            waitingMessage.classList.remove('hidden');
        }

        // フェーズが変わったら画面切り替え
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
        'lobby': '待機中',
        'night': '夜（行動）',
        'day': '昼（議論）',
        'vote': '投票中',
        'result': '結果発表'
    };
    return phaseNames[phase] || phase;
}

// フェーズごとのUI表示切り替え
function updatePhaseUI(info) {
    // 全フェーズ非表示
    document.querySelectorAll('.phase-section').forEach(el => el.classList.add('hidden'));

    const phase = info.phase || 'lobby';

    if (phase === 'lobby') {
        document.getElementById('lobby-phase').classList.remove('hidden');
    } else if (phase === 'night') {
        document.getElementById('night-phase').classList.remove('hidden');
        populatePlayerDropdown('night-target-select', info.other_players);
    } else if (phase === 'day') {
        document.getElementById('day-phase').classList.remove('hidden');
        renderLivingPlayers(info.other_players);
    } else if (phase === 'vote') {
        document.getElementById('vote-phase').classList.remove('hidden');
        populatePlayerDropdown('vote-target-select', info.other_players);
    } else if (phase === 'result') {
        document.getElementById('result-phase').classList.remove('hidden');
        if (info.result) {
            document.getElementById('result-content').innerHTML = info.result;
        }
    }
}

// ドロップダウンリストの作成
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

// プレイヤー一覧表示
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

// スタートボタン
async function handleStartGame() {
    try {
        const res = await fetch(`/api/room/${currentRoomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId })
        });
        const data = await res.json();
        if (!res.ok) return alert(data.detail || "スタート失敗");
        fetchGameStatus();
    } catch (err) {
        alert("通信エラー: " + err.message);
    }
}

// 夜アクション送信
async function handleSendAction() {
    const targetId = document.getElementById('night-target-select').value;
    if (!targetId) return alert("対象を選択してください");

    try {
        const res = await API.sendAction(currentRoomCode, currentPlayerId, targetId);
        document.getElementById('action-status-msg').textContent = res.message || "アクションを送信しました";
        document.getElementById('action-btn').disabled = true;
    } catch (err) {
        alert("送信失敗: " + err.message);
    }
}

// 投票送信
async function handleSendVote() {
    const targetId = document.getElementById('vote-target-select').value;
    if (!targetId) return alert("対象を選択してください");

    try {
        const res = await API.sendVote(currentRoomCode, currentPlayerId, targetId);
        document.getElementById('vote-status-msg').textContent = res.message || "投票を受け付けました";
        document.getElementById('vote-btn').disabled = true;
    } catch (err) {
        alert("投票失敗: " + err.message);
    }
}
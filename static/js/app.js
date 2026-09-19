let currentRoomCode = null;
let currentPlayerId = null;
let socket = null;
let pollTimer = null;

async function handleCreateRoom() {
    const name = document.getElementById('usernameInput').value.trim();
    if (!name) return alert("名前を入力してください");

    try {
        const roomRes = await API.createRoom();
        const joinRes = await API.joinRoom(roomRes.room_code, name);
        
        currentRoomCode = joinRes.room_code;
        currentPlayerId = joinRes.player_id;

        setupWebSocket();
        startPolling();
        showGameView();
        await updatePlayerUI();
    } catch (err) {
        alert(err.message);
    }
}

async function handleJoinRoom() {
    const name = document.getElementById('usernameInput').value.trim();
    const code = document.getElementById('roomCodeInput').value.trim().toUpperCase();
    if (!name || !code) return alert("名前と部屋コードを入力してください");

    try {
        const joinRes = await API.joinRoom(code, name);
        
        currentRoomCode = joinRes.room_code;
        currentPlayerId = joinRes.player_id;

        setupWebSocket();
        startPolling();
        showGameView();
        await updatePlayerUI();
    } catch (err) {
        alert(err.message);
    }
}

function setupWebSocket() {
    try {
        const isHttps = window.location.protocol === 'https:';
        const wsProtocol = isHttps ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/${currentRoomCode}/${currentPlayerId}`;
        
        socket = new WebSocket(wsUrl);

        socket.onmessage = async (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'UPDATE') {
                await updatePlayerUI();
            }
        };

        socket.onerror = (err) => {
            console.warn("WebSocket接続エラー。ポーリングで通信を継続します。", err);
        };
    } catch (e) {
        console.warn("WebSocket初期化失敗:", e);
    }
}

function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        await updatePlayerUI();
    }, 2000);
}

function showGameView() {
    document.getElementById('lobbyPanel').style.display = 'none';
    document.getElementById('gamePanel').style.display = 'block';
    document.getElementById('displayRoomCode').innerText = currentRoomCode;
}

async function updatePlayerUI() {
    if (!currentRoomCode || !currentPlayerId) return;

    try {
        const data = await API.getPlayerInfo(currentRoomCode, currentPlayerId);

        document.getElementById('roleName').innerText = data.displayed_role;
        document.getElementById('phaseText').innerText = formatPhase(data.phase, data.day_count);

        const statusElem = document.getElementById('statusText');
        statusElem.innerHTML = data.alive ? '状態: <span class="status-alive">生存</span>' : '状態: <span class="status-dead">死亡</span>';

        const resultBox = document.getElementById('resultBox');
        if (data.message) {
            resultBox.style.display = 'block';
            resultBox.innerText = `結果: ${data.message}`;
        } else {
            resultBox.style.display = 'none';
        }

        if (data.winner_faction) {
            alert(`ゲーム終了！ 勝利陣営: ${data.winner_faction}`);
        }

        const targetSelect = document.getElementById('targetSelect');
        targetSelect.innerHTML = '';
        data.targets.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name;
            targetSelect.appendChild(opt);
        });

        const actionArea = document.getElementById('actionArea');
        const submittedText = document.getElementById('submittedText');
        const actionBtn = document.getElementById('actionBtn');

        if (!data.alive || data.phase === 'ENDED') {
            actionArea.style.display = 'none';
            submittedText.style.display = 'none';
            checkHostButton(data);
            return;
        }

        if (data.action_submitted) {
            actionArea.style.display = 'none';
            submittedText.style.display = 'block';
        } else {
            actionArea.style.display = 'block';
            submittedText.style.display = 'none';

            if (data.phase === 'NIGHT') {
                actionBtn.innerText = '夜の能力を使用する';
            } else if (data.phase === 'VOTE') {
                actionBtn.innerText = 'このプレイヤーに投票する';
            } else {
                actionArea.style.display = 'none';
            }
        }

        // ホスト用スタートボタンの表示判定を呼び出し
        checkHostButton(data);

    } catch (err) {
        console.error(err);
    }
}

function formatPhase(phase, dayCount) {
    switch (phase) {
        case 'SETUP': return '待機中（SETUP）';
        case 'NIGHT': return `${dayCount}日目 - 夜`;
        case 'DAY': return `${dayCount}日目 - 昼（議論）`;
        case 'VOTE': return `${dayCount}日目 - 投票`;
        case 'ENDED': return 'ゲーム終了';
        default: return phase;
    }
}

async function handleActionSubmit() {
    const targetId = document.getElementById('targetSelect').value;
    const data = await API.getPlayerInfo(currentRoomCode, currentPlayerId);

    try {
        if (data.phase === 'NIGHT') {
            await API.sendAction(currentRoomCode, currentPlayerId, targetId);
        } else if (data.phase === 'VOTE') {
            await API.sendVote(currentRoomCode, currentPlayerId, targetId);
        }
        await updatePlayerUI();
    } catch (err) {
        alert(err.message);
    }
}

async function handleStartGame() {
    try {
        const res = await fetch(`/api/room/${currentRoomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId })
        });
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "開始に失敗しました");
        }
    } catch (e) {
        alert("通信エラーが発生しました");
    }
}

function checkHostButton(data) {
    const hostControls = document.getElementById('hostControls');
    if (hostControls) {
        if (data.is_host && data.phase === 'SETUP') {
            hostControls.style.display = 'block';
        } else {
            hostControls.style.display = 'none';
        }
    }
}
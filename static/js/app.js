let currentRoomCode = null;
let currentPlayerId = null;
let pollTimer = null;
let dayTimerInterval = null;
let remainingSeconds = 60;

async function handleCreateRoom() {
    const name = document.getElementById('usernameInput').value.trim();
    if (!name) return alert("名前を入力してください");
    try {
        const roomRes = await API.createRoom();
        const joinRes = await API.joinRoom(roomRes.room_code, name);
        currentRoomCode = joinRes.room_code;
        currentPlayerId = joinRes.player_id;
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
        startPolling();
        showGameView();
        await updatePlayerUI();
    } catch (err) {
        alert(err.message);
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
        
        // 昼タイマーの管理
        handleTimerDisplay(data.phase, data.day_timer);

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

        // ホスト設定パネルの表示制御
        const hostControls = document.getElementById('hostControls');
        if (hostControls) {
            if (data.is_host && data.phase === 'SETUP') {
                hostControls.style.display = 'block';
            } else {
                hostControls.style.display = 'none';
            }
        }

        const targetSelect = document.getElementById('targetSelect');
        targetSelect.innerHTML = '';
        data.targets.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name; // 「能力を使わない（パス）」含む
            targetSelect.appendChild(opt);
        });

        const actionArea = document.getElementById('actionArea');
        const submittedText = document.getElementById('submittedText');
        const actionBtn = document.getElementById('actionBtn');

        if (!data.alive || data.phase === 'ENDED') {
            actionArea.style.display = 'none';
            submittedText.style.display = 'none';
            return;
        }

        if (data.action_submitted) {
            actionArea.style.display = 'none';
            submittedText.style.display = 'block';
        } else {
            actionArea.style.display = 'block';
            submittedText.style.display = 'none';
            if (data.phase === 'NIGHT') {
                actionBtn.innerText = '夜の能力を実行する（パス選択可）';
            } else if (data.phase === 'DAY' || data.phase === 'VOTE') {
                actionBtn.innerText = 'このプレイヤーに投票する（過半数ルール）';
            } else {
                actionArea.style.display = 'none';
            }
        }
    } catch (err) {
        console.error(err);
    }
}

function formatPhase(phase, dayCount) {
    switch (phase) {
        case 'SETUP': return 'セットアップ中（ホスト設定待ち）';
        case 'NIGHT': return `${dayCount}日目 - 夜（能力行使・パス可能）`;
        case 'DAY': return `${dayCount}日目 - 昼（議論・タイマー進行）`;
        case 'VOTE': return `${dayCount}日目 - 投票（過半数以上で追放）`;
        case 'ENDED': return 'ゲーム終了';
        default: return phase;
    }
}

function handleTimerDisplay(phase, timerDuration) {
    const timerElem = document.getElementById('timerDisplay') || createTimerDisplayElement();
    if (phase === 'DAY') {
        timerElem.style.display = 'block';
        if (!dayTimerInterval) {
            remainingSeconds = timerDuration || 60;
            dayTimerInterval = setInterval(() => {
                remainingSeconds--;
                timerElem.innerText = `昼の残り時間: ${remainingSeconds}秒`;
                if (remainingSeconds <= 0) {
                    clearInterval(dayTimerInterval);
                    dayTimerInterval = null;
                }
            }, 1000);
        }
    } else {
        timerElem.style.display = 'none';
        if (dayTimerInterval) {
            clearInterval(dayTimerInterval);
            dayTimerInterval = null;
        }
    }
}

function createTimerDisplayElement() {
    const div = document.createElement('div');
    div.id = 'timerDisplay';
    div.style.cssText = 'font-size: 1.2em; color: #dc3545; font-weight: bold; margin: 10px 0;';
    const phaseText = document.getElementById('phaseText');
    phaseText.parentNode.insertBefore(div, phaseText.nextSibling);
    return div;
}

async function handleActionSubmit() {
    const targetId = document.getElementById('targetSelect').value;
    const data = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
    try {
        if (data.phase === 'NIGHT') {
            await API.sendAction(currentRoomCode, currentPlayerId, targetId);
        } else if (data.phase === 'DAY' || data.phase === 'VOTE') {
            await API.sendVote(currentRoomCode, currentPlayerId, targetId);
        }
        await updatePlayerUI();
    } catch (err) {
        alert(err.message);
    }
}

async function handleStartGame() {
    const timerInput = document.getElementById('dayTimerInput');
    const dayTimer = timerInput ? parseInt(timerInput.value) || 60 : 60;

    // 役職配分の収集
    const roleDistribution = {};
    document.querySelectorAll('.role-input').forEach(input => {
        const role = input.getAttribute('data-role');
        roleDistribution[role] = parseInt(input.value) || 0;
    });

    try {
        // 設定保存
        await fetch(`/api/room/${currentRoomCode}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId, day_timer: dayTimer, role_distribution: roleDistribution })
        });

        // ゲーム開始
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
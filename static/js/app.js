let currentState = {
    roomCode: localStorage.getItem('roomCode') || null,
    playerId: localStorage.getItem('playerId') || null,
    isHost: false,
    phase: 'lobby',
    displayedRole: '',
    camp: '',
    isAlive: true
};

let pollInterval = null;

const createRoomBtn = document.getElementById('create-room-btn');
const joinRoomBtn = document.getElementById('join-room-btn');
const startBtn = document.getElementById('start-game-btn');
const leaveBtn = document.getElementById('leave-room-btn');
const actionBtn = document.getElementById('send-action-btn');
const killBtn = document.getElementById('send-kill-btn');
const voteBtn = document.getElementById('send-vote-btn');
const returnLobbyBtn = document.getElementById('return-lobby-btn');
const resultLeaveBtn = document.getElementById('result-leave-btn');

document.addEventListener('DOMContentLoaded', () => {
    if (createRoomBtn) createRoomBtn.addEventListener('click', handleCreateRoom);
    if (joinRoomBtn) joinRoomBtn.addEventListener('click', handleJoinRoom);
    if (startBtn) startBtn.addEventListener('click', handleStartGame);
    if (leaveBtn) leaveBtn.addEventListener('click', handleLeaveRoom);
    if (actionBtn) actionBtn.addEventListener('click', handleSendAction);
    if (killBtn) killBtn.addEventListener('click', handleSendKill);
    if (voteBtn) voteBtn.addEventListener('click', handleSendVote);
    if (returnLobbyBtn) returnLobbyBtn.addEventListener('click', handleReturnLobby);
    if (resultLeaveBtn) resultLeaveBtn.addEventListener('click', handleLeaveRoom);

    if (currentState.roomCode && currentState.playerId) {
        startPolling();
    } else {
        showScreen('setup-screen');
    }
});

async function handleCreateRoom() {
    const playerName = document.getElementById('player-name-input').value.trim();
    if (!playerName) return alert("名前を入力してください");

    try {
        const createRes = await API.createRoom();
        currentState.roomCode = createRes.room_code;
        const joinRes = await API.joinRoom(currentState.roomCode, playerName);
        currentState.playerId = joinRes.player_id;
        currentState.isHost = joinRes.is_host;
        saveStateToStorage();
        startPolling();
    } catch (err) { alert(err.message); }
}

async function handleJoinRoom() {
    const roomCode = document.getElementById('room-code-input').value.trim().toUpperCase();
    const playerName = document.getElementById('player-name-input').value.trim();
    if (!roomCode || !playerName) return alert("部屋コードと名前を入力してください");

    try {
        const joinRes = await API.joinRoom(roomCode, playerName);
        currentState.roomCode = roomCode;
        currentState.playerId = joinRes.player_id;
        currentState.isHost = joinRes.is_host;
        saveStateToStorage();
        startPolling();
    } catch (err) { alert(err.message); }
}

async function handleLeaveRoom() {
    if (currentState.roomCode && currentState.playerId) {
        try {
            await fetch(`/api/room/${currentState.roomCode}/leave`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ player_id: currentState.playerId })
            });
        } catch(e){}
    }
    clearStateStorage();
    if (pollInterval) clearInterval(pollInterval);
    showScreen('setup-screen');
}

async function handleReturnLobby() {
    try {
        await fetch(`/api/room/${currentState.roomCode}/return_lobby`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: currentState.playerId })
        });
    } catch (err) { alert(err.message); }
}

function saveStateToStorage() {
    localStorage.setItem('roomCode', currentState.roomCode);
    localStorage.setItem('playerId', currentState.playerId);
}

function clearStateStorage() {
    localStorage.removeItem('roomCode');
    localStorage.removeItem('playerId');
    currentState.roomCode = null;
    currentState.playerId = null;
}

async function handleStartGame() {
    const impCount = parseInt(document.getElementById('setting-impostors').value) || 1;
    const neuCount = parseInt(document.getElementById('setting-neutrals').value) || 0;

    try {
        await fetch(`/api/room/${currentState.roomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                host_player_id: currentState.playerId,
                impostor_count: impCount,
                neutral_count: neuCount
            })
        });
    } catch (err) { alert(err.message); }
}

async function handleSendAction() {
    const targetSelect = document.getElementById('action-target-select');
    const extraInput = document.getElementById('action-extra-input');
    try {
        await API.sendAction(currentState.roomCode, currentState.playerId, targetSelect ? targetSelect.value : null, extraInput ? extraInput.value : null);
        alert("行動完了");
    } catch (err) { alert(err.message); }
}

async function handleSendKill() {
    const killSelect = document.getElementById('kill-target-select');
    try {
        await fetch(`/api/room/${currentState.roomCode}/kill`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: currentState.playerId, target_id: killSelect.value })
        });
        alert("襲撃ターゲット選択完了");
    } catch (err) { alert(err.message); }
}

async function handleSendVote() {
    const voteSelect = document.getElementById('vote-target-select');
    if (!voteSelect.value) return alert("投票先を選んでください");
    try {
        await API.sendVote(currentState.roomCode, currentState.playerId, voteSelect.value);
        alert("投票完了");
    } catch (err) { alert(err.message); }
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
        currentState.camp = data.camp;
        currentState.isAlive = data.is_alive;
        currentState.isHost = data.is_host;
        renderUI(data);
    } catch (err) {
        if (err.message && err.message.includes("404")) handleLeaveRoom();
    }
}

function renderUI(data) {
    ['setup-screen', 'lobby-screen', 'night-screen', 'day-screen', 'result-screen'].forEach(s => {
        document.getElementById(s).style.display = 'none';
    });

    if (data.phase === 'lobby') {
        showScreen('lobby-screen');
        document.getElementById('display-room-code').innerText = currentState.roomCode;
        document.getElementById('player-list').innerHTML = data.all_players.map(p => `<li>${p.name} ${p.is_host ? '(ホスト)' : ''}</li>`).join('');
        
        const hostSettings = document.getElementById('host-settings');
        if (startBtn) startBtn.style.display = data.is_host ? 'inline-block' : 'none';
        if (hostSettings) hostSettings.style.display = data.is_host ? 'block' : 'none';

    } else if (data.phase === 'night') {
        showScreen('night-screen');
        document.getElementById('my-role-display').innerText = data.displayed_role;
        document.getElementById('action-target-select').innerHTML = data.other_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
        
        const killSection = document.getElementById('kill-section');
        if (data.camp === 'impostor') {
            killSection.style.display = 'block';
            document.getElementById('kill-target-select').innerHTML = data.other_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
        } else {
            killSection.style.display = 'none';
        }
    } else if (data.phase === 'day' || data.phase === 'vote') {
        showScreen('day-screen');
        document.getElementById('night-report-box').innerHTML = data.night_report || "昨夜は報告がありません。";
        document.getElementById('vote-target-select').innerHTML = data.other_players.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    } else if (data.phase === 'result') {
        showScreen('result-screen');
        document.getElementById('game-result-text').innerText = data.result;
        
        const tbody = document.getElementById('roles-summary-body');
        tbody.innerHTML = (data.roles_summary || []).map(r => `
            <tr>
                <td>${r.name}</td>
                <td>${r.displayed_role}</td>
                <td>${r.real_role}</td>
                <td>${r.camp_name}</td>
            </tr>
        `).join('');
    }
}

function showScreen(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
}
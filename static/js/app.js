let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;
let currentDistMode = "individual"; // "individual" または "faction"

function switchMode(mode) {
    currentDistMode = mode;
    const btnInd = document.getElementById("tabIndividual");
    const btnFac = document.getElementById("tabFaction");
    const secInd = document.getElementById("individualSection");
    const secFac = document.getElementById("factionSection");

    if (mode === "individual") {
        btnInd.style.background = "#007bff";
        btnInd.style.color = "white";
        btnFac.style.background = "#e0e0e0";
        btnFac.style.color = "#333";
        secInd.style.display = "block";
        secFac.style.display = "none";
    } else {
        btnFac.style.background = "#007bff";
        btnFac.style.color = "white";
        btnInd.style.background = "#e0e0e0";
        btnInd.style.color = "#333";
        secFac.style.display = "block";
        secInd.style.display = "none";
    }
}

async function handleCreateRoom() {
    const name = document.getElementById("usernameInput").value.trim();
    if (!name) {
        alert("プレイヤー名を入力してください");
        return;
    }
    try {
        const data = await API.createRoom();
        currentRoomCode = data.room_code;
        const joinData = await API.joinRoom(currentRoomCode, name);
        currentPlayerId = joinData.player_id;
        
        localStorage.setItem("roomCode", currentRoomCode);
        localStorage.setItem("playerId", currentPlayerId);
        
        showGameScreen();
        startPolling();
    } catch (err) {
        alert(err.message);
    }
}

async function handleJoinRoom() {
    const name = document.getElementById("usernameInput").value.trim();
    const code = document.getElementById("roomCodeInput").value.trim().toUpperCase();
    if (!name || !code) {
        alert("プレイヤー名と部屋コードを入力してください");
        return;
    }
    try {
        const joinData = await API.joinRoom(code, name);
        currentRoomCode = joinData.room_code;
        currentPlayerId = joinData.player_id;
        
        localStorage.setItem("roomCode", currentRoomCode);
        localStorage.setItem("playerId", currentPlayerId);
        
        showGameScreen();
        startPolling();
    } catch (err) {
        alert("部屋への参加に失敗しました。コードが正しいか確認してください。");
    }
}

function showGameScreen() {
    document.getElementById("lobbyPanel").style.display = "none";
    document.getElementById("gamePanel").style.display = "block";
    document.getElementById("displayRoomCode").innerText = currentRoomCode;
}

function leaveRoom() {
    if (pollInterval) clearInterval(pollInterval);
    localStorage.removeItem("roomCode");
    localStorage.removeItem("playerId");
    currentRoomCode = null;
    currentPlayerId = null;
    document.getElementById("gamePanel").style.display = "none";
    document.getElementById("lobbyPanel").style.display = "block";
    document.getElementById("resultBox").style.display = "none";
}

async function handleStartGame() {
    const dayTimer = document.getElementById("dayTimerInput").value;
    let settingsPayload = {
        host_player_id: currentPlayerId,
        day_timer: dayTimer,
        distribution_mode: currentDistMode
    };

    if (currentDistMode === "individual") {
        const roleInputs = document.querySelectorAll(".role-input");
        let roleDistribution = {};
        roleInputs.forEach(input => {
            const role = input.dataset.role;
            const count = parseInt(input.value) || 0;
            roleDistribution[role] = count;
        });
        settingsPayload.role_distribution = roleDistribution;
    } else {
        settingsPayload.faction_distribution = {
            innocent: parseInt(document.getElementById("factionInnocent").value) || 0,
            imposter: parseInt(document.getElementById("factionImposter").value) || 0,
            neutral: parseInt(document.getElementById("factionNeutral").value) || 0
        };
    }

    try {
        await fetch(`/api/room/${currentRoomCode}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsPayload)
        });

        const res = await fetch(`/api/room/${currentRoomCode}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host_player_id: currentPlayerId })
        });
        
        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "ゲームの開始に失敗しました");
        }
    } catch (err) {
        alert(err.message);
    }
}

async function handleActionSubmit() {
    const targetId = document.getElementById("targetSelect").value;
    try {
        await API.sendAction(currentRoomCode, currentPlayerId, targetId);
        document.getElementById("actionArea").style.display = "none";
        document.getElementById("submittedText").style.display = "block";
    } catch (err) {
        alert(err.message);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(updateGameState, 2000);
    updateGameState();
}

async function updateGameState() {
    if (!currentRoomCode || !currentPlayerId) return;
    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        
        document.getElementById("phaseText").innerText = `現在のフェーズ: ${info.phase}`;
        document.getElementById("roleName").innerText = `あなたの役職: ${info.displayed_role}`;
        document.getElementById("statusText").innerText = info.alive ? "状態: 生存" : "状態: 死亡";

        if (info.message) {
            const resultBox = document.getElementById("resultBox");
            resultBox.innerText = info.message;
            resultBox.style.display = "block";
        }

        if (info.is_host && info.phase === "SETUP") {
            document.getElementById("hostControls").style.display = "block";
        } else {
            document.getElementById("hostControls").style.display = "none";
        }

        if (info.phase === "NIGHT" && info.alive && !info.action_submitted) {
            const select = document.getElementById("targetSelect");
            select.innerHTML = "";
            info.targets.forEach(t => {
                const opt = document.createElement("option");
                opt.value = t.id;
                opt.innerText = t.name;
                select.appendChild(opt);
            });
            document.getElementById("actionArea").style.display = "block";
            document.getElementById("submittedText").style.display = "none";
        } else {
            document.getElementById("actionArea").style.display = "none";
        }
    } catch (err) {
        console.error(err);
    }
}

window.onload = function() {
    const savedCode = localStorage.getItem("roomCode");
    const savedPlayer = localStorage.getItem("playerId");
    if (savedCode && savedPlayer) {
        currentRoomCode = savedCode;
        currentPlayerId = savedPlayer;
        showGameScreen();
        startPolling();
    }
};
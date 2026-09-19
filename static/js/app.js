let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;
let currentDistMode = "individual";

function switchMode(mode) {
    // 旧UIとの互換用。現在は陣営＋個別役職を同時に設定します。
    currentDistMode = "combined";
    updateFactionTotal();
}

function updateFactionTotal() {
    const ids = ["factionInnocent", "factionImposter", "factionNeutral"];
    const total = ids.reduce((sum, id) => sum + (parseInt(document.getElementById(id)?.value) || 0), 0);
    const playerCount = window.currentPlayerCount || null;
    const box = document.getElementById("factionTotalText");
    if (!box) return;
    box.innerText = playerCount === null ? `設定合計: ${total}人` : `設定合計: ${total}人 / 参加人数: ${playerCount}人`;
    box.style.color = playerCount !== null && total !== playerCount ? "#dc3545" : "#198754";
}

function toggleRoleGuide() {
    const panel = document.getElementById("roleGuidePanel");
    if (!panel) return;
    panel.style.display = panel.style.display === "none" || panel.style.display === "" ? "block" : "none";
}

async function handleCreateRoom() {
    const name = document.getElementById("usernameInput").value.trim();
    if (!name) return alert("プレイヤー名を入力してください");
    try {
        const data = await API.createRoom();
        currentRoomCode = data.room_code;
        const joinData = await API.joinRoom(currentRoomCode, name);
        currentPlayerId = joinData.player_id;
        localStorage.setItem("roomCode", currentRoomCode);
        localStorage.setItem("playerId", currentPlayerId);
        showGameScreen(); startPolling();
    } catch (err) { alert(err.message); }
}

async function handleJoinRoom() {
    const name = document.getElementById("usernameInput").value.trim();
    const code = document.getElementById("roomCodeInput").value.trim().toUpperCase();
    if (!name || !code) return alert("プレイヤー名と部屋コードを入力してください");
    try {
        const joinData = await API.joinRoom(code, name);
        currentRoomCode = joinData.room_code;
        currentPlayerId = joinData.player_id;
        localStorage.setItem("roomCode", currentRoomCode);
        localStorage.setItem("playerId", currentPlayerId);
        showGameScreen(); startPolling();
    } catch (err) { alert(err.message); }
}

function showGameScreen() {
    document.getElementById("lobbyPanel").style.display = "none";
    document.getElementById("gamePanel").style.display = "block";
    document.getElementById("displayRoomCode").innerText = currentRoomCode;
}

function leaveRoom() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    localStorage.removeItem("roomCode"); localStorage.removeItem("playerId");
    currentRoomCode = null; currentPlayerId = null;
    document.getElementById("gamePanel").style.display = "none";
    document.getElementById("lobbyPanel").style.display = "block";
    document.getElementById("resultBox").style.display = "none";
    const resultActions = document.getElementById("resultActions");
    if (resultActions) resultActions.style.display = "none";
    const guide = document.getElementById("roleGuidePanel");
    if (guide) guide.style.display = "none";
}

async function handleStartGame() {
    const roleDistribution = {};
    document.querySelectorAll(".role-input").forEach(input => {
        roleDistribution[input.dataset.role] = parseInt(input.value) || 0;
    });

    const settingsPayload = {
        host_player_id: currentPlayerId,
        day_timer: document.getElementById("dayTimerInput").value,
        distribution_mode: "combined",
        role_distribution: roleDistribution,
        faction_distribution: {
            innocent: parseInt(document.getElementById("factionInnocent").value) || 0,
            imposter: parseInt(document.getElementById("factionImposter").value) || 0,
            neutral: parseInt(document.getElementById("factionNeutral").value) || 0
        }
    };

    try {
        await API.updateSettings(currentRoomCode, settingsPayload);
        await API.startGame(currentRoomCode, currentPlayerId);
    } catch (err) { alert(err.message); }
}


const MAGICIAN_GUESS_ROLES = [
    ["fool", "バカ"], ["doctor", "ドクター"], ["mouse", "ねずみ"],
    ["police", "ポリス"], ["trapper", "トラッパー"], ["lookout", "ルックアウト"],
    ["investigator", "インベスティゲーター"], ["provoker", "挑発者"], ["tracker", "トラッカー"],
    ["blaimer", "ブレイマー"], ["cleaner", "クリーナー"], ["serial_killer", "シリアルキラー"],
    ["bomber", "ボマー"], ["survivor", "サバイバー"], ["thief", "シーフ"],
    ["ghost", "ゴースト"], ["magician", "魔術師"]
];

function buildRoleActionUI(info) {
    const actionRoleText = document.getElementById("actionRoleText");
    const targetSelect = document.getElementById("targetSelect");
    const extraArea = document.getElementById("extraActionArea");
    const actionHelp = document.getElementById("actionHelp");
    actionRoleText.innerText = `${info.displayed_role} の夜アクション`;
    targetSelect.innerHTML = "";
    info.targets.forEach(t => {
        const opt = document.createElement("option"); opt.value = t.id; opt.innerText = t.name;
        targetSelect.appendChild(opt);
    });
    extraArea.innerHTML = ""; actionHelp.innerText = "";
    const role = info.displayed_role;

    if (role === "魔術師") {
        actionHelp.innerText = "ターゲットの役職を予想してください。正解ならターゲットを殺害、外れると自分が死亡します。";
        const label = document.createElement("label"); label.innerText = "予想役職: ";
        const select = document.createElement("select"); select.id = "roleGuessSelect"; select.style.padding = "6px";
        MAGICIAN_GUESS_ROLES.forEach(([id, name]) => {
            const opt = document.createElement("option"); opt.value = id; opt.innerText = name; select.appendChild(opt);
        });
        label.appendChild(select); extraArea.appendChild(label);
    }
    if (role === "ボマー") {
        actionHelp.innerText = "爆弾を仕掛けるか、すでに仕掛けた爆弾を起爆します。";
        const select = document.createElement("select"); select.id = "bombModeSelect"; select.style.padding = "6px";
        const plant = document.createElement("option"); plant.value = "plant"; plant.innerText = "爆弾を仕掛ける";
        const detonate = document.createElement("option"); detonate.value = "detonate"; detonate.innerText = "爆弾を起爆する";
        select.appendChild(plant); select.appendChild(detonate); extraArea.appendChild(select);
    }
    const helps = {
        "シーフ": "選択したプレイヤーを殺害し、その役職を盗みます。",
        "ねずみ": "1回だけ使用できます。調査結果は次の昼に全員へ公表されます。",
        "挑発者": "対象の次の昼の票数を+2します。残り2回まで使用できます。",
        "ドクター": "対象が夜に死亡した場合、蘇生できます。同じ対象を2夜連続では選べません。",
        "ポリス": "対象の夜能力を封じます。同じ対象を2夜連続では選べません。",
        "トラッパー": "対象の家に罠を仕掛け、そこを訪れた人のうち1人をランダムに封じます。",
        "ルックアウト": "対象の家を訪れたプレイヤーを確認します。",
        "インベスティゲーター": "対象の役職候補を2つに絞り込みます。",
        "トラッカー": "対象が夜に訪れた家を確認します。",
        "ゴースト": "対象の家にろうそくを置き、投票で追放された場合は次の夜に復讐します。",
        "バカ": "あなたには別のイノセント役職に見えていますが、実際には能力を持ちません。",
        "ブレイマー": "対象の死亡・追放時の役職表示をインポスターに見せます。残り2回まで使用できます。",
        "クリーナー": "対象が死亡・追放された際、その役職を不明にします。",
        "シリアルキラー": "対象を殺害します。ポリスやトラッパーでは止まりません。",
        "サバイバー": "夜の行動はありません。殺害されても最大3回まで復活します。",
        "インベスティゲーター": "対象の役職候補を2つに絞り込みます。"
    };
    if (helps[role]) actionHelp.innerText = helps[role];
}

async function handleActionSubmit() {
    const action = { target_id: document.getElementById("targetSelect").value };
    const guessSelect = document.getElementById("roleGuessSelect");
    if (guessSelect) action.guessed_role = guessSelect.value;
    const bombMode = document.getElementById("bombModeSelect");
    if (bombMode) action.bomb_action = bombMode.value;
    try {
        await API.sendAction(currentRoomCode, currentPlayerId, action);
        document.getElementById("actionArea").style.display = "none";
        document.getElementById("submittedText").style.display = "block";
    } catch (err) { alert(err.message); }
}

function renderPrivateReports(info) {
    const box = document.getElementById("privateReportBox"); if (!box) return;
    if (!info.private_reports || info.private_reports.length === 0) {
        box.style.display = "none"; box.innerText = ""; return;
    }
    box.innerHTML = "";
    info.private_reports.forEach(report => {
        const div = document.createElement("div"); div.innerText = report; div.style.marginBottom = "6px"; box.appendChild(div);
    });
    box.style.display = "block";
}

function renderVoteArea(info) {
    const voteArea = document.getElementById("voteArea"); const voteSelect = document.getElementById("voteSelect");
    if (!voteArea || !voteSelect) return;
    if (info.phase !== "DAY" || !info.alive || info.vote_submitted) { voteArea.style.display = "none"; return; }
    voteSelect.innerHTML = "";
    const pass = document.createElement("option"); pass.value = "pass"; pass.innerText = "棄権"; voteSelect.appendChild(pass);
    info.targets.forEach(t => { if (t.id === "pass") return; const opt = document.createElement("option"); opt.value = t.id; opt.innerText = t.name; voteSelect.appendChild(opt); });
    voteArea.style.display = "block";
}

async function handleVoteSubmit() {
    try {
        await API.sendVote(currentRoomCode, currentPlayerId, document.getElementById("voteSelect").value);
        document.getElementById("voteArea").style.display = "none";
        document.getElementById("votedText").style.display = "block";
    } catch (err) { alert(err.message); }
}

function resetDayUI() {
    const votedText = document.getElementById("votedText"); if (votedText) votedText.style.display = "none";
}

function renderResultActions(info) {
    const panel = document.getElementById("resultActions"); if (!panel) return;
    if (info.phase !== "RESULT") { panel.style.display = "none"; return; }
    panel.style.display = "block";
    let winner = info.winner_faction || "結果";
    const names = { innocent: "イノセント", imposter: "インポスター", neutral: "ニュートラル", survivor: "サバイバー", draw: "引き分け" };
    if (names[winner]) winner = names[winner];
    const winnerText = document.getElementById("resultWinnerText"); if (winnerText) winnerText.innerText = `勝利: ${winner}`;
    const button = document.getElementById("rematchButton"); if (button) button.style.display = info.is_host ? "block" : "none";
    const waiting = document.getElementById("rematchWaitingText"); if (waiting) waiting.style.display = info.is_host ? "none" : "block";
}

async function handleRematch() {
    if (!currentRoomCode || !currentPlayerId) return;
    const button = document.getElementById("rematchButton");
    if (button) { button.disabled = true; button.innerText = "再戦準備中..."; }
    try {
        await API.rematchRoom(currentRoomCode, currentPlayerId);
        await updateGameState();
        if (button) { button.disabled = false; button.innerText = "同じルームでもう一度遊ぶ"; }
    } catch (err) {
        if (button) { button.disabled = false; button.innerText = "同じルームでもう一度遊ぶ"; }
        alert(err.message);
    }
}

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(updateGameState, 2000); updateGameState();
}

async function updateGameState() {
    if (!currentRoomCode || !currentPlayerId) return;
    try {
        const info = await API.getPlayerInfo(currentRoomCode, currentPlayerId);
        document.getElementById("phaseText").innerText = `現在のフェーズ: ${info.phase} / ${info.day_count}日目`;
        const roleName = document.getElementById("roleName"); roleName.innerText = `あなたの役職: ${info.displayed_role}`; roleName.dataset.role = info.displayed_role;
        document.getElementById("statusText").innerText = info.alive ? "状態: 生存" : "状態: 死亡";
        const resultBox = document.getElementById("resultBox");
        if (info.message) { resultBox.innerText = info.message; resultBox.style.display = "block"; }
        renderPrivateReports(info);
        document.getElementById("hostControls").style.display = info.is_host && info.phase === "SETUP" ? "block" : "none";
        resetDayUI();
        if (info.phase === "NIGHT" && info.alive && !info.action_submitted) {
            buildRoleActionUI(info); document.getElementById("actionArea").style.display = "block"; document.getElementById("submittedText").style.display = "none";
        } else document.getElementById("actionArea").style.display = "none";
        if (info.phase === "DAY") renderVoteArea(info); else { const v = document.getElementById("voteArea"); if (v) v.style.display = "none"; }
        if (info.phase === "RESULT") { const v = document.getElementById("voteArea"); if (v) v.style.display = "none"; document.getElementById("actionArea").style.display = "none"; }
        renderResultActions(info);
    } catch (err) { console.error(err); }
}

window.onload = function() {
    const savedCode = localStorage.getItem("roomCode"); const savedPlayer = localStorage.getItem("playerId");
    if (savedCode && savedPlayer) { currentRoomCode = savedCode; currentPlayerId = savedPlayer; showGameScreen(); startPolling(); }
};


window.addEventListener("DOMContentLoaded", () => {
    ["factionInnocent", "factionImposter", "factionNeutral"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("input", updateFactionTotal);
    });
    updateFactionTotal();
});

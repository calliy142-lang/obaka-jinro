let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;
let currentDistMode = "individual";


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


function toggleRoleGuide() {
    const guidePanel = document.getElementById("roleGuidePanel");

    if (guidePanel.style.display === "none" ||
        guidePanel.style.display === "") {
        guidePanel.style.display = "block";
    } else {
        guidePanel.style.display = "none";
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

        const joinData = await API.joinRoom(
            currentRoomCode,
            name
        );

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
    const code = document
        .getElementById("roomCodeInput")
        .value
        .trim()
        .toUpperCase();

    if (!name || !code) {
        alert("プレイヤー名と部屋コードを入力してください");
        return;
    }

    try {
        const joinData = await API.joinRoom(
            code,
            name
        );

        currentRoomCode = joinData.room_code;
        currentPlayerId = joinData.player_id;

        localStorage.setItem("roomCode", currentRoomCode);
        localStorage.setItem("playerId", currentPlayerId);

        showGameScreen();
        startPolling();

    } catch (err) {
        alert(err.message);
    }
}


function showGameScreen() {
    document.getElementById("lobbyPanel").style.display = "none";
    document.getElementById("gamePanel").style.display = "block";

    document.getElementById("displayRoomCode").innerText =
        currentRoomCode;
}


function leaveRoom() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    localStorage.removeItem("roomCode");
    localStorage.removeItem("playerId");

    currentRoomCode = null;
    currentPlayerId = null;

    document.getElementById("gamePanel").style.display = "none";
    document.getElementById("lobbyPanel").style.display = "block";

    document.getElementById("resultBox").style.display = "none";

    const resultActions =
        document.getElementById("resultActions");

    if (resultActions) {
        resultActions.style.display = "none";
    }

    document.getElementById("roleGuidePanel").style.display = "none";
}


async function handleStartGame() {
    const dayTimer =
        document.getElementById("dayTimerInput").value;

    const settingsPayload = {
        host_player_id: currentPlayerId,
        day_timer: dayTimer,
        distribution_mode: currentDistMode
    };

    if (currentDistMode === "individual") {
        const roleInputs =
            document.querySelectorAll(".role-input");

        const roleDistribution = {};

        roleInputs.forEach(input => {
            roleDistribution[input.dataset.role] =
                parseInt(input.value) || 0;
        });

        settingsPayload.role_distribution =
            roleDistribution;

    } else {
        settingsPayload.faction_distribution = {
            innocent:
                parseInt(
                    document.getElementById("factionInnocent").value
                ) || 0,

            imposter:
                parseInt(
                    document.getElementById("factionImposter").value
                ) || 0,

            neutral:
                parseInt(
                    document.getElementById("factionNeutral").value
                ) || 0
        };
    }

    try {
        await API.updateSettings(
            currentRoomCode,
            settingsPayload
        );

        await API.startGame(
            currentRoomCode,
            currentPlayerId
        );

    } catch (err) {
        alert(err.message);
    }
}


function buildRoleActionUI(info) {
    const actionArea =
        document.getElementById("actionArea");

    const actionRoleText =
        document.getElementById("actionRoleText");

    const targetSelect =
        document.getElementById("targetSelect");

    const extraArea =
        document.getElementById("extraActionArea");

    const actionHelp =
        document.getElementById("actionHelp");

    actionRoleText.innerText =
        `${info.displayed_role} の夜アクション`;

    targetSelect.innerHTML = "";

    info.targets.forEach(t => {
        const opt = document.createElement("option");

        opt.value = t.id;
        opt.innerText = t.name;

        targetSelect.appendChild(opt);
    });

    extraArea.innerHTML = "";
    actionHelp.innerText = "";

    const role = info.displayed_role;


    if (role === "魔術師") {
        actionHelp.innerText =
            "ターゲットの役職を予想してください。正解ならターゲットを殺害、外れると自分が死亡します。";

        const label = document.createElement("label");
        label.innerText = "予想役職: ";

        const guessSelect =
            document.createElement("select");

        guessSelect.id = "roleGuessSelect";
        guessSelect.style.padding = "6px";

        const roles = [
            ["fool", "バカ"],
            ["doctor", "ドクター"],
            ["mouse", "ねずみ"],
            ["police", "ポリス"],
            ["trapper", "トラッパー"],
            ["lookout", "ルックアウト"],
            ["investigator", "インベスティゲーター"],
            ["provoker", "挑発者"],
            ["tracker", "トラッカー"],
            ["imposter", "インポスター"],
            ["blaimer", "ブレイマー"],
            ["cleaner", "クリーナー"],
            ["serial_killer", "シリアルキラー"],
            ["bomber", "ボマー"],
            ["survivor", "サバイバー"],
            ["thief", "シーフ"],
            ["ghost", "ゴースト"],
            ["magician", "魔術師"]
        ];

        roles.forEach(([id, name]) => {
            const opt = document.createElement("option");

            opt.value = id;
            opt.innerText = name;

            guessSelect.appendChild(opt);
        });

        label.appendChild(guessSelect);
        extraArea.appendChild(label);
    }


    if (role === "ボマー") {
        actionHelp.innerText =
            "爆弾を仕掛けるか、すでに仕掛けた爆弾を起爆します。";

        const bombMode =
            document.createElement("select");

        bombMode.id = "bombModeSelect";
        bombMode.style.padding = "6px";

        const plant =
            document.createElement("option");

        plant.value = "plant";
        plant.innerText = "爆弾を仕掛ける";

        const detonate =
            document.createElement("option");

        detonate.value = "detonate";
        detonate.innerText = "爆弾を起爆する";

        bombMode.appendChild(plant);
        bombMode.appendChild(detonate);

        extraArea.appendChild(bombMode);
    }


    if (role === "シーフ") {
        actionHelp.innerText =
            "選択したプレイヤーを殺害し、その役職を盗みます。";
    }


    if (role === "ねずみ") {
        actionHelp.innerText =
            "1回だけ使用できます。調査結果は次の昼に全員へ公表されます。";
    }


    if (role === "挑発者") {
        actionHelp.innerText =
            "対象の次の昼の票数を+2します。残り2回まで使用できます。";
    }


    if (role === "ドクター") {
        actionHelp.innerText =
            "対象が夜に死亡した場合、蘇生できます。同じ対象を2夜連続では選べません。";
    }


    if (role === "ポリス") {
        actionHelp.innerText =
            "対象の夜能力を封じます。同じ対象を2夜連続では選べません。";
    }


    if (role === "トラッパー") {
        actionHelp.innerText =
            "対象の家に罠を仕掛け、そこを訪れた人のうち1人をランダムに封じます。";
    }


    if (role === "ルックアウト") {
        actionHelp.innerText =
            "対象の家を訪れたプレイヤーを確認します。";
    }


    if (role === "インベスティゲーター") {
        actionHelp.innerText =
            "対象の役職候補を2つに絞り込みます。";
    }


    if (role === "トラッカー") {
        actionHelp.innerText =
            "対象が夜に訪れた家を確認します。";
    }


    if (role === "ゴースト") {
        actionHelp.innerText =
            "対象の家にろうそくを置き、投票で追放された場合は次の夜に復讐します。";
    }


    if (role === "バカ") {
        actionHelp.innerText =
            "あなたには別のイノセント役職に見えていますが、実際には能力を持ちません。";
    }


    if (role === "インポスター") {
        actionHelp.innerText =
            "夜に対象プレイヤーを襲撃します。";
    }


    if (role === "ブレイマー") {
        actionHelp.innerText =
            "対象の死亡・追放時の役職表示をインポスターに見せます。残り2回まで使用できます。";
    }


    if (role === "クリーナー") {
        actionHelp.innerText =
            "対象が死亡・追放された際、その役職を不明にします。";
    }


    if (role === "シリアルキラー") {
        actionHelp.innerText =
            "対象を殺害します。ポリスやトラッパーでは止まりません。";
    }


    if (role === "サバイバー") {
        actionHelp.innerText =
            "夜の行動はありません。殺害されても最大3回まで復活します。";
    }


    actionArea.style.display = "block";
}


async function handleActionSubmit() {
    const targetId =
        document.getElementById("targetSelect").value;

    const action = {
        target_id: targetId
    };

    const guessSelect =
        document.getElementById("roleGuessSelect");

    if (guessSelect) {
        action.guessed_role =
            guessSelect.value;
    }

    const bombMode =
        document.getElementById("bombModeSelect");

    if (bombMode) {
        action.bomb_action =
            bombMode.value;
    }

    try {
        await API.sendAction(
            currentRoomCode,
            currentPlayerId,
            action
        );

        document.getElementById("actionArea").style.display =
            "none";

        document.getElementById("submittedText").style.display =
            "block";

    } catch (err) {
        alert(err.message);
    }
}


function renderPrivateReports(info) {
    const box =
        document.getElementById("privateReportBox");

    if (!box) return;

    if (!info.private_reports ||
        info.private_reports.length === 0) {

        box.style.display = "none";
        box.innerText = "";

        return;
    }

    box.innerHTML = "";

    info.private_reports.forEach(report => {
        const div = document.createElement("div");

        div.innerText = report;
        div.style.marginBottom = "6px";

        box.appendChild(div);
    });

    box.style.display = "block";
}


function renderVoteArea(info) {
    const voteArea =
        document.getElementById("voteArea");

    const voteSelect =
        document.getElementById("voteSelect");

    if (!voteArea || !voteSelect) {
        return;
    }

    if (info.phase !== "DAY" ||
        !info.alive ||
        info.action_submitted) {

        voteArea.style.display = "none";

        return;
    }

    voteSelect.innerHTML = "";

    const pass =
        document.createElement("option");

    pass.value = "pass";
    pass.innerText = "棄権";

    voteSelect.appendChild(pass);

    info.targets.forEach(t => {
        if (t.id === "pass") return;

        const opt =
            document.createElement("option");

        opt.value = t.id;
        opt.innerText = t.name;

        voteSelect.appendChild(opt);
    });

    voteArea.style.display = "block";
}


async function handleVoteSubmit() {
    const targetId =
        document.getElementById("voteSelect").value;

    try {
        await API.sendVote(
            currentRoomCode,
            currentPlayerId,
            targetId
        );

        document.getElementById("voteArea").style.display =
            "none";

        document.getElementById("votedText").style.display =
            "block";

    } catch (err) {
        alert(err.message);
    }
}


function resetDayUI() {
    const votedText =
        document.getElementById("votedText");

    if (votedText) {
        votedText.style.display = "none";
    }
}


function renderResultActions(info) {
    const resultActions =
        document.getElementById("resultActions");

    const rematchButton =
        document.getElementById("rematchButton");

    const rematchWaitingText =
        document.getElementById("rematchWaitingText");

    if (!resultActions) {
        return;
    }

    if (info.phase !== "RESULT") {
        resultActions.style.display = "none";
        return;
    }

    resultActions.style.display = "block";

    const isHost =
        info.is_host === true;

    if (rematchButton) {
        rematchButton.style.display =
            isHost ? "inline-block" : "none";
    }

    if (rematchWaitingText) {
        rematchWaitingText.style.display =
            isHost ? "none" : "block";

        rematchWaitingText.innerText =
            "ホストが再戦を開始するまでお待ちください。";
    }
}


async function handleRematch() {
    if (!currentRoomCode || !currentPlayerId) {
        return;
    }

    try {
        await API.rematchRoom(
            currentRoomCode,
            currentPlayerId
        );

        document.getElementById("resultActions").style.display =
            "none";

        document.getElementById("resultBox").style.display =
            "none";

    } catch (err) {
        alert(err.message);
    }
}


function renderHostControls(info) {
    const hostControls =
        document.getElementById("hostControls");

    if (!hostControls) {
        return;
    }

    if (info.phase === "SETUP" && info.is_host) {
        hostControls.style.display = "block";
    } else {
        hostControls.style.display = "none";
    }
}


function renderRole(info) {
    const roleName =
        document.getElementById("roleName");

    if (!roleName) return;

    roleName.innerText =
        info.displayed_role || "役職未決定";

    roleName.dataset.role =
        info.displayed_role || "";
}


function renderPhase(info) {
    const phaseText =
        document.getElementById("phaseText");

    if (!phaseText) return;

    const phaseNames = {
        SETUP: "待機中",
        NIGHT: "夜",
        DAY: "昼",
        RESULT: "結果"
    };

    phaseText.innerText =
        phaseNames[info.phase] || info.phase;
}


function renderStatus(info) {
    const statusText =
        document.getElementById("statusText");

    if (!statusText) return;

    if (info.alive) {
        statusText.innerText = "生存";
        statusText.style.color = "green";
    } else {
        statusText.innerText = "死亡";
        statusText.style.color = "red";
    }
}


function renderResult(info) {
    const resultBox =
        document.getElementById("resultBox");

    if (!resultBox) return;

    if (info.phase !== "RESULT") {
        resultBox.style.display = "none";
        return;
    }

    resultBox.style.display = "block";

    const winnerText =
        info.winner_faction ||
        info.message ||
        "ゲーム終了";

    resultBox.innerText =
        winnerText;
}


function renderPlayerList(info) {
    const playerList =
        document.getElementById("playerList");

    if (!playerList) {
        return;
    }

    playerList.innerHTML = "";

    if (!info.players) {
        return;
    }

    info.players.forEach(player => {
        const div =
            document.createElement("div");

        let text =
            player.name;

        if (!player.alive) {
            text += "（死亡）";
        }

        if (player.is_host) {
            text += " [HOST]";
        }

        div.innerText = text;

        playerList.appendChild(div);
    });
}


function renderNightAction(info) {
    const actionArea =
        document.getElementById("actionArea");

    const submittedText =
        document.getElementById("submittedText");

    if (!actionArea) {
        return;
    }

    if (info.phase !== "NIGHT" ||
        !info.alive ||
        info.action_submitted) {

        actionArea.style.display = "none";

        if (submittedText) {
            submittedText.style.display =
                info.action_submitted
                    ? "block"
                    : "none";
        }

        return;
    }

    if (!info.can_act) {
        actionArea.style.display = "none";

        if (submittedText) {
            submittedText.style.display = "none";
        }

        return;
    }

    if (submittedText) {
        submittedText.style.display = "none";
    }

    buildRoleActionUI(info);
}


function updateGameState(info) {
    renderRole(info);
    renderPhase(info);
    renderStatus(info);
    renderPlayerList(info);
    renderHostControls(info);
    renderPrivateReports(info);
    renderNightAction(info);
    renderVoteArea(info);
    renderResult(info);
    renderResultActions(info);

    if (info.phase === "DAY") {
        resetDayUI();
    }

    if (info.room_code) {
        document.getElementById("displayRoomCode").innerText =
            info.room_code;
    }

    if (info.day_count !== undefined) {
        const dayCount =
            document.getElementById("dayCount");

        if (dayCount) {
            dayCount.innerText =
                `Day ${info.day_count}`;
        }
    }
}


async function pollGameState() {
    if (!currentRoomCode ||
        !currentPlayerId) {
        return;
    }

    try {
        const info =
            await API.getPlayerInfo(
                currentRoomCode,
                currentPlayerId
            );

        updateGameState(info);

    } catch (err) {
        console.error(err);
    }
}


function startPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }

    pollGameState();

    pollInterval =
        setInterval(
            pollGameState,
            2000
        );
}


function restoreSession() {
    const savedRoomCode =
        localStorage.getItem("roomCode");

    const savedPlayerId =
        localStorage.getItem("playerId");

    if (!savedRoomCode ||
        !savedPlayerId) {
        return;
    }

    currentRoomCode = savedRoomCode;
    currentPlayerId = savedPlayerId;

    showGameScreen();
    startPolling();
}


document.addEventListener("DOMContentLoaded", () => {
    restoreSession();
});
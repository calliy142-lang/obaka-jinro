let currentRoomCode = null;
let currentPlayerId = null;
let pollInterval = null;
let currentDistMode = "individual";
let selectedNightTarget = "pass";
let selectedAttackTarget = "pass";
let nightUiBuilt = false;
let nightUiPhase = null;
let selectedVoteTarget = "pass";
let voteOptionIds = "";
let lastRenderedPhase = null;
let dayTimerInterval = null;

function switchMode(mode) {
    // 旧UIとの互換用。現在は陣営＋個別役職を同時に設定します。
    currentDistMode = "combined";
    updateFactionTotal();
}

function updateFactionTotal() {
    const vals = ["factionInnocent", "factionImposter", "factionNeutral"].map(id => document.getElementById(id)?.value ?? "0");
    const hasRandom = vals.includes("random");
    const total = vals.reduce((sum, v) => sum + (v === "random" ? 0 : (parseInt(v) || 0)), 0);
    const playerCount = window.currentPlayerCount || null;
    const box = document.getElementById("factionTotalText");
    if (!box) return;
    if (hasRandom) {
        box.innerText = playerCount === null ? "ランダム陣営あり：開始時に人数を抽選" : `ランダム陣営あり：開始時に抽選 / 参加人数: ${playerCount}人`;
        box.style.color = "#6c757d";
    } else {
        box.innerText = playerCount === null ? `設定合計: ${total}人` : `設定合計: ${total}人 / 参加人数: ${playerCount}人`;
        box.style.color = playerCount !== null && total !== playerCount ? "#dc3545" : "#198754";
    }
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

async function leaveRoom() {
    try { if (currentRoomCode && currentPlayerId) await API.leaveRoom(currentRoomCode, currentPlayerId); } catch (_) {}
    if (dayTimerInterval) { clearInterval(dayTimerInterval); dayTimerInterval = null; }
    lastRenderedPhase = null;
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
    localStorage.removeItem("roomCode"); localStorage.removeItem("playerId");
    currentRoomCode = null; currentPlayerId = null;
    document.getElementById("gamePanel").style.display = "none";
    document.getElementById("lobbyPanel").style.display = "block";
    document.getElementById("resultBox").style.display = "none";
    const resultActions = document.getElementById("resultActions"); if (resultActions) resultActions.style.display = "none";
}


async function handleStartGame() {
    const roleDistribution = {};
    const excludedRoles = [];
    document.querySelectorAll(".role-input").forEach(input => {
        const value = input.value;
        if (value === "none") {
            roleDistribution[input.dataset.role] = 0;
            excludedRoles.push(input.dataset.role);
        } else {
            roleDistribution[input.dataset.role] = parseInt(value) || 0;
        }
    });

    const settingsPayload = {
        host_player_id: currentPlayerId,
        day_timer: document.getElementById("dayTimerInput").value,
        distribution_mode: "combined",
        role_distribution: roleDistribution,
        excluded_roles: excludedRoles,
        faction_distribution: {
            innocent: parseInt(document.getElementById("factionInnocent").value) || 0,
            imposter: document.getElementById("factionImposter").value === "random" ? 0 : (parseInt(document.getElementById("factionImposter").value) || 0),
            neutral: document.getElementById("factionNeutral").value === "random" ? 0 : (parseInt(document.getElementById("factionNeutral").value) || 0)
        },
        faction_random: [
            ...(document.getElementById("factionImposter").value === "random" ? ["imposter"] : []),
            ...(document.getElementById("factionNeutral").value === "random" ? ["neutral"] : [])
        ]
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
    const attackArea = document.getElementById("imposterAttackArea");
    const attackSelect = document.getElementById("attackTargetSelect");
    const extraArea = document.getElementById("extraActionArea");
    const actionHelp = document.getElementById("actionHelp");
    if (!targetSelect || !extraArea || !actionHelp) return;

    actionRoleText.innerText = `${info.displayed_role} の夜アクション`;

    // 一度作ったselectを毎ポーリングで作り直さない。
    // これが「選んだ対象が何もしないへ戻る」原因にならないようにする本命対策。
    const targetIds = info.targets.map(t => t.id).join("|");
    if (targetSelect.dataset.optionIds !== targetIds) {
        const current = targetSelect.value || selectedNightTarget;
        targetSelect.innerHTML = "";
        info.targets.forEach(t => {
            const opt = document.createElement("option");
            opt.value = t.id;
            opt.innerText = t.name;
            targetSelect.appendChild(opt);
        });
        targetSelect.dataset.optionIds = targetIds;
        const keep = info.targets.some(t => t.id === selectedNightTarget)
            ? selectedNightTarget
            : (info.targets.some(t => t.id === current) ? current : "pass");
        selectedNightTarget = keep;
        targetSelect.value = keep;
    } else if (info.targets.some(t => t.id === selectedNightTarget)) {
        targetSelect.value = selectedNightTarget;
    }
    targetSelect.onchange = () => {
        selectedNightTarget = targetSelect.value;
        if (info.is_imposter && selectedNightTarget !== "pass" && attackSelect) { selectedAttackTarget = "pass"; attackSelect.value = "pass"; }
    };

    // インポスター陣営は役職能力とは別に必ず襲撃欄を持つ。
    if (attackArea && attackSelect) {
        if (info.is_imposter && info.phase === "NIGHT") {
            attackArea.style.display = "block";
            const attackIds = info.attack_targets.map(t => t.id).join("|");
            if (attackSelect.dataset.optionIds !== attackIds) {
                const current = attackSelect.value || selectedAttackTarget;
                attackSelect.innerHTML = "";
                const pass = document.createElement("option");
                pass.value = "pass";
                pass.innerText = "襲撃しない";
                attackSelect.appendChild(pass);
                info.attack_targets.forEach(t => {
                    const opt = document.createElement("option");
                    opt.value = t.id;
                    opt.innerText = t.name;
                    attackSelect.appendChild(opt);
                });
                attackSelect.dataset.optionIds = attackIds;
                const keep = info.attack_targets.some(t => t.id === selectedAttackTarget)
                    ? selectedAttackTarget
                    : (info.attack_targets.some(t => t.id === current) ? current : "pass");
                selectedAttackTarget = keep;
                attackSelect.value = keep;
            } else if (info.attack_targets.some(t => t.id === selectedAttackTarget)) {
                attackSelect.value = selectedAttackTarget;
            }
            attackSelect.onchange = () => {
                selectedAttackTarget = attackSelect.value;
                if (selectedAttackTarget !== "pass") { selectedNightTarget = "pass"; targetSelect.value = "pass"; }
            };
        } else {
            attackArea.style.display = "none";
        }
    }

    const role = info.displayed_role;
    const roleKey = `${info.phase}|${role}|${info.is_imposter}|${info.ability_uses_remaining?.[role] ?? ""}`;
    if (extraArea.dataset.roleKey !== roleKey) {
        extraArea.innerHTML = "";
        actionHelp.innerText = "";
        if (role === "魔術師") {
            actionHelp.innerText = "ターゲットの役職を予想してください。正解ならターゲットを殺害、外れると自分が死亡します。";
            const label = document.createElement("label"); label.innerText = "予想役職: ";
            const select = document.createElement("select"); select.id = "roleGuessSelect"; select.style.padding = "6px";
            MAGICIAN_GUESS_ROLES.forEach(([id, name]) => { const opt=document.createElement("option"); opt.value=id; opt.innerText=name; select.appendChild(opt); });
            label.appendChild(select); extraArea.appendChild(label);
        } else if (role === "ボマー") {
            actionHelp.innerText = "爆弾を仕掛けるか、すでに仕掛けた爆弾を起爆します。";
            const select=document.createElement("select"); select.id="bombModeSelect"; select.style.padding="6px";
            const plant=document.createElement("option"); plant.value="plant"; plant.innerText="爆弾を仕掛ける";
            const detonate=document.createElement("option"); detonate.value="detonate"; detonate.innerText="爆弾を起爆する";
            select.appendChild(plant); select.appendChild(detonate); extraArea.appendChild(select);
            const syncBomb = () => {
                const detonating = select.value === "detonate";
                targetSelect.disabled = detonating;
                if (detonating) { selectedNightTarget = "pass"; targetSelect.value = "pass"; actionHelp.innerText = "設置済みの爆弾をすべて同時に起爆します。起爆対象を選ぶ必要はありません。"; }
            };
            select.onchange = syncBomb; syncBomb();
        }
        const helps={
            "シーフ":"選択したプレイヤーを殺害し、その役職を盗みます。","ねずみ":"1回だけ使用できます。使用されたことだけ全体通知され、調査結果は自分だけに表示されます。",
            "挑発者":"対象の次の昼の票数を+2します。残り2回まで使用できます。","ドクター":"対象が夜に死亡した場合、蘇生できます。同じ対象を2夜連続では選べません。",
            "ポリス":"対象の夜能力を封じます。同じ対象を2夜連続では選べません。","トラッパー":"対象の家に罠を仕掛け、そこを訪れた人のうち1人をランダムに封じます。",
            "ルックアウト":"対象の家を訪れたプレイヤーを確認します。","インベスティゲーター":"対象の役職候補を2つに絞り込みます。",
            "トラッカー":"対象が夜に訪れた家を確認します。","ゴースト":"対象の家にろうそくを置き、投票で追放された場合は次の夜に復讐します。",
            "バカ":"あなたには別のイノセント役職に見えていますが、実際には能力を持ちません。","ブレイマー":"対象の死亡・追放時の役職表示をインポスターに見せます。残り2回まで使用できます。",
            "クリーナー":"対象が死亡・追放された際、その役職を不明にします。","シリアルキラー":"対象を殺害します。ポリスやトラッパーでは止まりません。",
            "サバイバー":"夜の行動はありません。殺害されても最大3回まで復活します。"
        };
        if (helps[role]) actionHelp.innerText = helps[role];
        extraArea.dataset.roleKey = roleKey;
    }
}

async function handleActionSubmit() {
    const action = {
        target_id: document.getElementById("targetSelect").value || selectedNightTarget || "pass",
        attack_target_id: document.getElementById("attackTargetSelect")?.value || selectedAttackTarget || "pass"
    };
    const guessSelect = document.getElementById("roleGuessSelect");
    if (guessSelect) action.guessed_role = guessSelect.value;
    const bombMode = document.getElementById("bombModeSelect");
    if (bombMode) { action.bomb_action = bombMode.value; if (bombMode.value === "detonate") action.target_id = "pass"; }
    try {
        const result = await API.sendAction(currentRoomCode, currentPlayerId, action);
        selectedNightTarget = action.target_id || "pass";
        selectedAttackTarget = action.attack_target_id || "pass";
        document.getElementById("actionArea").style.display = "none";
        document.getElementById("submittedText").style.display = "block";

        // ホストは自分のアクションを提出しても、夜を終了する権限を失わない。
        // まだ夜なら即座にボタンを再表示する。
        const nightEndArea = document.getElementById("nightEndArea");
        if (nightEndArea) {
            nightEndArea.style.display = result.phase === "NIGHT" ? "block" : "none";
        }
    } catch (err) { alert(err.message); }
}

function renderPrivateReports(info) {
    const box = document.getElementById("privateReportBox"); if (!box) return;
    if (!info.private_reports || info.private_reports.length === 0) {
        box.style.display = "none"; box.innerText = ""; return;
    }
    box.innerHTML = "";
    const title = document.createElement("div");
    title.innerText = "個人履歴（自分だけに表示）";
    title.style.cssText = "font-weight:bold;margin-bottom:8px;";
    box.appendChild(title);
    info.private_reports.forEach(report => {
        const div = document.createElement("div"); div.innerText = report; div.style.marginBottom = "6px"; box.appendChild(div);
    });
    box.style.display = "block";
}

function renderVoteArea(info) {
    const voteArea = document.getElementById("voteArea");
    const voteSelect = document.getElementById("voteSelect");
    const votedText = document.getElementById("votedText");
    if (!voteArea || !voteSelect) return;
    if (info.phase !== "DAY" || !info.alive) {
        voteArea.style.display = "none";
        if (votedText && info.phase !== "DAY") votedText.style.display = "none";
        return;
    }
    const provokedNotice = document.getElementById("provokedNotice");
    if (provokedNotice) { provokedNotice.style.display = info.provoked_bonus > 0 ? "block" : "none"; provokedNotice.innerText = info.provoked_bonus > 0 ? `挑発者の能力により、あなたには最初から${info.provoked_bonus}票入っています。` : ""; }
    if (info.can_vote === false) {
        voteArea.style.display = "none";
        if (votedText) { votedText.style.display = "block"; votedText.innerText = "挑発者の能力を使用したため、この昼は投票できません。"; }
        return;
    }
    if (info.vote_submitted) {
        voteArea.style.display = "none";
        if (votedText) votedText.style.display = "block";
        return;
    }
    const optionIds = ["pass", ...(info.targets || []).filter(t => t.id !== "pass").map(t => t.id)].join(",");
    if (voteSelect.dataset.optionIds !== optionIds) {
        const keep = voteSelect.value || selectedVoteTarget || "pass";
        voteSelect.innerHTML = "";
        const pass = document.createElement("option");
        pass.value = "pass"; pass.innerText = "棄権"; voteSelect.appendChild(pass);
        (info.targets || []).forEach(t => {
            if (t.id === "pass") return;
            const opt = document.createElement("option");
            opt.value = t.id; opt.innerText = t.name; voteSelect.appendChild(opt);
        });
        voteSelect.dataset.optionIds = optionIds;
        selectedVoteTarget = [...voteSelect.options].some(o => o.value === keep) ? keep : "pass";
        voteSelect.value = selectedVoteTarget;
    } else if (selectedVoteTarget && [...voteSelect.options].some(o => o.value === selectedVoteTarget)) {
        voteSelect.value = selectedVoteTarget;
    }
    voteSelect.onchange = () => { selectedVoteTarget = voteSelect.value; };
    voteArea.style.display = "block";
    if (votedText) votedText.style.display = "none";
}

async function handleVoteSubmit() {
    try {
        await API.sendVote(currentRoomCode, currentPlayerId, document.getElementById("voteSelect").value);
        document.getElementById("voteArea").style.display = "none";
        document.getElementById("votedText").style.display = "block";
    } catch (err) { alert(err.message); }
}

function renderParticipants(info) {
    const list = document.getElementById("participantsList");
    const count = document.getElementById("participantCount");
    if (!list) return;

    const participants = info.participants || [];
    if (count) count.innerText = `(${participants.length}人)`;
    list.innerHTML = "";

    participants.forEach(p => {
        const row = document.createElement("div");
        row.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:8px 10px;border:1px solid #ddd;border-radius:6px;background:#fafafa;";

        const name = document.createElement("span");
        name.innerText = p.name + (p.is_host ? " 👑" : "");
        name.style.fontWeight = p.is_host ? "bold" : "normal";

        const status = document.createElement("span");
        status.innerText = p.alive ? "生存" : "死亡";
        status.style.color = p.alive ? "#198754" : "#dc3545";
        status.style.fontSize = "0.9em";

        row.appendChild(name);
        const right = document.createElement("div"); right.style.cssText="display:flex;gap:8px;align-items:center;flex-shrink:0;"; right.appendChild(status);
        if (info.is_host && !p.is_host) { const k=document.createElement("button"); k.innerText="キック"; k.style.cssText="padding:3px 7px;background:#dc3545;color:white;border:0;border-radius:4px;"; k.onclick=()=>handleKick(p.id,p.name); right.appendChild(k); }
        row.appendChild(right);
        list.appendChild(row);
    });
}

function resetDayUI() {
    selectedVoteTarget = "pass";
    const voteSelect = document.getElementById("voteSelect");
    if (voteSelect) { voteSelect.dataset.optionIds = ""; voteSelect.value = "pass"; }
    const votedText = document.getElementById("votedText"); if (votedText) votedText.style.display = "none";
}

function renderDayTimer(info) {
    const box = document.getElementById("dayTimerDisplay");
    if (!box) return;
    if (info.phase !== "DAY") {
        box.style.display = "none";
        if (dayTimerInterval) { clearInterval(dayTimerInterval); dayTimerInterval = null; }
        return;
    }
    box.style.display = "block";
    let remaining = Math.max(0, Number(info.day_timer_remaining ?? info.day_timer ?? 0));
    const render = () => {
        const sec = Math.max(0, Math.ceil(remaining));
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        box.innerText = `昼の残り時間: ${m}:${String(s).padStart(2, "0")}`;
    };
    render();
    if (dayTimerInterval) clearInterval(dayTimerInterval);
    dayTimerInterval = setInterval(() => {
        remaining -= 1;
        render();
        if (remaining <= 0) {
            clearInterval(dayTimerInterval);
            dayTimerInterval = null;
            updateGameState();
        }
    }, 1000);
}

function renderResultActions(info) {
    const panel = document.getElementById("resultActions"); if (!panel) return;
    if (info.phase !== "RESULT") { panel.style.display = "none"; return; }
    panel.style.display = "block";
    const names = { innocent:"イノセント", imposter:"インポスター", neutral:"ニュートラル", serial_killer:"シリアルキラー", bomber:"ボマー", survivor:"サバイバー", ghost:"ゴースト", thief:"シーフ", magician:"魔術師", draw:"引き分け" };
    let winner = names[info.winner_faction] || info.winner_faction || "結果";
    const winnerText = document.getElementById("resultWinnerText"); if (winnerText) winnerText.innerText = `勝利: ${winner}`;
    const voteBox = document.getElementById("resultVoteText");
    const vr = info.last_vote_result;
    if (voteBox) {
        if (vr && vr.expelled) voteBox.innerText = `直前の投票: ${vr.expelled.name} が追放されました`;
        else if (vr && vr.status === "tie") voteBox.innerText = "直前の投票: 同票のため追放者なし";
        else if (vr && vr.status === "no_exile") voteBox.innerText = "直前の投票: 追放者なし";
        else voteBox.innerText = "直前の投票: 今回の決着は投票以外で発生しました";
    }
    const list = document.getElementById("resultPlayersList");
    if (list) {
        list.innerHTML = "";
        (info.result_players || []).forEach(p => {
            const row = document.createElement("div");
            row.style.cssText = "display:grid;grid-template-columns:1.2fr 1fr 1fr auto;gap:8px;padding:8px 10px;border-bottom:1px solid #ddd;align-items:center;";
            [p.name, p.camp || "陣営不明", p.role || "不明", p.alive ? "生存" : "死亡"].forEach(v => { const span=document.createElement("span"); span.innerText=v; row.appendChild(span); });
            list.appendChild(row);
        });
    }
    const button = document.getElementById("rematchButton"); if (button) button.style.display = info.is_host ? "block" : "none";
    const waiting = document.getElementById("rematchWaitingText"); if (waiting) waiting.style.display = info.is_host ? "none" : "block";
}

async function handleNightEnd() {
    if (!currentRoomCode || !currentPlayerId) return;
    const button = document.getElementById("nightEndButton");
    if (button) { button.disabled = true; button.innerText = "夜を終了中..."; }
    try {
        await API.endNight(currentRoomCode, currentPlayerId);
        await updateGameState();
    } catch (err) {
        alert(err.message);
    } finally {
        if (button) { button.disabled = false; button.innerText = "夜を終了する（ホスト）"; }
    }
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

async function handleKick(id, name) {
    if (!confirm(`${name} をキックしますか？`)) return;
    try { await API.kickPlayer(currentRoomCode,currentPlayerId,id); await updateGameState(); } catch(e){ alert(e.message); }
}
async function handleForceFinish() {
    if (!confirm("現在のゲームを強制終了して、同じルームの設定画面へ戻しますか？")) return;
    try { await API.forceFinish(currentRoomCode,currentPlayerId); await updateGameState(); } catch(e){ alert(e.message); }
}
function renderSystemMessages(info) {
    const box=document.getElementById("systemMessages"); if(!box) return;
    const msgs=info.system_messages||[]; box.innerHTML="";
    msgs.slice(-12).forEach(m=>{const d=document.createElement("div");d.innerText=m;box.appendChild(d);});
    box.style.display=msgs.length?"block":"none";
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
        document.body.dataset.uiVersion = info.ui_version || "unknown";
        const roleName = document.getElementById("roleName");
        const campText = info.camp_name || (info.camp === "innocent" ? "イノセント" : info.camp === "imposter" ? "インポスター" : info.camp === "neutral" ? "ニュートラル" : "陣営不明");
        roleName.innerText = `あなたの役職: ${info.displayed_role}（${campText}陣営）`;
        roleName.dataset.role = info.displayed_role;
        document.getElementById("statusText").innerText = info.alive ? "状態: 生存" : "状態: 死亡";
        renderParticipants(info);
        renderSystemMessages(info);
        const submitted = document.getElementById("submittedText");
        if (submitted && info.phase !== "NIGHT") submitted.style.display = "none";
        const resultBox = document.getElementById("resultBox");
        if (info.message) { resultBox.innerText = info.message; resultBox.style.display = "block"; }
        renderPrivateReports(info);
        document.getElementById("hostControls").style.display = info.is_host && info.phase === "SETUP" ? "block" : "none";
        const ff=document.getElementById("forceFinishTop"); if(ff) ff.style.display = info.is_host && !["SETUP","RESULT"].includes(info.phase) ? "inline-block" : "none";
        const nightEndArea = document.getElementById("nightEndArea");
        if (nightEndArea) {
            // ホストの「夜を終了する」は、自分のアクション提出状態とは独立して表示する。
            // 他プレイヤーが未提出なら、ホスト自身が提出済みでもこのボタンを残す。
            const showNightEnd = Boolean(info.is_host && info.phase === "NIGHT");
            nightEndArea.style.display = showNightEnd ? "block" : "none";
        }
        if (lastRenderedPhase !== info.phase) {
            if (info.phase === "DAY") resetDayUI();
            lastRenderedPhase = info.phase;
        }
        renderDayTimer(info);
        if (info.phase !== "NIGHT") {
            selectedNightTarget = "pass";
            selectedAttackTarget = "pass";
            nightUiBuilt = false;
            nightUiPhase = info.phase;
            const ts=document.getElementById("targetSelect"); if(ts) ts.dataset.optionIds="";
            const as=document.getElementById("attackTargetSelect"); if(as) as.dataset.optionIds="";
        }
        if (info.phase === "NIGHT" && info.alive && !info.action_submitted) {
            if (nightUiPhase !== "NIGHT") {
                nightUiPhase = "NIGHT";
                nightUiBuilt = true;
            }
            buildRoleActionUI(info);
            document.getElementById("actionArea").style.display = "block";
            document.getElementById("submittedText").style.display = "none";
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

const API = {
    // 共通のヘッダー設定
    headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
    },

    async createRoom() {
        const res = await fetch('/api/room/create', { 
            method: 'POST',
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        if (!res.ok) throw new Error("部屋の作成に失敗しました");
        return await res.json();
    },

    async joinRoom(roomCode, playerName) {
        const res = await fetch('/api/room/join', {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ room_code: roomCode, player_name: playerName })
        });
        if (!res.ok) throw new Error("部屋への参加に失敗しました");
        return await res.json();
    },

    async getPlayerInfo(roomCode, playerId) {
        const res = await fetch(`/api/room/${roomCode}/player/${playerId}`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        if (!res.ok) throw new Error("情報の取得に失敗しました");
        return await res.json();
    },

    async sendAction(roomCode, actorId, targetId) {
        const res = await fetch(`/api/room/${roomCode}/action`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ actor_id: actorId, target_id: targetId })
        });
        if (!res.ok) throw new Error("行動の送信に失敗しました");
        return await res.json();
    },

    async sendVote(roomCode, actorId, targetId) {
        const res = await fetch(`/api/room/${roomCode}/vote`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ actor_id: actorId, target_id: targetId })
        });
        if (!res.ok) throw new Error("投票の送信に失敗しました");
        return await res.json();
    }
};
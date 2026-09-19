const API = {
    async createRoom() {
        const res = await fetch('/api/room/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) throw new Error("部屋の作成に失敗しました");
        return await res.json();
    },

    async joinRoom(roomCode, playerName) {
        const res = await fetch(`/api/room/${roomCode}/join`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: playerName }) // ← player_name から name に修正
        });
        if (!res.ok) throw new Error("部屋への参加に失敗しました");
        return await res.json();
    },

    async getPlayerInfo(roomCode, playerId) {
        const res = await fetch(`/api/room/${roomCode}/player/${playerId}`);
        if (!res.ok) throw new Error("プレイヤー情報の取得に失敗しました");
        return await res.json();
    },

    async sendAction(roomCode, playerId, targetId) {
        const res = await fetch(`/api/room/${roomCode}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: playerId, target_id: targetId })
        });
        if (!res.ok) throw new Error("アクションの送信に失敗しました");
        return await res.json();
    },

    async sendVote(roomCode, playerId, targetId) {
        const res = await fetch(`/api/room/${roomCode}/vote`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: playerId, target_id: targetId })
        });
        if (!res.ok) throw new Error("投票の送信に失敗しました");
        return await res.json();
    }
};
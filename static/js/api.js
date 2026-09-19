const API = {

    async createRoom() {
        const res = await fetch(
            "/api/room/create",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                }
            }
        );

        if (!res.ok) {
            throw new Error(
                "部屋の作成に失敗しました"
            );
        }

        return await res.json();
    },


    async joinRoom(roomCode, playerName) {
        const res = await fetch(
            `/api/room/${roomCode}/join`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    name: playerName
                })
            }
        );

        if (!res.ok) {
            const data =
                await res.json().catch(() => ({}));

            throw new Error(
                data.detail ||
                "部屋への参加に失敗しました"
            );
        }

        return await res.json();
    },


    async getPlayerInfo(roomCode, playerId) {
        const res = await fetch(
            `/api/room/${roomCode}/player/${playerId}`
        );

        if (!res.ok) {
            throw new Error(
                "プレイヤー情報の取得に失敗しました"
            );
        }

        return await res.json();
    },


    async sendAction(roomCode, playerId, action) {
        const res = await fetch(
            `/api/room/${roomCode}/action`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    player_id: playerId,
                    ...action
                })
            }
        );

        if (!res.ok) {
            const data =
                await res.json().catch(() => ({}));

            throw new Error(
                data.detail ||
                "アクションの送信に失敗しました"
            );
        }

        return await res.json();
    },


    async sendVote(roomCode, playerId, targetId) {
        const res = await fetch(
            `/api/room/${roomCode}/vote`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    player_id: playerId,
                    target_id: targetId
                })
            }
        );

        if (!res.ok) {
            const data =
                await res.json().catch(() => ({}));

            throw new Error(
                data.detail ||
                "投票の送信に失敗しました"
            );
        }

        return await res.json();
    },


    async updateSettings(roomCode, settings) {
        const res = await fetch(
            `/api/room/${roomCode}/settings`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(settings)
            }
        );

        if (!res.ok) {
            const data =
                await res.json().catch(() => ({}));

            throw new Error(
                data.detail ||
                "設定の更新に失敗しました"
            );
        }

        return await res.json();
    },


    async startGame(roomCode, hostPlayerId) {
        const res = await fetch(
            `/api/room/${roomCode}/start`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    host_player_id: hostPlayerId
                })
            }
        );

        if (!res.ok) {
            const data =
                await res.json().catch(() => ({}));

            throw new Error(
                data.detail ||
                "ゲームの開始に失敗しました"
            );
        }

        return await res.json();
    }
};
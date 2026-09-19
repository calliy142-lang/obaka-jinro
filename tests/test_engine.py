import pytest
from app.models.enums import Faction, Phase
from app.models.roles import ROLE_DEFINITIONS
from app.models.player import PlayerState, PlayerRoleState
from app.core.state import GameState
from app.core.engine import GameEngine

@pytest.fixture
def game_setup():
    """テスト用の基本ゲーム環境をセットアップ"""
    state = GameState(session_id="test_session")
    
    # プレイヤー作成
    p1_role = PlayerRoleState(ROLE_DEFINITIONS["doctor"], ROLE_DEFINITIONS["doctor"], Faction.INNOCENT, ROLE_DEFINITIONS["doctor"].win_condition)
    p2_role = PlayerRoleState(ROLE_DEFINITIONS["police"], ROLE_DEFINITIONS["police"], Faction.INNOCENT, ROLE_DEFINITIONS["police"].win_condition)
    p3_role = PlayerRoleState(ROLE_DEFINITIONS["fool"], ROLE_DEFINITIONS["police"], Faction.INNOCENT, ROLE_DEFINITIONS["fool"].win_condition) # バカ（表示:ポリス）
    p4_role = PlayerRoleState(ROLE_DEFINITIONS["killer"], ROLE_DEFINITIONS["killer"], Faction.NEUTRAL, ROLE_DEFINITIONS["killer"].win_condition)

    state.add_player(PlayerState("p1", "アリス", p1_role))
    state.add_player(PlayerState("p2", "ボブ", p2_role))
    state.add_player(PlayerState("p3", "チャーリー", p3_role))
    state.add_player(PlayerState("p4", "ダニエル", p4_role))

    state.phase = Phase.NIGHT
    engine = GameEngine(state)
    return engine, state

def test_police_blocks_killer(game_setup):
    """ポリスがキラーを止め、誰も死なないことをテスト"""
    engine, state = game_setup

    engine.submit_night_action("p2", "p4")  # ポリス(p2) -> キラー(p4)を阻止
    engine.submit_night_action("p4", "p1")  # キラー(p4) -> アリス(p1)を攻撃
    engine.process_night()

    # キラーは阻害されたため、アリスは生存しているはず
    assert state.players["p1"].alive is True

def test_fool_does_not_block(game_setup):
    """バカ（見た目ポリス）がキラーを指定しても攻撃を止められないことをテスト"""
    engine, state = game_setup

    engine.submit_night_action("p3", "p4")  # バカ(p3) -> キラー(p4)を指定（能力不発）
    engine.submit_night_action("p4", "p1")  # キラー(p4) -> アリス(p1)を攻撃
    engine.process_night()

    # アリスは死亡しているはず
    assert state.players["p1"].alive is False

def test_doctor_saves_target(game_setup):
    """ドクターが治療した対象が救出されるかテスト"""
    engine, state = game_setup

    engine.submit_night_action("p1", "p2")  # ドクター(p1) -> ボブ(p2)を保護
    engine.submit_night_action("p4", "p2")  # キラー(p4) -> ボブ(p2)を攻撃
    engine.process_night()

    # ドクターに救命されたためボブは生存しているはず
    assert state.players["p2"].alive is True

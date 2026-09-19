\# おバカ人狼 (Obaka Jinro) - Game Engine \& Web API



Feignライクなゲーム仕様（真の役職と見た目の役職の分離、優先度別夜解決エンジン、GMレス動作）を備えた人狼ゲームサーバーです。



\## 起動方法



```bash

pip install -r requirements.txt

uvicorn app.main:app --reload

---

### `app/models/enums.py`

`obaka_jinro/app/models/enums.py`

陣営、能力タイプ、ゲームフェーズ、勝敗判定などの列挙型定義です。今後の役職拡張（ルックアウト、魔術師、シーフ等）にも耐えられる共通定数をまとめています。

```python
from enum import Enum, auto

class Faction(str, Enum):
    """陣営"""
    INNOCENT = "イノセント"
    IMPOSTER = "インポスター"
    NEUTRAL = "ニュートラル"

class AbilityType(str, Enum):
    """夜行動のタイプ"""
    NONE = "なし"
    VISIT = "訪問"          # 家を出て相手に作用する（ドクター、ポリス、ルックアウト等）
    ATTACK = "攻撃"         # 殺害目的（シリアルキラー、魔術師等）
    TRAP = "トラップ"       # 自宅設置型（トラッパー）
    INFO = "情報"           # 調査系（インベスティゲーター、ねずみ等）

class Phase(str, Enum):
    """ゲームの進行フェーズ"""
    SETUP = "SETUP"         # 参加者待機・役職配布
    NIGHT = "NIGHT"         # 夜行動受け付け
    DAY = "DAY"             # 翌朝の結果発表・議論
    VOTE = "VOTE"           # 投票フェーズ
    ENDED = "ENDED"         # ゲーム終了・勝利陣営決定

class StatusEffectType(str, Enum):
    """プレイヤーに付与される状態異常"""
    POLICED = "POLICED"     # ポリスにより行動阻害
    TRAPPED = "TRAPPED"     # トラップにより行動不能
    CLEANED = "CLEANED"     # クリーナー対象（死亡時役職伏せ）
    PROTECTED = "PROTECTED" # 護衛状態

class WinCondition(str, Enum):
    """勝利条件"""
    FACTION = "FACTION"     # 所属陣営の勝利条件に従う
    SOLO_KILL = "SOLO_KILL" # 他全員の死亡（シリアルキラー・ボマー）
    SURVIVAL = "SURVIVAL"   # ゲーム終了時生存（サバイバー）
    EXILE = "EXILE"         # 追放されること（魔術師等）
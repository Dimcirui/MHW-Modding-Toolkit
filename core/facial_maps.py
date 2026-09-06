"""core/facial_maps.py — 读 assets/facial_maps/ 下的面部骨骼对应表。

为什么是数据文件而不是代码里的字面量
------------------------------------
面部对应表全是**人标出来的**：标准键系统覆盖 52 个身体槽 + 50 个辅助骨槽，面部一个
都没有，而且实测各游戏面部骨之间没有 1:1 的自动对应，靠几何推不出来。所以每加一个
游戏对，就是加一份人标的表——那是数据，不是逻辑。

原先 Endfield->MHWilds 那份写死在 ``games/mhws/operators.py`` 里，存档时又抄了一份到
assets 下，于是同一份数据有两个副本、改一处不会有任何报错。现在反过来：**assets 下的
JSON 是唯一权威**，代码从这里读。再加游戏对只需要丢一个 JSON 进去。

顺序是有意义的
--------------
改名是"先到先得、后到的合并进去"（见 ``weight_utils.rename_or_merge_vgroup``），所以
表里的先后决定了哪一个源顶点组把名字让给了目标、哪些被并进去。JSON 对象在 Python 里
保持插入顺序，这一点是靠得住的；但**不要把这些文件拿去做键排序的格式化**。
"""

import json
import os

_CACHE = {}


def _dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets", "facial_maps")


def load(name):
    """返回 ``[(源名, 目标名), ...]``，保持文件里的顺序；读不到时返回空列表。

    读不到就是空——面部表是可选数据，缺一份的表现应当是"那个按钮什么都不做"，
    而不是插件加载失败。
    """
    if name in _CACHE:
        return _CACHE[name]
    path = os.path.join(_dir(), name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        pairs = list((data.get("map") or {}).items())
    except Exception as exc:                       # noqa: BLE001 - 见上
        print("[Modding-Toolkit] facial map %s unavailable: %r" % (name, exc))
        pairs = []
    _CACHE[name] = pairs
    return pairs


def available():
    try:
        return sorted(f[:-5] for f in os.listdir(_dir()) if f.endswith(".json"))
    except OSError:
        return []

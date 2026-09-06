# 面部骨骼对应表 · 存档

这里既是存档，也是**运行时数据**：`core/facial_maps.py` 从这里读表，
`mhws.endfield_face_rename` 和 `mhwi.endfield_face_rename` 各用一份。剩下两份暂时
没有对应的操作符，纯存档。

放在这里而不是写死在代码里，是因为这些对应关系是**手工标注出来的数据，不是逻辑**：
再加一个游戏对只需要丢一个 JSON 进来。曾经 Endfield→MHWilds 那份在代码和 assets 下
各存了一份，改一处不会有任何报错——现在 assets 是唯一权威。

**顺序有意义**：改名是先到先得、后到的合并进去，所以表里的先后决定了哪个源顶点组
把名字让给目标。不要对这些文件做键排序的格式化。

## 为什么这些数据换不来

`core/bone_mapper.py` 的标准键系统覆盖 52 个身体骨槽 + 50 个辅助骨槽，**面部一个都
没有**。面部也做不出通用槽位：实测 MHWS / RE4 / RE9 三家的面部骨之间**没有 1:1 的
自动对应**，按区域分类可行，单靠几何不行。所以每一对面部对应都只能是人标的。

## 各文件

| 文件 | 方向 | 对数 | 状态 |
|---|---|---|---|
| `endfield_to_mhwi.json` | Endfield → MHWorld | 97 | 从旧插件找回，代码里已无 |
| `endfield_to_mhws.json` | Endfield → MHWilds | 97 | **运行时数据**，`mhws.endfield_face_rename` 读它 |
| `endfield_to_re4.json` | Endfield → RE4 | 49 | 死表存档 |
| `mhwi_to_re4.json` | MHWorld → RE4 | 26 | 死表存档 |

## 为什么不能由一份推出另一份

试过了：拿两份表共有的 94 个 Endfield 骨名把 MHWilds 名复合到 MhBone 上，得到 59 个
MHWilds 面部骨，其中 **49 个唯一、10 个有歧义**。歧义全在眉毛和上眼睑——MHWorld 那边
是两排骨（`MhBone_305~308` 和 `browLine 316~318`），荒野那边压成了 A/B/C 三根，
2 排 → 1 排不是一一对应。

这直接决定了 `mhws.face_weight_simplify` **搬不到 MHWorld 上**：它用到 59 个骨名，
其中 10 个有歧义，而 `L_EyeBrow_B_LOD01` / `R_EyeBrow_B_LOD01` 这两个歧义项还是
**合并的目标骨**。目标骨必须唯一，靠复合定不下来。真要做 MHWorld 版，得按 MHWorld
自己的面部骨表重新设计合并组与分配比例，那是设计决定，不是能推出来的东西。

## 面部/躯干是怎么分的

按名字 token 划分（`brow` `eye` `lip` `tongue` `nose` `jaw` `cheek` `tooth` `iris`
`pupil` 等，以及目标侧的 `Brow` `Eyelid` `MouthCorner` `Risorius` `Chin` 等）。分到
躯干那半边的条目没有丢，收在各文件的 `body_leftovers` 字段里。

躯干部分之所以不当作正文，是因为**它可以由预设推出来**，而且推出来的往往更对。逐条
比对过：

- `VRC_TO_RE4_MAP` 51 条里 50 条与预设一致，唯一分歧是 `Spine → Spine_0`（预设给
  `Spine_1`）——就是已知的"脊椎差一节，以预设为准"。整张表零独有价值，已删。
- `MHWI_TO_RE4_MAP` 的躯干有 15 条与预设不一致，其中**扭转骨那几条是老表错了**：
  它把 `MhBone_006`（上臂）映到 `L_UpperArm_Twist_s1`、把 `MhBone_080`（上臂扭转）
  映到 `L_UpperArm`，两者对调了。MHWI 的扭转骨只有 080~083，见骨骼 ID 表。
  **别照抄 `body_leftovers` 里的躯干条目。**

## 可信度

全部是 hand-made、**未经实机验证**。`endfield_to_mhwi.json` 的作者原注里躯干大部分
是注释掉的状态，只留了 `_ty_/_tz_` 修正骨，而且把它们指向**扭转骨**而不是父段骨
（`L_UpperArm_ty_minus` → `MhBone_080`）。这与 `core/chain_classifier.py` 现在的
"修正骨并进父骨"不一致；作者确认当年是**凭感觉随手归类**的，所以那几条不作数，
按父骨走。

# Licensing scope / 授权范围说明

## English

The GNU General Public License v3.0 in [`LICENSE`](LICENSE) applies to the
**source code of this add-on** (`*.py`) and to the author-created data files —
the JSON presets, export schemes, bone/pose/import presets and facial maps
under `assets/`.

It does **not** apply to the following, which are redistributed here only as
reference data required for the tools to work, and which remain the property of
their respective rights holders:

### Game data

| Path | Content |
|---|---|
| `assets/reference_skeletons/` | character FBX skeletons converted from game files |
| `assets/native_skeletons/`, `assets/mhws/bonesystem/` | native `.fbxskel` / `.refskel` / `.skeleton` files |
| `assets/blank_files/` | minimal `.mesh` / `.mdf2` / `.mod3` / `.gpuc` / `.chain2` / `.clsp` / `.user` / `.evhl` templates |
| `assets/mhwi/`, `assets/mhrs/` | body, shadow, effect and watermark assets |
| `assets/mdf_presets/**/*.dds` | reference textures |

These are derived from assets owned by **CAPCOM CO., LTD.** No ownership is
claimed over them and no license to them is granted by this repository. They
are included solely to make the add-on usable for non-commercial modding of
games the user already owns. Rights holders who want any of it removed can open
an issue and it will be taken down.

### Third-party binaries

| Path | Component | License |
|---|---|---|
| `assets/bin/texconv/texconv.dll` | matyalatte's [Texconv-Custom-DLL](https://github.com/matyalatte/Texconv-Custom-DLL), wrapping Microsoft's DirectXTex `texconv` | MIT — see `assets/bin/texconv/THIRD_PARTY_LICENSES.txt` |
| `assets/bin/gdeflate/GDeflateWrapper.dll` | GDeflate compression wrapper | see upstream |

`addon_updater.py` and `addon_updater_ops.py` are CGCookie's Blender Addon
Updater, GPL-3.0-or-later.

---

## 中文

[`LICENSE`](LICENSE) 中的 GNU GPL v3.0 适用于**本插件的源代码**（`*.py`）以及作者自行编写的数据文件——即 `assets/` 下的 JSON 预设、导出方案、骨骼/姿态/导入预设和面部对应表。

它**不适用于**以下内容。这些文件仅作为工具运行所必需的参考数据被一并提供，版权归各自权利人所有：

### 游戏数据

| 路径 | 内容 |
|---|---|
| `assets/reference_skeletons/` | 由游戏文件转换而来的角色 FBX 骨架 |
| `assets/native_skeletons/`、`assets/mhws/bonesystem/` | 原生 `.fbxskel` / `.refskel` / `.skeleton` 文件 |
| `assets/blank_files/` | 最小化的 `.mesh` / `.mdf2` / `.mod3` / `.gpuc` / `.chain2` / `.clsp` / `.user` / `.evhl` 模板 |
| `assets/mhwi/`、`assets/mhrs/` | 身体、阴影、特效及水印资产 |
| `assets/mdf_presets/**/*.dds` | 参考贴图 |

上述内容衍生自 **株式会社卡普空（CAPCOM CO., LTD.）** 所有的资产。本仓库不对其主张任何权利，也不就其授予任何许可。收录它们的唯一目的，是让本插件能够用于对用户已购买游戏的非商业性 Mod 制作。若权利人希望移除其中任何内容，请提 issue，我会撤下。

### 第三方二进制文件

| 路径 | 组件 | 授权 |
|---|---|---|
| `assets/bin/texconv/texconv.dll` | matyalatte 的 [Texconv-Custom-DLL](https://github.com/matyalatte/Texconv-Custom-DLL)，封装微软 DirectXTex 的 `texconv` | MIT，见 `assets/bin/texconv/THIRD_PARTY_LICENSES.txt` |
| `assets/bin/gdeflate/GDeflateWrapper.dll` | GDeflate 压缩封装 | 见上游 |

`addon_updater.py` 与 `addon_updater_ops.py` 为 CGCookie 的 Blender Addon Updater，GPL-3.0-or-later。

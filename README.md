# Modding Toolkit (Blender Addon)

[中文说明见下方](#中文说明)

A comprehensive Blender toolkit for game modding. Primarily targets several Capcom titles, with partial support for others.

**Supported Blender Versions**: 4.x (recommended 4.3+)

---

## Fully Supported Games

These games have a dedicated module.

* Monster Hunter World: Iceborne (MHWI)
* Monster Hunter Rise: Sunbreak (MHRS)
* Monster Hunter Wilds (MHWs)
* Resident Evil 4 Remake (RE4R)
* Resident Evil: Requiem (RE9)

## Basic Support

These games can only use the most general-purpose tools.

* Street Fighter 6 (SF6)
* Devil May Cry 5 (DMC5)
* Helldivers 2 (HD2)

## Core Features

### 1. Skeleton & Mesh Convert
Convert any source model into any target game's format by aligning the skeleton and renaming vertex groups, driven by customizable JSON presets.

* **X → Y Architecture**: Define your source (X) and target (Y) freely.
    * **Source (X)**: any of the games above, VRChat, MMD, Endfield, Granblue Fantasy, or any preset you create yourself.
    * **Target (Y)**: any of the games above, or any preset you create yourself.
* Fuzzy bone-name matching: separators (`_`, `.`, space) are normalized when matching bone names, so preset-driven operations are unaffected by naming style differences in the source.
* **Bone Align** [X+Y, dual armature]: aligns the model's skeleton to the target game's skeleton. The dropdown to the left of the button picks the align mode (Position Only / Position + Roll / Full Align); switching the target (Y) preset syncs it to that preset's default mode, which you can still override by hand.
* Align modes: **Position Only** moves the head and preserves the original direction; **Position + Roll** also copies the roll value; **Full Align** copies head, tail and roll.
* **Same-Kind Bone Align**: tick this when both armatures are already the same kind — bones are matched by name and no preset is needed. Ticking it leaves only the align action in this section.
* **Rename Vertex Groups** [X+Y]: renames vertex groups directly on the mesh.
* **Non-Physics Workflow tools**: mainly for getting rid of physics bones and weights — physics weight downgrade, remove physics bones, rename base bones.
* **Physics Workflow tools**: mainly for transplanting physics bones from source to target (specialised for MT Framework and RE Engine) plus the bone-marking utilities around it, so the one-click physics creation in the fully supported games is easier to use.

### 2. Pose Convert
A standalone pose transformation system, independent of the skeleton converter.

* **Direction Calc**: a simple tool that only rotates the upper arms to horizontal, intended for MMD-style models.
* **RE Engine Matrix Zero**: resets limb bone rotation matrices on RE Engine skeletons (Wilds / RE4R / RE9 / SF6 / MHRS / DMC5).
* **Pose Transform Recorder**: records the relative rotation between two poses of the same skeleton type, then applies it forward (A→B) or inverse (B→A) to any skeleton of that type.
    * Record once, use forever — no need to keep a reference armature in the scene every time.
    * Stored as JSON under `assets/presets/pose/`; addon updates do not remove existing records.

### 3. Visual Preset Editor
A built-in GUI editor for creating custom bone mappings without writing code.
* Pick bones by clicking them in the 3D viewport.
* Batch-add auxiliary bones.
* Smart mirror: generates the right-side mapping from the left automatically. If mirroring fails, pick the bone manually.
* Category-grouped preset dropdown, for managing large preset libraries.

### 4. General Basic Tools
* Zero Roll, Add Tail Bone, Mirror Align X.
* **Bone & Weight Merge**: merging bones merges their weights too. This covers every mesh bound to the armature through an Armature modifier, plus meshes that are not bound but are children of the armature and carry a vertex group named after a bone being deleted.
    * **Merge Bones into Active Bone**: bone level — the other selected bones are merged into the last one clicked.
    * **Simplify Selected Chains** / **Merge Chains into Active Chain**: chain level. The former pairs bones up to reduce chain density (an unweighted tail bone at the end of a chain is skipped automatically); the latter merges several chains bone-by-bone by position.
* **Cylindrical Face Normals (Toon)**: replaces the selected faces' custom normals with a cylindrical field, reproducing how anime-stylised face meshes are shaded — normals point horizontally away from the vertical axis, flattening out the shading relief of the nose and lips and leaving only a left-to-right light falloff. Unselected faces (ears, back of the head, under the jaw) keep their own normals, and the boundary transitions on its own through angle-weighted vertex averaging.
* **Reset Face Normals**: resets face normals back to smooth shading, and can weld the coincident vertices that UV / material borders split apart, removing the normal seams those cuts leave behind.
* **Apply Modifiers to Meshes with Shape Keys**: applies modifiers directly without disturbing the mesh's shape keys. Only for modifiers that do not change topology.
* **Separate by Materials**: splits the selected meshes into one object per material, cleans up the shape keys and vertex groups, and renames each fragment after its material.
* **Texture Processing**: outputs either **DDS** or the `.tex` files some games need directly.
    * Output size readout: the final output size is shown at the bottom of the panel, turning red with a warning when it is not a power of two (non-power-of-two textures can crash the game).
    * Resize output: the size can be entered by hand. The recommended default snaps to the nearest power of two when it is within 15%, and rounds up to the next one otherwise.
* **Drag an Image in to Convert to DDS**: drop an image into the viewport and pick "Convert to DDS" from the menu. Every file is listed with its own DXGI format dropdown and converted in one batch. A filename whose purpose cannot be identified falls back to **BC7 sRGB**.

### 5. Game-Specific Modules

**Some features in these modules depend on the following addons; installing them is recommended**:
* [MHW Model Editor](https://github.com/NSACloud/RE-Mesh-Editor)
* [RE Mesh Editor](https://github.com/NSACloud/RE-Mesh-Editor)
* [RE Chain Editor](https://github.com/NSACloud/RE-Mesh-Editor)

#### Monster Hunter World: Iceborne (MHWI)
* Batch import & export
* Align non-physics bones
* MMD shape keys to facial weights
* Set mesh display condition
* Convert selected objects to packed shader: a custom packed shader
* Material processor / generator
* Split physics bones
* One-click rename
* One-click Chain creation

#### Monster Hunter Wilds (MHWS)
* **Armor Batch Exporter**: export the files for all 5 parts (arm / body / helmet / leg / waist) in one click.
    * Supports the 4 armor variants (male hunter male set / male hunter female set / female hunter male set / female hunter female set)
    * Complete armor sets
    * Tells you which file types each piece of armor supports
    * Optionally substitutes a blank file for slots with no collection bound
    * Supports BoneSystem standalone bones
    * Triangulate face meshes before export: avoids the shading break RE Mesh produces when exporting face meshes (the "blotchy face" problem).
* **MDF2 + Tex Semi-Auto Processor**: batch-updates the texture binding paths in an MDF2 collection and converts the source images into game-ready `.tex` files in one step.
    * Per-material PBR inputs (Albedo / Alpha / Normal / Roughness / Metallic / AO / Emissive).
    * Per-slot modes: **PBR Compose** (channel-pack from the PBR inputs), **Direct** (pick any image / DDS / TEX), **Default Null Texture** (write the game's null-texture path), **Skip** (leave the existing path alone).
    * Single-channel inputs support a channel selector (R/G/B/A) and invert (e.g. smoothness→roughness, dielectric→metallic).
    * **GL→DX normal flip**: a per-material toggle; the G-channel flip is applied during processing together with the other channel compositing, so it needs no separate step.
    * Existing null-texture paths are detected on refresh and set to "Default Null Texture" mode.
    * Material configuration can be copied and pasted.
    * State is persisted per collection — switching between MDF2 collections keeps each one's configuration independently.
* **One-Click RE Chain Creation**: detects chain-head bones by colour, shows a collection picker, then calls RE Chain Editor to create Chain Settings and a Chain Group for every chain. Three modes: independent Settings per chain, one shared Settings for all chains, or automatic grouping by chain name with parameters applied per group.
* One-click import and align a Wilds model
* Optimize Wilds skeleton
* Optimize auxiliary bones and weights
* MMD shape keys to facial weights
* One-click add facial bones

#### Monster Hunter Rise: Sunbreak (MHRS)
* Batch export
* Material & texture processor / generator
* One-click RE Chain creation

#### Resident Evil 4 Remake / Resident Evil: Requiem (RE4R / RE9)
* Batch exporter
    * Simplified mode supported: bind collections per group instead of configuring every entry.
* Material & texture processor / generator
* Generate fake bones
* MMD shape keys to facial weights
* One-click add facial bones
* One-click RE Chain creation

#### Resident Evil 4 Remake / Resident Evil: Requiem (RE4R / RE9)
* Batch exporter
* Sync child orientation and roll
* MMD shape keys to facial weights
* One-click add facial bones
* Material & texture processor / generator
* One-click RE Chain creation

---

## Installation

1. Download the **ZIP** file from the Releases page.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click **Install**, select the ZIP, and enable **Modding Toolkit**.

---

## License

The add-on's source code is licensed under the **GNU General Public License
v3.0** — see [`LICENSE`](LICENSE).

That license covers the code and the author-created presets only. The game
files bundled under `assets/` (reference skeletons, blank templates, body and
shadow meshes, textures) are the property of CAPCOM CO., LTD. and are **not**
covered by it, and `assets/bin/` contains third-party MIT components. See
[`NOTICE.md`](NOTICE.md) for the exact scope.

---
<a id="中文说明"></a>
# 中文说明

一款综合性的 Blender 游戏 Mod 制作工具包，主要支持部分卡普空游戏，并部分支持其他游戏。

**支持的 Blender 版本**: 4.x（推荐 4.3+）

---

## 深度支持的游戏

这些游戏有专门的板块支持

* 怪物猎人世界：冰原 (MHWI)
* 怪物猎人崛起：曙光 (MHRS)
* 怪物猎人：荒野 (MHWs)
* 生化危机4重制版 (RE4R)
* 生化危机：镇魂曲（RE9）

## 基本支持的游戏

这些游戏仅能使用最基础的一些工具

* 街霸6 (SF6)
* 鬼泣5 (DMC5)
* 绝地潜兵2 (HD2)

## 核心功能

### 1. 骨架&网格转换
通过可自定义的 JSON 预设，将任意来源模型，通过对齐骨架和修改顶点组的方式，转换为任意目标游戏格式。

* **X → Y 架构**: 自由定义来源 (X) 和目标 (Y)。
    * **来源 (X)**: 上述支持的游戏、VRChat、MMD、明日方舟：终末地、碧蓝幻想，或任何自行创建的预设。
    * **目标 (Y)**: 上述支持的游戏，或任何自行创建的预设。
* 模糊骨骼名匹配: 在匹配骨骼名时自动归一化分隔符（`_`、`.`、空格），使预设驱动的操作不受来源骨骼命名风格差异影响。
* **骨骼对齐** [X+Y, 双骨架]: 将模型骨架对齐到目标游戏骨架。可在按钮左侧的下拉栏中选择对齐模式（仅位置 / 位置+扭转 / 完全对齐），切换目标 (Y) 预设时会自动同步为该预设定义的默认模式，之后仍可手动改选。
* 对齐模式：**仅位置**只移动头部，保留原有方向；**位置+扭转**同时复制扭转值；**完全对齐**同时复制头部、尾部和 Roll。
* **同种类骨骼对齐**: 两个骨架本就是同一种类时勾选，按骨骼名直接匹配，不需要预设。勾选后本区域只保留对齐功能。
* **重命名顶点组** [X+Y]: 直接在网格上重命名顶点组。
* **非物理流程工具组**: 主要是消除物理骨骼/权重相关的功能，有物理权重降级、剔除物理骨骼、基础骨骼改名。
* **物理流程工具组**: 主要是（针对MT Framework和RE Engine特化的）将物理骨骼从来源移植到目标，并进行骨骼标记处理相关的功能（以方便深度支持游戏的物理一键创建功能的使用）。

### 2. 姿态转换
独立于骨架转换器的姿态变换系统。

* **方向计算**: 简易工具，仅将上臂旋转到水平方向，针对MMD类模型使用。
* **RE Engine 矩阵归零**: 重置 RE Engine 游戏骨架的肢体旋转矩阵（适用于荒野/生化4重制/生化9/街霸6/崛起/鬼泣5）。
* **姿态变换记录器**: 录制同类型骨架两个姿态之间的相对旋转变换，之后可正向 (A→B) 或逆向 (B→A) 应用到任何同类型骨架。
    * 录制一次，永久使用——不需要每次都在场景中准备参考骨架。
    * 基于 JSON 文件存储在 `assets/presets/pose/`，插件更新不会删除已有记录。

### 3. 可视化预设编辑器
内置的图形界面编辑器，无需编写代码即可创建自定义骨骼映射。
* 在 3D 视口中点选骨骼进行分配。
* 批量添加辅助骨骼。
* 智能镜像：自动从左侧生成右侧映射。如果映射失败，需要自行手动选择。
* 分类分组的预设下拉菜单，便于管理大型预设库。

### 4. 通用基础工具
* 扭转归零、添加尾骨、镜像对齐 X。
* **骨骼&权重合并**: 合并骨骼时权重一并合并。作用范围是所有通过姿态修改器绑定到该骨架的网格，以及虽未绑定但作为骨架子级、且含有待删骨骼同名顶点组的网格。
    * **合并骨骼到激活骨**: 骨骼级别，其余选中骨并入最后点击的那根。
    * **简化选中骨骼链** / **合并链到激活链**: 链级别，前者两两配对缩减链密度（链末无权重的尾骨自动跳过），后者按位置逐骨合并多条链。
* **面法向柱面化 (三渲二)**: 把选中面的自定义法线换成柱面场，复现动漫风格化脸部网格的做法——法线水平背离竖直轴，抹掉鼻子和嘴唇的着色起伏，只留左右的明暗渐变。未选中的面（耳朵、后脑、脖子底）保留自身法线，边界靠角度加权顶点平均自动过渡。
* **重置面法向**: 使用平滑着色重置面法向，并可焊接 UV / 材质边界处被拆开的重合顶点，消掉切割留下的法线割裂。
* **对有形态键网格应用修改器**: 在不影响网格形态键的情况下直接应用修改器。仅适用于不会改变拓扑的修改器。
* **按材质分离网格**: 把选中网格按材质拆成多个物体、清理网格的形态键和顶点组，并按材质名重命名。
* **贴图处理**: 可输出**DDS** 或 部分游戏直接需要的`.tex`文件。
    * 输出尺寸提示: 面板底部显示最终输出尺寸，不是 2 的 n 次幂时标红并警告（非 2 次幂贴图可能导致游戏崩溃）。
    * 调整输出尺寸: 可手填贴图尺寸。默认推荐值规则是：与最近的 2 的 n 次幂相差 15% 以内时贴到该值，超过则向上取下一个 2 的 n 次幂。
* **拖入图片转 DDS**: 把图片拖进视图，在弹出菜单里选「Convert to DDS」，逐文件列出并可单独指定 DXGI 格式，一次批量转换。文件名识别不出用途时默认 **BC7 sRGB**。

### 5. 游戏专用模块

**这些模块部分功能依赖以下插件，建议安装**：
* [MHW Model Editor](https://github.com/chikichikibangbang/MHW_Model_Editor)
* [RE Mesh Editor](https://github.com/NSACloud/RE-Mesh-Editor)
* [RE Chain Editor](https://github.com/NSACloud/RE-Chain-Editor)

#### 怪猎世界冰原 (MHWI)
* 批量导入&导出
* 对齐非物理骨骼
* MMD形态键转表情权重
* 设置网格显示条件
* 选中物体转为打包着色器：自定义打包着色器
* 材质处理器/生成器
* 拆分物理骨
* 一键重命名
* 一键创建 Chain

#### 怪猎荒野 (MHWS)
* **装备批量导出器**: 一键导出全部5个部位（手臂/身体/头盔/腿/腰）的文件。
    * 支持4种装备变体（男猎男套/男猎女套/女猎男套/女猎女套）
    * 完整的装备集
    * 会提示不同装备支持的文件种类
    * 可选择使用空文件替代未绑定集合的槽位
    * 支持BoneSystem 独立骨骼
    * 导出前面部网格三角化: 用于规避 RE Mesh 导出面部网格时的着色异常（花脸问题）。
* **MDF2 + Tex 半自动贴图处理器**: 批量更新 MDF2 集合中的贴图绑定路径，并将来源图像一步转换为游戏可用的 `.tex` 文件。
    * 每个材质独立配置 PBR 输入（固有色/Alpha/法线/粗糙度/金属度/AO/自发光）。
    * 每个贴图槽位独立模式：**PBR转换**（从 PBR 输入合成通道）、**直接选择**（选择任意图片/DDS/TEX）、**默认空贴图**（写入游戏内空贴图路径）、**不修改**（保持现有路径）。
    * 单通道输入支持通道选择（R/G/B/A）和反相（例如平滑度→粗糙度、绝缘度→金属度）。
    * **GL→DX 法线翻转**：按材质独立开关，G 通道翻转在处理阶段与通道合成一并执行，不需要单独操作。
    * 刷新时自动检测现有空贴图路径并设为"默认空贴图"模式。
    * 支持材质配置的复制/粘贴。
    * 按集合持久化状态——在不同 MDF2 集合间切换时各自独立保留配置。
* **一键创建 RE Chain**: 自动检测链首骨骼（按颜色），弹出集合选择器，随后调用 RE Chain Editor 为每条链自动创建 Chain Settings 和 Chain Group。支持每条链独立 Settings 、全部链共用同一 Settings ，或根据骨骼链名称自动分组并应用参数 三种模式。
* 一键导入并对齐荒野模型
* 优化荒野骨架
* 优化辅助骨骼及权重
* MMD形态键转表情权重
* 一键添加表情骨

#### 怪猎崛起（MHRS）
* 批量导出
* 材质&贴图处理器/生成器
* 一键创建 RE Chain

#### 生化危机4重制版 (RE4R)
* 批量导出工具
    * 支持简化模式：按组绑定集合，无需逐条目配置。
* 材质&贴图处理器/生成器
* 生成假骨骼
* MMD形态键转表情权重
* 一键添加表情骨
* 一键创建 RE Chain

#### 生化危机：镇魂曲 (RE9)
* 批量导出工具
* 同步子级朝向及扭转
* MMD形态键转表情权重
* 一键添加表情骨
* 材质&贴图处理器/生成器
* 一键创建 RE Chain

---

## 安装方法

1. 从 Releases 页面下载 **ZIP** 文件。
2. 在 Blender 中，进入 `编辑 > 首选项 > 插件`。
3. 点击 **安装**，选择 ZIP 文件，启用 **Modding Toolkit**。

---

## 授权协议

本插件源代码以 **GNU GPL v3.0** 授权，见 [`LICENSE`](LICENSE)。

该授权仅覆盖代码及作者自行编写的预设。`assets/` 下随附的游戏文件（参考骨架、空白模板、身体与阴影网格、贴图）版权归株式会社卡普空所有，**不在**本授权范围内；`assets/bin/` 为第三方 MIT 组件。具体范围见 [`NOTICE.md`](NOTICE.md)。


import bpy
import json
import os
import re
from urllib.parse import unquote


def _normalize_bone_name(name):
    """归一化骨骼名：去除分隔符（_ . 空格）并统一小写，用于模糊匹配"""
    return re.sub(r'[_.\s]', '', name).lower()

# --- 1. 标准骨骼定义 (The Standard) ---
STANDARD_BONE_NAMES = [
    # 躯干 (Center)
    "pelvis", "spine_01", "spine_02", "spine_03", "neck", "head",
    
    # 手臂 (Arm) - 左/右
    "clavicle_L", "upperarm_L", "forearm_L", "hand_L",
    "clavicle_R", "upperarm_R", "forearm_R", "hand_R",
    
    # 腿部 (Leg) - 左/右
    "thigh_L", "shin_L", "foot_L", "toe_L",
    "thigh_R", "shin_R", "foot_R", "toe_R",
    
    # 手指 (Fingers) - 左 (Thumb, Index, Middle, Ring, Pinky)
    "thumb_01_L", "thumb_02_L", "thumb_03_L",
    "index_01_L", "index_02_L", "index_03_L",
    "middle_01_L", "middle_02_L", "middle_03_L",
    "ring_01_L",   "ring_02_L",  "ring_03_L",
    "pinky_01_L",  "pinky_02_L", "pinky_03_L",

    # 手指 (Fingers) - 右
    "thumb_01_R", "thumb_02_R", "thumb_03_R",
    "index_01_R", "index_02_R", "index_03_R",
    "middle_01_R", "middle_02_R", "middle_03_R",
    "ring_01_R",   "ring_02_R",  "ring_03_R",
    "pinky_01_R",  "pinky_02_R", "pinky_03_R"
]

class BoneMapManager:
    def __init__(self):
        # 统一后的数据存储
        self.mapping_data = {}      # 存储 JSON 中的 "mappings" 内容
        self.preset_info = {}       # 存储 JSON 中的 "preset_info" 内容
        self.reverse_mapping = {}   # 反向查找表：仅存储每个 Standard Key 对应的第一个 Main Candidate
        self.exclude_bones = set()  # 顶级 "exclude" 字段：不是物理骨，但不属于任何标准骨骼映射

    def get_preset_path(self, filename, is_import_x=False):
        """路径获取"""
        # 当前文件在 core/ 目录下
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 根目录是 core 的上一级
        root_dir = os.path.dirname(current_dir)
        
        sub_folder = os.path.join("presets", "import" if is_import_x else "bone")
        return os.path.join(root_dir, "assets", sub_folder, filename)

    def load_preset(self, filename, is_import_x=False):
        """
        加载预设
        """
        if not filename or filename in ("NONE", "AUTO"):
            return False
        
        real_filename = os.path.basename(unquote(filename))
        filepath = self.get_preset_path(real_filename, is_import_x)
        
        if not os.path.exists(filepath):
            print(f"[Error] Preset file not found: {filepath}")
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.preset_info = data.get("preset_info", {})
            self.mapping_data = data.get("mappings", {})
            self.exclude_bones = set(data.get("exclude", []))

            # 生成反向映射 (主要为了兼容导出逻辑：GameBoneName -> StandardKey)
            # 我们只取 mappings 中每个 standard_key 的 main 列表里的第一个元素作为主键
            self.reverse_mapping = {}
            for std_key, entry in self.mapping_data.items():
                main_list = entry.get("main", [])
                if main_list:
                    primary_game_name = main_list[0]
                    self.reverse_mapping[primary_game_name] = std_key
            
            print(f"[Info] Preset Loaded Successfully: {self.preset_info.get('name')}")
            return True
            
        except Exception as e:
            print(f"[Error] Failed to parse JSON: {e}")
            return False

    def get_matches_for_standard(self, armature_obj, standard_key):
        """
        【抢占式执行核心】
        输入：标准名 (如 'upperarm_L')
        返回：(被选中的主骨名, 需要被合并的辅助骨列表)
        精确匹配优先，失败时归一化模糊匹配（忽略 _ . 空格及大小写）
        """
        if standard_key not in self.mapping_data:
            return None, []

        bone_entry = self.mapping_data[standard_key]
        existing_bones = armature_obj.data.bones.keys()

        # 归一化查找表：{归一化名: 实际骨名}，碰撞时保留第一个
        norm_lookup = {}
        for b in existing_bones:
            norm = _normalize_bone_name(b)
            if norm not in norm_lookup:
                norm_lookup[norm] = b

        def find_bone(name):
            """精确匹配优先，归一化匹配兜底，返回实际骨名"""
            if name in existing_bones:
                return name
            return norm_lookup.get(_normalize_bone_name(name))

        main_candidates = bone_entry.get("main", [])
        aux_candidates = bone_entry.get("aux", [])

        final_main = None
        to_merge = []

        # 1. 查找主骨 (抢占制：列表里第一个匹配的骨骼获胜)
        for cand in main_candidates:
            actual = find_bone(cand)
            if actual:
                if final_main is None:
                    final_main = actual
                else:
                    to_merge.append(actual)

        # 2. 查找辅助骨
        for aux in aux_candidates:
            actual = find_bone(aux)
            if actual and actual != final_main and actual not in to_merge:
                to_merge.append(actual)

        return final_main, to_merge

    # --- 辅助方法 ---
    def get_standard_from_game(self, game_bone_name):
        """输入 MhBone_013 -> 返回 pelvis"""
        return self.reverse_mapping.get(game_bone_name, None)

    def standard_from_any(self, game_bone_name):
        """比 get_standard_from_game 宽：main 的**全部**候选 + aux 都能反查到标准键。
        reverse_mapping 只收每个标准键 main 列表的第一个，够导出用，但跨游戏映射需要
        认出备选主骨和辅助骨（碰撞体就会挂在 aux 上，如 Hip_HJ_00）。"""
        for std_key, entry in self.mapping_data.items():
            if game_bone_name in entry.get("main", ()):
                return std_key
        for std_key, entry in self.mapping_data.items():
            if game_bone_name in entry.get("aux", ()):
                return std_key
        return None


# --- 跨游戏骨名映射（由两份预设经标准键组合而来）---
#
# 51 个标准键在各游戏预设里是同一套，所以「源预设反查 → 标准键 → 目标预设正查」就得到
# 任意游戏对的重命名表，不需要另建映射表。物理链转换与骨架转换**必须共用这一份**，
# 各存一份会漂移成"碰撞体挂错骨"（且 chain 物理只在开局时失败，静态检查看不出来）。

# 预设覆盖 51 个标准槽，槽外的骨它不管。下表补的是**确认存在于真实骨架、但预设里查不到**
# 的骨，值为它应归入的标准键。只收录已验证条目，别凭猜测扩表。
_PRESET_GAP_FILL = {
    # RE4R 脚尖末端，re4.json 只到 L_Toe。RE9 没有 ToesEnd（参考脚本 CORRECTION_DATA
    # 58 条里唯二解析不了的就是这对），跨到 RE9 时必须能收敛到 toe_*。
    "RE4": {"L_ToeEnd": "toe_L", "R_ToeEnd": "toe_R"},
}


class CrossGameBoneMap:
    """源游戏骨名 -> 目标游戏骨名。

    mapping    : {源骨名: 目标骨名}，含恒等项（两边同名时）
    collapsed  : {目标骨名: [塌进它的源骨名…]}，仅列真正多对一的项。
                 多对一意味着**几何上不同的挂点被合并**，碰撞体的局部偏移可能需要补偿
                 （实测 MHWilds L_Knee/L_Shin 塌成一个时残差约 28mm，占胶囊半径约 40%）。
                 补偿量必须从实际源资产上量 —— 方向会随资产翻转，不能建表。
    dropped    : 源侧有、目标侧该标准键无主骨的标准键（目标缺这个槽位）
    """

    def __init__(self, src_game, dst_game):
        self.src_game = src_game
        self.dst_game = dst_game
        self.mapping = {}
        self.collapsed = {}
        self.dropped = []

    def __len__(self):
        return len(self.mapping)

    def get(self, bone_name, default=None):
        """查不到返回 default —— 自带的头发/布料骨走这条路，应当原样透传。"""
        return self.mapping.get(bone_name, default)


def build_cross_game_map(src_preset, dst_preset):
    """组合两份骨骼预设，返回 CrossGameBoneMap。

    src_preset / dst_preset 是 assets/presets/bone/ 下的文件名（如 "mhws.json"）。
    载入失败返回 None。
    """
    src = BoneMapManager()
    dst = BoneMapManager()
    if not src.load_preset(src_preset) or not dst.load_preset(dst_preset):
        return None

    result = CrossGameBoneMap(src.preset_info.get("game_code"),
                              dst.preset_info.get("game_code"))

    src_extra = _PRESET_GAP_FILL.get(result.src_game, {})

    # 源骨名 -> 标准键：main 全部候选 + aux + 补漏表
    src_to_std = {}
    for std_key, entry in src.mapping_data.items():
        for name in entry.get("main", ()):
            src_to_std.setdefault(name, std_key)
    for std_key, entry in src.mapping_data.items():
        for name in entry.get("aux", ()):
            src_to_std.setdefault(name, std_key)
    for name, std_key in src_extra.items():
        src_to_std.setdefault(name, std_key)

    for src_name, std_key in src_to_std.items():
        dst_entry = dst.mapping_data.get(std_key)
        dst_main = (dst_entry or {}).get("main", ())
        if not dst_main:
            if std_key not in result.dropped:
                result.dropped.append(std_key)
            continue

        # 同名骨在目标预设的同一标准键下也存在时保留原名，别无谓塌到主骨上
        # （辅助骨系统各游戏不同名，但偶有共享名，如脚背/掌心一类）
        dst_names = set(dst_main) | set(dst_entry.get("aux", ()))
        result.mapping[src_name] = src_name if src_name in dst_names else dst_main[0]

    for src_name, dst_name in result.mapping.items():
        result.collapsed.setdefault(dst_name, []).append(src_name)
    result.collapsed = {d: sorted(s) for d, s in result.collapsed.items()
                        if len(s) > 1}

    return result


def _list_preset_files(is_import_x):
    """返回预设目录下所有 .json 文件名列表"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    sub_dir = os.path.join("presets", "import" if is_import_x else "bone")
    preset_dir = os.path.join(root_dir, "assets", sub_dir)
    if not os.path.exists(preset_dir):
        return []
    return sorted(f for f in os.listdir(preset_dir) if f.endswith('.json'))


def auto_detect_preset(armature_obj, is_import_x, prefer_game=None):
    """遍历所有预设文件，对每个预设在骨架的 47 个标准骨骼上做匹配测试，
    返回覆盖率最高的文件名。覆盖率 >= 95% 才视为匹配成功，否则返回 None。

    *prefer_game*：并列第一时优先返回该 game_code 的预设。

    ⚠ **并列是真的分不出来，不是判据不够好。** RE4R 与荒野同属一个骨骼约定族，
    标准键覆盖的主链骨骼**名字逐个相同**（见 core/pose_ops.py 的 _RE4R_LIMBS 注释），
    所以两份预设在一具 RE4R 骨架上都是 1.0（实测 cha000_00：re4.json 与 mhws.json
    双双满分）。原先靠文件名排序决定谁赢，于是 RE4 骨架一律被报成"看起来是 MHWS"，
    跨游戏移植的预检直接拦下正确的选择。

    区分它们只能靠标准键之外的信号（RE4R 的 _Twist_s / _Help_ 辅助骨 vs 荒野的
    _HJ_）；在那之前，并列时听调用方的——移植对话框知道用户选的是哪个源游戏，而
    "用户说是 RE4、名字也确实对得上 RE4"没有任何理由报成冲突。
    """
    from .ui_config import OPTIONAL_BONES

    scored = []
    for filename in _list_preset_files(is_import_x):
        mapper = BoneMapManager()
        if not mapper.load_preset(filename, is_import_x):
            continue

        total = 0
        matched = 0
        for std_key in STANDARD_BONE_NAMES:
            if std_key in OPTIONAL_BONES:
                continue
            total += 1
            main, _ = mapper.get_matches_for_standard(armature_obj, std_key)
            if main:
                matched += 1

        if total == 0:
            continue
        scored.append((matched / total, filename,
                       mapper.preset_info.get("game_code")))

    if not scored:
        return None
    best_ratio = max(ratio for ratio, _f, _g in scored)
    if best_ratio < 0.95:
        return None
    # 不能提前 break 在 1.0：那样就看不到并列，而并列正是要处理的情况。
    tied = [(f, g) for ratio, f, g in scored if ratio >= best_ratio - 1e-9]
    if prefer_game:
        for filename, game_code in tied:
            if game_code == prefer_game:
                return filename
    return tied[0][0]


def resolve_preset(preset_value, arm_obj, is_import_x):
    """若 preset_value 为 'AUTO'，则对 arm_obj 执行自动检测并返回匹配的预设文件名。
    返回 (resolved_filename_or_None, error_msg_or_None)。
    非 AUTO 值直接透传；AUTO 检测失败时 resolved 为 None，error_msg 说明原因。"""
    if preset_value != 'AUTO':
        return preset_value, None
    if not arm_obj or arm_obj.type != 'ARMATURE':
        return None, "自动识别需要骨架对象，但未找到可用骨架"
    result = auto_detect_preset(arm_obj, is_import_x)
    if result:
        return result, None
    return None, "自动识别未找到覆盖率 ≥ 95% 的匹配预设，请手动选择预设或新建预设"
import bpy
import json
import os

# --- 1. 标准骨骼定义 (The Standard) ---
STANDARD_BONE_NAMES = [
    # 躯干 (Center)
    "pelvis", "spine_01", "spine_02", "neck", "head",
    
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
        self.reverse_mapping = {}    # 反向查找表：仅存储每个 Standard Key 对应的第一个 Main Candidate

    def get_preset_path(self, filename, is_import_x=False):
        """路径获取"""
        # 当前文件在 core/ 目录下
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 根目录是 core 的上一级
        root_dir = os.path.dirname(current_dir)
        
        # 对应你截图中的文件夹名
        sub_folder = "import_presets" if is_import_x else "bone_presets"
        return os.path.join(root_dir, "assets", sub_folder, filename)

    def load_preset(self, filename, is_import_x=False):
        """
        加载预设
        """
        filepath = self.get_preset_path(filename, is_import_x)
        
        if not os.path.exists(filepath):
            print(f"[Error] Preset file not found: {filepath}")
            return False
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.preset_info = data.get("preset_info", {})
            self.mapping_data = data.get("mappings", {})
            
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
        """
        if standard_key not in self.mapping_data:
            return None, []

        bone_entry = self.mapping_data[standard_key]
        existing_bones = armature_obj.data.bones.keys()
        
        main_candidates = bone_entry.get("main", [])
        aux_candidates = bone_entry.get("aux", [])

        final_main = None
        to_merge = []

        # 1. 查找主骨 (抢占制：列表里第一个在场景中存在的骨骼获胜)
        for cand in main_candidates:
            if cand in existing_bones:
                if final_main is None:
                    final_main = cand
                else:
                    # 如果后续的 Candidate 也存在，它们将被视为辅助骨合并掉
                    to_merge.append(cand)

        # 2. 查找辅助骨 (所有在场景中存在的 Aux 骨骼)
        for aux in aux_candidates:
            if aux in existing_bones:
                if aux != final_main and aux not in to_merge:
                    to_merge.append(aux)

        return final_main, to_merge

    # --- 辅助方法 ---
    def get_standard_from_game(self, game_bone_name):
        """输入 MhBone_013 -> 返回 pelvis"""
        return self.reverse_mapping.get(game_bone_name, None)
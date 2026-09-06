# core/ui_config.py

# 可选骨骼：这些骨骼不是所有游戏都支持，当 Y 预设中不包含时不显示为"缺失"
OPTIONAL_BONES = {
    "spine_03": "可选 | 上胸",
}


# 骨骼显示名：中文名 (英文标准名)
# 未在此表中的骨骼会直接显示英文标准名
BONE_DISPLAY_NAMES = {
    # 躯干
    "pelvis":    "胯部 (pelvis)",
    "spine_01":  "腰腹部 (spine_01)",
    "spine_02":  "胸腔 (spine_02)",
    "spine_03":  "上胸 (spine_03)",
    "neck":      "颈部 (neck)",
    "head":      "头部 (head)",
    # 左臂
    "clavicle_L":  "左肩 (clavicle_L)",
    "upperarm_L":  "左上臂 (upperarm_L)",
    "forearm_L":   "左前臂 (forearm_L)",
    "hand_L":      "左手掌 (hand_L)",
    # 右臂
    "clavicle_R":  "右肩 (clavicle_R)",
    "upperarm_R":  "右上臂 (upperarm_R)",
    "forearm_R":   "右前臂 (forearm_R)",
    "hand_R":      "右手掌 (hand_R)",
    # 左腿
    "thigh_L":  "左大腿 (thigh_L)",
    "shin_L":   "左小腿 (shin_L)",
    "foot_L":   "左脚掌 (foot_L)",
    "toe_L":    "左脚趾 (toe_L)",
    # 右腿
    "thigh_R":  "右大腿 (thigh_R)",
    "shin_R":   "右小腿 (shin_R)",
    "foot_R":   "右脚掌 (foot_R)",
    "toe_R":    "右脚趾 (toe_R)",
    # 左手指
    "thumb_01_L":  "左拇指1", "thumb_02_L":  "左拇指2", "thumb_03_L":  "左拇指3",
    "index_01_L":  "左食指1", "index_02_L":  "左食指2", "index_03_L":  "左食指3",
    "middle_01_L": "左中指1", "middle_02_L": "左中指2", "middle_03_L": "左中指3",
    "ring_01_L":   "左无名指1", "ring_02_L":   "左无名指2", "ring_03_L":   "左无名指3",
    "pinky_01_L":  "左小指1", "pinky_02_L":  "左小指2", "pinky_03_L":  "左小指3",
    # 右手指
    "thumb_01_R":  "右拇指1", "thumb_02_R":  "右拇指2", "thumb_03_R":  "右拇指3",
    "index_01_R":  "右食指1", "index_02_R":  "右食指2", "index_03_R":  "右食指3",
    "middle_01_R": "右中指1", "middle_02_R": "右中指2", "middle_03_R": "右中指3",
    "ring_01_R":   "右无名指1", "ring_02_R":   "右无名指2", "ring_03_R":   "右无名指3",
    "pinky_01_R":  "右小指1", "pinky_02_R":  "右小指2", "pinky_03_R":  "右小指3",
}

# 辅助骨槽位的显示名与"可选"标记。这些键**全部**可选：任何一个没填，行为就退回
# "并进父段主骨"，也就是加槽位之前的样子，所以缺项不是错误，也不该进自动识别的分母
# ——auto_detect_preset 正是靠 OPTIONAL_BONES 把它们排除在打分之外的。
_SEG_CN = {"upperarm": "上臂", "forearm": "前臂", "thigh": "大腿", "shin": "小腿"}
_JOINT_CN = {"palm": "掌骨", "elbow": "肘", "knee": "膝", "instep": "脚背",
             "toe_end": "脚尖末节"}
for _s, _cn in (("L", "左"), ("R", "右")):
    for _seg, _segcn in _SEG_CN.items():
        for _i in range(1, 6):
            _k = "%s_twist_%02d_%s" % (_seg, _i, _s)
            BONE_DISPLAY_NAMES[_k] = "%s%s扭转%d (%s)" % (_cn, _segcn, _i, _k)
            OPTIONAL_BONES[_k] = "可选"
    for _j, _jcn in _JOINT_CN.items():
        _k = "%s_%s" % (_j, _s)
        BONE_DISPLAY_NAMES[_k] = "%s%s (%s)" % (_cn, _jcn, _k)
        OPTIONAL_BONES[_k] = "可选"
del _s, _cn, _seg, _segcn, _i, _k, _j, _jcn


def get_display_name(std_key):
    """获取骨骼的显示名，带可选标记"""
    name = BONE_DISPLAY_NAMES.get(std_key, std_key)
    if std_key in OPTIONAL_BONES:
        name += f"  [{OPTIONAL_BONES[std_key]}]"
    return name

# 分组显示名
UI_HIERARCHY = {
    "躯干和头部": {
        "icon": 'USER',
        "subsections": {
            "脊椎": ["pelvis", "spine_01", "spine_02", "spine_03"],
            "上半身": ["neck", "head"]
        }
    },
    "手臂": {
        "icon": 'ARMATURE_DATA',
        "subsections": {
            "左臂": ["clavicle_L", "upperarm_L", "forearm_L", "hand_L"],
            "右臂": ["clavicle_R", "upperarm_R", "forearm_R", "hand_R"]
        }
    },
    "腿部": {
        "icon": 'MOD_DYNAMICPAINT',
        "subsections": {
            "左腿": ["thigh_L", "shin_L", "foot_L", "toe_L"],
            "右腿": ["thigh_R", "shin_R", "foot_R", "toe_R"]
        }
    },
    "手指 (左)": {
        "icon": 'HAND',
        "subsections": {
            "拇指": ["thumb_01_L", "thumb_02_L", "thumb_03_L"],
            "食指": ["index_01_L", "index_02_L", "index_03_L"],
            "中指": ["middle_01_L", "middle_02_L", "middle_03_L"],
            "无名指": ["ring_01_L", "ring_02_L", "ring_03_L"],
            "小指": ["pinky_01_L", "pinky_02_L", "pinky_03_L"],
        }
    },
    "手指 (右)": {
        "icon": 'HAND',
        "subsections": {
            "拇指": ["thumb_01_R", "thumb_02_R", "thumb_03_R"],
            "食指": ["index_01_R", "index_02_R", "index_03_R"],
            "中指": ["middle_01_R", "middle_02_R", "middle_03_R"],
            "无名指": ["ring_01_R", "ring_02_R", "ring_03_R"],
            "小指": ["pinky_01_R", "pinky_02_R", "pinky_03_R"],
        }
    },
    # 辅助骨：整节全部可选。分左右两个子节，因为编辑预设时人是按一侧填完再镜像的。
    "辅助骨 (左)": {
        "icon": 'CON_SPLINEIK',
        "subsections": {
            "扭转骨": ["%s_twist_%02d_L" % (seg, i)
                       for seg in ("upperarm", "forearm", "thigh", "shin")
                       for i in range(1, 6)],
            "关节": ["palm_L", "elbow_L", "knee_L", "instep_L", "toe_end_L"],
        }
    },
    "辅助骨 (右)": {
        "icon": 'CON_SPLINEIK',
        "subsections": {
            "扭转骨": ["%s_twist_%02d_R" % (seg, i)
                       for seg in ("upperarm", "forearm", "thigh", "shin")
                       for i in range(1, 6)],
            "关节": ["palm_R", "elbow_R", "knee_R", "instep_R", "toe_end_R"],
        }
    },
}

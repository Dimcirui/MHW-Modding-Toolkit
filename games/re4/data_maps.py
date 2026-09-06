# RE4R 的骨名数据表。
#
# 这里曾经还有 MHWI_TO_RE4_MAP / ENDFIELD_TO_RE4_MAP / VRC_TO_RE4_MAP 三张
# "某某 -> RE4" 的骨名对照表，全部**删掉了**，因为它们全仓库无人引用，而躯干部分
# 已经被 core/bone_mapper.py 的标准键系统取代（逐条比对过：VRC 那张 51 条里 50 条
# 与预设一致，MHWI 那张的扭转骨条目还把段骨和扭转骨对调了）。
#
# 唯一换不来的是**面部**——标准键系统不覆盖面部，那些对应是人标的。已存档到
# assets/facial_maps/，见那里的 README。
# ==========================================
# 假骨工具 (FakeBone) 数据
# ==========================================
FAKEBONE_BODY_BONES = [
    "Spine_0", "Spine_1", "Spine_2", "L_Shoulder", "R_Shoulder", 
    "Neck_0", "Neck_1", "Head", "R_Thigh", "L_Thigh", "L_UpperArm", "R_UpperArm"
]

FAKEBONE_BODY_FAKES = [
    "Hip", "Spine_0", "Spine_1", "Spine_2", "L_Shoulder", "R_Shoulder", "Neck_0", "Neck_1"
]

FAKEBONE_BODY_PARENTS = {
    "Hip": ["Spine_0", "R_Thigh", "L_Thigh"],
    "Spine_0": ["Spine_1"], "Spine_1": ["Spine_2"], 
    "Spine_2": ["L_Shoulder", "R_Shoulder", "Neck_0"], 
    "L_Shoulder": ["L_UpperArm"], "R_Shoulder": ["R_UpperArm"], 
    "Neck_0": ["Neck_1"], "Neck_1": ["Head"]
}

FAKEBONE_FINGER_BONES = [
    "R_Hand", "R_Thumb1", "R_Thumb2", "R_Thumb3", "R_IndexF1", "R_IndexF2", "R_IndexF3",
    "R_MiddleF1", "R_MiddleF2", "R_MiddleF3", "R_Palm", "R_RingF1", "R_RingF2", "R_RingF3",
    "R_PinkyF1", "R_PinkyF2", "R_PinkyF3", "L_Hand", "L_Thumb1", "L_Thumb2", "L_Thumb3", 
    "L_IndexF1", "L_IndexF2", "L_IndexF3", "L_MiddleF1", "L_MiddleF2", "L_MiddleF3",
    "L_Palm", "L_RingF1", "L_RingF2", "L_RingF3", "L_PinkyF1", "L_PinkyF2", "L_PinkyF3"
]

FAKEBONE_FINGER_MERGE_MAP = {
    "L_Wep": "L_Hand_end", "L_IndexF1": "L_Hand_endI", "L_MiddleF1": "L_Hand_endM",
    "L_Palm": "L_Hand_endP", "L_Thumb1": "L_Hand_endT", "L_PinkyF1": "L_Palm_endP",
    "L_RingF1": "L_Palm_endR", "R_Wep": "R_Hand_end", "R_IndexF1": "R_Hand_endI",
    "R_MiddleF1": "R_Hand_endM", "R_Palm": "R_Hand_endP", "R_Thumb1": "R_Hand_endT",
    "R_PinkyF1": "R_Palm_endP", "R_RingF1": "R_Palm_endR",
}

FAKEBONE_FINGER_PATTERNS = [
    ("L_IndexF", 3), ("L_MiddleF", 3), ("L_RingF", 3), ("L_PinkyF", 3), ("L_Thumb", 3),
    ("R_IndexF", 3), ("R_MiddleF", 3), ("R_RingF", 3), ("R_PinkyF", 3), ("R_Thumb", 3),
]

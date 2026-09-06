"""core/twist_chain.py — 扭转骨链的识别、定位与跨游戏重采样。

为什么不是一张名字表
--------------------
原先 ``bone_mapper._re4_re9_twists()`` 用固定骨名把 RE4 的扭转骨映射到 RE9。实测
三具自带 RE4 参考骨架后发现名字**逐角色不同**：同一根小腿扭转骨，ada 叫
``L_Toe_Twist_s``（名字里的 Toe 是误导，它量出来在小腿中段）、ashley 叫
``L_Foot_Twist_s0``、leon 叫 ``L_Shin_Twist_s``；大腿那根 ada/ashley 是
``L_Thigh_Twist_s1`` 而 leon 是 ``L_Thigh_Twist_s``。那张表用的是 leon 的名字，
对另外两具静默失效。位置同样逐角色不同（leon 的上臂扭转在 0.43/0.79，ada 与 ashley
在精确的 1/3、2/3）。

所以这里只用**结构**：某段的后代、落在段轴上、按归一化位置 ``t`` 排序。名字一个不存。

t 与滚转系数
------------
``t`` = 骨头部沿"段首关节 -> 段尾关节"方向的归一化投影，0 在父端、1 在子端。三个游戏
的序号方向一致（实测 RE9 ``Twist_0..3`` = 0/1/3/2/3/1，RE4 ``s1/s2/Wrist`` = 1/3/2/3/1，
MHWS ``HJ_00..02`` 递增）。

滚转系数按 *role* 取，两者都是 t 的线性函数——这正是重采样能做到精确的原因：

- ``inherit``（前臂、小腿）：滚转来自子关节（腕/踝），``c(t) = t``。段骨自己不滚。
- ``cancel``（上臂、大腿）：段骨自己在球窝里滚，贴躯干的皮肤不能跟，
  ``c(t) = t - 1``（相对段骨），即父端 -1 完全抵消、子端 0 完全跟随。

role 是**每段一个值**，且有解剖学理由（肱骨/股骨在肩/髋处自转，桡尺骨/胫腓骨不在肘/膝
处自转、滚转由腕/踝传入），实测 MHWS 与 RE9 的 jcns 六格全部符合，所以它按游戏×段写死
在预设里即可，不随角色变。

几何不足以判定"是不是扭转骨"
----------------------------
实测 MHWilds_Female：``L_Biceps_HJ_00``（t=0.538）、``L_Elbow_HJ_00``（t=0.996）、
``L_Shin_HJ_01``（t=0.641）三根垂距都是 0，全部通过"在段轴上"的检验，但都不是扭转骨
（jcns 里 MHWS 小腿根本没有扭转约束）。所以 :func:`candidates` 只负责**提出候选并算 t**，
判定要靠 jcns、名字 token 或预设记录的人工结论。
"""

#: 垂距阈值：占段长的比例。实测所有真扭转骨的垂距是 0.0 mm，肌肉助推骨从 10 mm
#: (L_Biceps_HJ_01) 到 90 mm (L_Calf_HJ_00) 不等，所以这个阈值只是防浮点噪声。
PERP_EPS = 0.02

#: t 落在这个距离内视为同一位置，直接改名而不做分配。留一点余量是因为两侧骨架的
#: 比例不同，同一设计位置量出来会差千分之几；但阈值不能大，否则会把真的错位当成同位。
SAME_T = 0.02


def normalized_position(head, seg_head, seg_tail):
    """返回 (t, perp)：*head* 沿段轴的归一化投影，以及到轴的垂直距离。

    三个参数都是可索引的三元组（``mathutils.Vector`` 或 tuple 均可）。
    """
    d = tuple(seg_tail[i] - seg_head[i] for i in range(3))
    v = tuple(head[i] - seg_head[i] for i in range(3))
    ll = sum(c * c for c in d)
    if ll == 0.0:
        return 0.0, 0.0
    t = sum(v[i] * d[i] for i in range(3)) / ll
    perp = sum((v[i] - d[i] * t) ** 2 for i in range(3)) ** 0.5
    return t, perp


def candidates(bones, seg_head, seg_tail):
    """从 *bones* 里挑出落在段轴上的候选，返回按 t 升序的 ``[(name, t), ...]``。

    *bones* 是 ``[(name, head_xyz), ...]``，调用方负责只传该段的后代（用父子关系筛，
    **不要**用投影筛：``L_Arm_Lower_Twist_0`` 在上臂段上投影出 t=1.0，因为它就在肘部，
    即上臂的子关节——按投影归属会一骨两属）。

    返回的是**候选**，不是判定结果。见模块文档。
    """
    length = sum((seg_tail[i] - seg_head[i]) ** 2 for i in range(3)) ** 0.5
    out = []
    for name, head in bones:
        t, perp = normalized_position(head, seg_head, seg_tail)
        if -PERP_EPS <= t <= 1.0 + PERP_EPS and perp <= PERP_EPS * length:
            out.append((name, t))
    out.sort(key=lambda r: r[1])
    return out


def coefficient(t, role):
    """滚转系数：inherit 为 t，cancel 为 t-1。见模块文档。"""
    if role == "inherit":
        return t
    if role == "cancel":
        return t - 1.0
    raise ValueError("role must be 'inherit' or 'cancel', got %r" % (role,))


def _augment(members, role, seg_bone, child_bone):
    """给目标链补虚拟端点，使任何源位置都必然落在某个区间内。

    端点由 role 决定，两者都不是新造的骨，而是**本来就承担该角色的骨**：

    - inherit：t=0 的"不滚"由段骨自己承担（前臂不自转），t=1 的"全滚"由子关节骨承担
      （腕/踝就是滚转源）。
    - cancel：t=1 的"全滚"由段骨自己承担。**t=0 没有替身**——"完全不跟着滚"在目标侧
      缺失时无法用任何现有骨代替，只能钳位并报残差。
    """
    aug = list(members)
    have = lambda tt: any(abs(t - tt) < SAME_T for _n, t in members)
    if role == "inherit":
        if not have(0.0) and seg_bone:
            aug.append((seg_bone, 0.0))
        if not have(1.0) and child_bone:
            aug.append((child_bone, 1.0))
    else:
        if not have(1.0) and seg_bone:
            aug.append((seg_bone, 1.0))
    aug.sort(key=lambda r: r[1])
    return aug


def build_transfer(src_members, dst_members, role,
                   dst_seg_bone=None, dst_child_bone=None):
    """把源链重采样到目标链，返回 ``(transfer, report)``。

    ``transfer`` : ``{源骨名: [(目标骨名, 系数), ...]}``，每行系数和为 1（权重守恒，
                   逐顶点总权重不变，因此**不需要重新归一化**）。
    ``report``   : 诊断，见下面各键的说明。

    规则是"区间 + 线性分配"：源骨位于目标链的哪两根之间，权重就按距离线性分给这两根。
    因为 :func:`coefficient` 是 t 的线性函数，这样分配能**精确复现**源骨原本的滚转量，
    不是近似——``report["fidelity"]`` 就是这一点的残差，正常为 0（浮点级）。

    ``report["snap_error"]`` 是另一回事：同位改名会把源骨吸附到最近的目标位置，代价是
    最多 ``SAME_T`` 的滚转差。两者必须分开看，否则"分配精确"这条主张会被吸附误差淹没。

    等分数相同时 α 退化为 0/1，自动变成普通改名，不走额外路径。
    """
    aug = _augment(dst_members, role, dst_seg_bone, dst_child_bone)
    transfer = {}
    clamped = []
    exact = []      # 走区间分配的行：残差必须是 0，那是本模块的数学主张
    snapped = []    # 走同位改名的行：残差就是吸附掉的那点 t 差，上限 SAME_T

    if not aug:
        return {}, {"error": "target chain is empty", "conserved": 0.0,
                    "fidelity": 0.0, "clamped": [], "inverted": []}

    lo_name, lo_t = aug[0]
    hi_name, hi_t = aug[-1]

    for name, t in src_members:
        if t < lo_t - SAME_T or t > hi_t + SAME_T:
            # 目标侧没有能覆盖这个位置的骨。钳到最近端，并报出残余滚转——
            # 4 根链降到 1 根时低 t 端必然走到这里，那是真丢信息，不该静默。
            tgt, tgt_t = (lo_name, lo_t) if t < lo_t else (hi_name, hi_t)
            transfer[name] = [(tgt, 1.0)]
            clamped.append({"bone": name, "t": round(t, 4),
                            "landed_t": round(tgt_t, 4),
                            "roll_residual": round(
                                coefficient(tgt_t, role) - coefficient(t, role), 4)})
            continue       # 已单列在 clamped 里，不混进保真度统计

        # 同位：直接改名，避免引入一个千分位的第二权重把顶点组撑肥
        hit = min(aug, key=lambda r: abs(r[1] - t))
        if abs(hit[1] - t) < SAME_T:
            transfer[name] = [(hit[0], 1.0)]
            snapped.append(abs(coefficient(hit[1], role) - coefficient(t, role)))
            continue

        a = max((r for r in aug if r[1] <= t), key=lambda r: r[1])
        b = min((r for r in aug if r[1] >= t), key=lambda r: r[1])
        span = b[1] - a[1]
        alpha = 0.0 if span == 0 else (t - a[1]) / span
        alpha = min(1.0, max(0.0, alpha))
        transfer[name] = [(a[0], 1.0 - alpha), (b[0], alpha)]
        got = (1.0 - alpha) * coefficient(a[1], role) + alpha * coefficient(b[1], role)
        exact.append(abs(got - coefficient(t, role)))

    conserved = max((abs(sum(f for _n, f in rows) - 1.0)
                     for rows in transfer.values()), default=0.0)

    # 顺序反转检查：源链按 t 升序，落点也必须非递减。反转意味着两根骨换了位置，
    # 皮肤会拧成麻花，而且是静态看不出来的那类错误。
    landed, inverted = [], []
    for name, t in src_members:
        rows = transfer.get(name) or []
        if rows:
            landed.append((name, max(dict(aug).get(n, 0.0) for n, _f in rows)))
    for (n0, t0), (n1, t1) in zip(landed, landed[1:]):
        if t1 < t0 - 1e-9:
            inverted.append((n0, n1))

    return transfer, {
        "conserved": conserved,
        # 分配的滚转保真度残差。因为 coefficient() 是 t 的线性函数，区间线性分配能
        # **精确**复现源骨的滚转量，所以这个值应当是 0（浮点级）。它不为 0 就说明
        # 分配逻辑本身出了偏差 —— 这是"会不会过矫"的判据。
        "fidelity": max(exact) if exact else 0.0,
        # 同位改名把源骨吸附到相邻目标位置所丢掉的那点滚转，上限是 SAME_T。
        # 它跟过矫无关，是为了不给顶点组塞一个千分位的第二权重而故意付的代价。
        "snap_error": max(snapped) if snapped else 0.0,
        "clamped": clamped,
        "inverted": inverted,
        "virtual_endpoints": [n for n, _t in aug if n not in dict(dst_members)],
    }


def apply_to_weights(get_weight, set_weight, transfer, vertex_ids):
    """把 *transfer* 施加到顶点权重上。

    调用方提供 ``get_weight(group_name, vid) -> float`` 与
    ``set_weight(group_name, vid, w)``，本函数不碰 bpy，便于离线测试。

    逐顶点总权重不变，所以**不做归一化**。源组由调用方在之后删除——分配本身不删，
    是为了让"跑两遍"这件事可检测（源组还在 = 还没完成），而不是悄悄把权重加倍。
    """
    for src_name, rows in transfer.items():
        for vid in vertex_ids:
            w = get_weight(src_name, vid)
            if not w:
                continue
            for dst_name, factor in rows:
                if factor:
                    set_weight(dst_name, vid, get_weight(dst_name, vid) + w * factor)


# ---------------------------------------------------------------------------
# 整具骨架的规划
# ---------------------------------------------------------------------------

#: 四个带扭转链的肢体段，以及各段的首尾标准键。``{s}`` 展开为 L / R。
#:
#: 段的端点骨名**从预设里取**，不另建表——``upperarm_L`` 的 main 就是该游戏的上臂骨。
#: 于是"哪一段"这件事是游戏无关的，"叫什么"由预设回答，两边都不需要新字段。
SEGMENTS = (
    ("upperarm", "upperarm_{s}", "forearm_{s}"),
    ("forearm",  "forearm_{s}",  "hand_{s}"),
    ("thigh",    "thigh_{s}",    "shin_{s}"),
    ("shin",     "shin_{s}",     "foot_{s}"),
)

#: 每段的滚转机制。**不是每游戏一份**：实测 MHWS 与 RE9 的 jcns 六格全部符合
#: "近端段抵消自身、远端段继承末端"，而这条有解剖学理由（肱骨/股骨在肩/髋的球窝里
#: 自转，所以贴躯干的皮肤不能跟；桡尺骨/胫腓骨在肘/膝处不自转，滚转由腕/踝传入，
#: 所以皮肤必须跟）。因此它是常量，不进预设。
SEGMENT_ROLE = {"upperarm": "cancel", "forearm": "inherit",
                "thigh": "cancel", "shin": "inherit"}

#: 名字兜底判据。几何只能判"在不在段轴上"，判不出"是不是扭转骨"——实测荒野的
#: ``L_Biceps_HJ_00`` / ``L_Elbow_HJ_00`` / ``L_Shin_HJ_01`` 垂距都是 0 却都不是扭转骨。
#: 有 jcns 时以 jcns 为准（源轴==目标轴==该段滚转轴），没有时靠这几个词根。
#: ``_T`` / ``_W`` 是老 RE Engine（DMC5/MHWR）的写法，只在结尾成立。
_TWIST_TOKENS = ("twist", "roll", "捩")

#: 名字里带 twist 但**不是**变形扭转骨的两类，实测于八具 VRChat 头像骨架：
#:
#: - ``*_end`` / ``*先``：Blender / MMD 导入产生的末端骨，无权重。八具里
#:   ``Twist elbow_L_end`` 与 ``Twist wrist_L_end`` 就落在 t=1.12 / 1.09，
#:   即已经越过子关节。
#: - ``cloth``：布料专用的伴生扭转骨。``Upper_arm_Cloth_Twist_L`` 与
#:   ``Upper_arm_Twist_L`` 同处 t=0.998，两根同位，一根管皮肤一根管布料；
#:   把布料那根也当扭转链成员会让同一位置出现两个链节。
_NOT_TWIST_TOKENS = ("cloth",)


def is_twist_name(name):
    """名字兜底判据。**不是**权威——见 :data:`_TWIST_TOKENS` 的说明。"""
    low = name.lower()
    if name.endswith("_end") or name.endswith("先"):
        return False
    if any(tok in low for tok in _NOT_TWIST_TOKENS):
        return False
    if any(tok in low for tok in _TWIST_TOKENS):
        return True
    return name.endswith("_T") or name.endswith("_W")


def chain_for_segment(positions, parents, seg_head, seg_tail, name_filter=is_twist_name):
    """返回该段的扭转链 ``[(name, t), ...]``，按 t 升序。

    *positions* : ``{骨名: (x, y, z)}``，头部世界坐标。
    *parents*   : ``{骨名: 父骨名或 None}``。
    *name_filter*: 传 ``None`` 表示不做名字过滤，只按几何取候选（用于"先看看有什么"）。

    归属**按父子关系**确定：从 *seg_head* 向下遍历，但不进入 *seg_tail* 那条分支。
    这一点不能用投影代替——``L_Arm_Lower_Twist_0`` 在上臂段上投影出 t=1.0，因为它就在
    肘部，即上臂的子关节；按投影归属会一骨两属。
    """
    if seg_head not in positions or seg_tail not in positions:
        return []

    children = {}
    for name, par in parents.items():
        if par:
            children.setdefault(par, []).append(name)

    desc = []
    stack = list(children.get(seg_head, ()))
    while stack:
        name = stack.pop()
        if name == seg_tail:
            continue                      # 主链分支整枝不进
        if name in positions:
            desc.append((name, positions[name]))
        stack.extend(children.get(name, ()))

    if name_filter is not None:
        desc = [(n, p) for n, p in desc if name_filter(n)]
    return candidates(desc, positions[seg_head], positions[seg_tail])


def segments_from_presets(src_mapper, dst_mapper, sides=("L", "R")):
    """由两份骨骼预设推出各段的端点骨名。

    参数是任何带 ``mapping_data`` 的对象（``BoneMapManager`` 即可），所以本模块不必
    import bone_mapper，也就不必 import bpy。

    返回 ``[(label, (src_head, src_tail), (dst_head, dst_tail), role), ...]``；
    任一侧缺端点的段直接跳过——缺了就没有段，谈不上链。
    """
    def main_of(mapper, std_key):
        entry = (mapper.mapping_data or {}).get(std_key) or {}
        mains = entry.get("main") or ()
        return mains[0] if mains else None

    out = []
    for seg, head_key, tail_key in SEGMENTS:
        for s in sides:
            sh = main_of(src_mapper, head_key.format(s=s))
            st = main_of(src_mapper, tail_key.format(s=s))
            dh = main_of(dst_mapper, head_key.format(s=s))
            dt = main_of(dst_mapper, tail_key.format(s=s))
            if not all((sh, st, dh, dt)):
                continue
            out.append(("%s_%s" % (seg, s), (sh, st), (dh, dt), SEGMENT_ROLE[seg]))
    return out


def plan_transfers(src_rig, dst_rig, segments, name_filter=is_twist_name):
    """对整具骨架规划扭转链转移。

    *src_rig* / *dst_rig* : ``{"positions": {...}, "parents": {...}}``。
    *segments*            : :func:`segments_from_presets` 的返回值。

    返回 ``(transfer, reports)``：

    ``transfer`` : ``{源骨名: [(目标骨名, 系数), ...]}``，可直接喂
                   :func:`apply_to_weights`。单项且系数为 1 的行就是普通改名，
                   调用方可以把它们降级成 rename 而不必走权重分配。
    ``reports``  : ``{段标签: 诊断}``，只收录真有链的段。诊断里的 ``clamped``
                   是降级丢信息的地方，必须报给用户，不能静默。
    """
    transfer = {}
    reports = {}
    for label, (sh, st), (dh, dt), role in segments:
        src_chain = chain_for_segment(src_rig["positions"], src_rig["parents"],
                                      sh, st, name_filter)
        if not src_chain:
            continue
        dst_chain = chain_for_segment(dst_rig["positions"], dst_rig["parents"],
                                      dh, dt, name_filter)
        rows, rep = build_transfer(src_chain, dst_chain, role,
                                   dst_seg_bone=dh, dst_child_bone=dt)
        if not rows:
            continue
        transfer.update(rows)
        rep["segment"] = label
        rep["src_chain"] = src_chain
        rep["dst_chain"] = dst_chain
        reports[label] = rep
    return transfer, reports


#: 标准化路径用的扭转槽位键模板。序号上限与 ``bone_mapper.AUX_BONE_NAMES`` 一致；
#: 这里不 import bone_mapper（它顶层 import bpy，本模块要能脱离 Blender 加载），
#: 由 ``tests/test_twist_chain.py`` 的一条断言盯住两者不漂移。
MAX_TWIST_ORDINAL = 5


def twist_slot_keys(segment, side, max_ordinal=MAX_TWIST_ORDINAL):
    return ["%s_twist_%02d_%s" % (segment, i, side)
            for i in range(1, max_ordinal + 1)]


def plan_slot_resample(std_to_bone, positions, kept_slots, sides=("L", "R"),
                       max_ordinal=MAX_TWIST_ORDINAL):
    """标准化路径的重采样：目标游戏装不下的扭转槽，按位置分给**留下来的那几根**。

    这条路和跨游戏移植不同的地方在于：目标侧的扭转骨就是源骨架自己那几根（改个名而已），
    所以两边的坐标都在场景里，不需要参考骨架，也不需要假设"等分"。实测 leon 的上臂
    扭转在 0.43/0.79 而不是 1/3、2/3 —— 等分假设本来就是错的，这里不做这个假设。

    参数
    ----
    std_to_bone : ``{标准键: 骨架上的实际骨名}``，需覆盖段首尾键与扭转槽位键。
    positions   : ``{实际骨名: (x, y, z)}``，骨头的 head。
    kept_slots  : 目标预设**叫得出名字**的槽位键集合；不在其中的就是要被分掉的。

    返回 ``(splits, reports)``：

    ``splits``  : ``[(源骨名, [(目标骨名, 系数), ...]), ...]``，只含要被分掉的骨，
                  可直接喂 ``weight_utils.distribute_and_remove``。
    ``reports`` : ``{段标签: 诊断}``，键与 :func:`build_transfer` 的 report 相同，
                  外加 ``dropped`` / ``kept``。``no_target`` 表示整段一根都不剩，
                  调用方应退回"并进段骨"的老路 —— 那不是这里能修的。
    """
    splits, reports = [], {}
    for seg, head_tpl, tail_tpl in SEGMENTS:
        for side in sides:
            head_key, tail_key = head_tpl.format(s=side), tail_tpl.format(s=side)
            head_bone = std_to_bone.get(head_key)
            tail_bone = std_to_bone.get(tail_key)
            if not head_bone or not tail_bone:
                continue
            if head_bone not in positions or tail_bone not in positions:
                continue
            seg_head, seg_tail = positions[head_bone], positions[tail_bone]

            members = []
            for key in twist_slot_keys(seg, side, max_ordinal):
                bone = std_to_bone.get(key)
                if not bone or bone not in positions:
                    continue
                t, _perp = normalized_position(positions[bone], seg_head, seg_tail)
                members.append((key, bone, t))
            if not members:
                continue
            members.sort(key=lambda r: r[2])

            dropped = [m for m in members if m[0] not in kept_slots]
            if not dropped:
                continue                      # 全都装得下，改名即可
            kept = [m for m in members if m[0] in kept_slots]
            label = "%s_%s" % (seg, side)
            if not kept:
                # 一根都不剩：分配没有落点，只能退回并进段骨。这不是钳位，是没有链。
                reports[label] = {"no_target": True,
                                  "dropped": [m[0] for m in dropped], "kept": []}
                continue

            role = SEGMENT_ROLE[seg]
            transfer, rep = build_transfer(
                [(b, t) for _k, b, t in members],
                [(b, t) for _k, b, t in kept],
                role, dst_seg_bone=head_bone, dst_child_bone=tail_bone)
            drop_bones = {b for _k, b, _t in dropped}
            rows = [(b, transfer[b]) for _k, b, _t in dropped if transfer.get(b)]
            # 落点不能是另一根同样要被删掉的骨 —— 那等于把权重扔进垃圾桶。
            for src, targets in rows:
                bad = [n for n, _f in targets if n in drop_bones]
                assert not bad, (src, bad)
            splits += rows
            rep["dropped"] = [m[0] for m in dropped]
            rep["kept"] = [m[0] for m in kept]
            reports[label] = rep
    return splits, reports

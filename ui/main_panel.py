import bpy
from ..core import bone_utils, weight_utils, ui_config
from ..core.bone_utils import get_import_presets_callback, get_target_presets_callback
from ..core.bone_mapper import BoneMapManager

mapper = BoneMapManager()
class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    # 顶部开关
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=True)
    show_mhws: bpy.props.BoolProperty(name="Wilds", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    
    # 通用转换器开关
    show_std_converter: bpy.props.BoolProperty(name="通用骨架转换", default=True)

    # 预设选择 (X/Y)
    import_preset_enum: bpy.props.EnumProperty(
        name="来源预设 (X)",
        description="选择导入模型的骨架结构",
        items=get_import_presets_callback
    )
    
    target_preset_enum: bpy.props.EnumProperty(
        name="目标游戏 (Y)",
        description="选择要导出的目标游戏",
        items=get_target_presets_callback
    )
    
    show_mapping_details: bpy.props.BoolProperty(name="显示映射细节", default=False)

class MHW_OT_GeneralTools(bpy.types.Operator):
    """通用工具集合"""
    bl_idname = "mhw.general_tools"
    bl_label = "通用工具"
    bl_options = {'REGISTER', 'UNDO'}
    
    action: bpy.props.EnumProperty(
        items=[
            ('ROLL_ZERO', "扭转归零", "递归将选中骨骼的 Roll 设为 0"),
            ('ADD_TAIL', "添加尾骨", "在选中骨骼末端添加垂直骨骼"),
            ('MIRROR_X', "镜像对齐 X", "以 X+ 为基准镜像对齐 X- 骨骼"),
            ('SIMPLIFY_CHAIN', "骨链简化", "隔一个删一个并合并权重"),
        ]
    )

    def execute(self, context):
        arm_obj = context.active_object
        if not arm_obj or arm_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "请先选中一个骨架")
            return {'CANCELLED'}

        # =========================================
        # 功能 A: 扭转归零 (Roll = 0)
        # =========================================
        if self.action == 'ROLL_ZERO':
            bpy.ops.object.mode_set(mode='EDIT')
            # 获取用户手动选中的骨骼作为“根”
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, "请在编辑模式下至少选中一根骨骼")
                return {'CANCELLED'}
            
            # 调用核心逻辑
            count = bone_utils.set_roll_to_zero_recursive(selected_bones)
            self.report({'INFO'}, f"已重置 {count} 根骨骼的 Roll")

        # =========================================
        # 功能 B: 添加尾骨
        # =========================================
        elif self.action == 'ADD_TAIL':
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            # 同样获取选中的骨骼
            selected_bones = context.selected_editable_bones
            if not selected_bones:
                self.report({'WARNING'}, "请选中需要加尾巴的骨骼")
                return {'CANCELLED'}
            
            # 调用核心逻辑
            count = bone_utils.add_vertical_tail_bone(edit_bones, selected_bones)
            self.report({'INFO'}, f"添加了 {count} 根尾骨")
            # 刷新视图
            bpy.ops.object.mode_set(mode='POSE') 
            bpy.ops.object.mode_set(mode='EDIT')

        # =========================================
        # 功能 C: 镜像对齐 X
        # =========================================
        elif self.action == 'MIRROR_X':
            # 原始脚本是在 Pose 模式下选骨骼
            # 为了方便用户，我们允许在 Pose 或 Edit 模式下选，然后脚本切到 Edit 模式改坐标
            
            # 1. 收集选中的骨骼名字
            selected_names = []
            if context.mode == 'POSE':
                selected_names = [b.name for b in context.selected_pose_bones]
            elif context.mode == 'EDIT':
                selected_names = [b.name for b in context.selected_editable_bones]
            else:
                selected_names = [b.name for b in arm_obj.data.bones if b.select]

            if len(selected_names) != 2:
                self.report({'ERROR'}, "请正好选中两个骨骼进行镜像对齐")
                return {'CANCELLED'}

            # 2. 切换到编辑模式进行修改
            bpy.ops.object.mode_set(mode='EDIT')
            edit_bones = arm_obj.data.edit_bones
            
            # 调用核心逻辑
            success, msg = bone_utils.mirror_bone_transform(edit_bones, selected_names)
            
            if success:
                self.report({'INFO'}, msg)
            else:
                self.report({'ERROR'}, msg)

        # =========================================
        # 功能 D: 骨链简化 (权重合并)
        # =========================================
        elif self.action == 'SIMPLIFY_CHAIN':
            # 1. 收集选中骨骼，注意顺序
            # 最好在编辑模式下，或者物体模式下有选中状态
            if context.mode != 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
            
            # 获取选中骨骼并按层级/顺序排列 (Blender 默认 selected_editable_bones 不保证顺序，
            # 但通常用户是按顺序选的。为了稳妥，我们按骨骼列表里的顺序过滤)
            all_bone_names = [b.name for b in arm_obj.data.edit_bones]
            selected_names = [b.name for b in context.selected_editable_bones]
            
            # 简单的排序策略：按照它们在骨架中的出现顺序（通常也是层级顺序）
            # 或者保留用户的点击顺序（需要更复杂的逻辑，这里暂时按原有脚本逻辑简化）
            sorted_selection = [name for name in all_bone_names if name in selected_names]
            
            if len(sorted_selection) < 2:
                self.report({'ERROR'}, "至少需要选中两个骨骼")
                return {'CANCELLED'}
            
            # 2. 配对 (保留, 删除)
            # 逻辑：隔一个删一个
            pairs = []
            delete_every_n = 2
            for i in range(0, len(sorted_selection) - 1, delete_every_n):
                keep = sorted_selection[i]
                delete = sorted_selection[i+1]
                pairs.append((keep, delete))
            
            print(f"待处理骨骼对: {pairs}")
            
            # 3. 切回物体模式以处理权重 (Vertex Groups 操作需要在 Object Mode)
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # 调用核心逻辑
            weight_utils.merge_weights_and_delete_bones(arm_obj, pairs)
            
            self.report({'INFO'}, f"骨链简化完成，合并了 {len(pairs)} 对骨骼")

        return {'FINISHED'}
class MHW_PT_MainPanel(bpy.types.Panel):
    bl_label = "MOD Toolkit"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MOD Toolkit'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        arm_obj = context.active_object
        
        # =========================================
        # 1. 顶部开关区域
        # =========================================
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="Wilds")
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        
        layout.separator()

        # =========================================
        # 2. 通用基础工具 (General Tools)
        # =========================================
        box = layout.box()
        box.label(text="基础工具 (Basic)", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        col.operator("mhw.general_tools", text="扭转归零 (Roll=0)").action = 'ROLL_ZERO'
        
        row = col.row(align=True)
        row.operator("mhw.general_tools", text="添加尾骨").action = 'ADD_TAIL'
        row.operator("mhw.general_tools", text="镜像对齐 X").action = 'MIRROR_X'
        col.operator("mhw.general_tools", text="骨链简化 (隔1删1)").action = 'SIMPLIFY_CHAIN'

        layout.separator()

        # =========================================
        # 3. 通用骨架转换系统 (Standard Converter)
        # =========================================
        main_box = layout.box()
        row = main_box.row()
        row.prop(settings, "show_std_converter", 
                 icon="TRIA_DOWN" if settings.show_std_converter else "TRIA_RIGHT", 
                 icon_only=True, emboss=False)
        row.label(text="通用标准转换 (Standard Converter)", icon='ARMATURE_DATA')

        if settings.show_std_converter:
            col = main_box.column(align=True)
            col.prop(settings, "import_preset_enum", icon='IMPORT')
            col.prop(settings, "target_preset_enum", icon='EXPORT')
            
            col.separator()
            # col.label(text="核心流程 (按顺序):")
            
            row = col.row(align=True)
            row.operator("modder.universal_snap", text="对齐骨骼", icon='SNAP_ON')
            
            row = col.row(align=True)
            row.scale_y = 1.2
            row.operator("modder.direct_convert", text="重命名顶点组", icon='MOD_VERTEX_WEIGHT')
            # row.operator("modder.apply_standard_x", text="1. 标准化 (X)", icon='MOD_VERTEX_WEIGHT')
            # row.operator("modder.apply_standard_y", text="2. 游戏化 (Y)", icon='SORTALPHA')
            
            # 映射详情预览
            col.separator()
            row = col.row()
            row.prop(settings, "show_mapping_details", 
                     icon='TRIA_DOWN' if settings.show_mapping_details else 'TRIA_RIGHT', 
                     emboss=False)
            
            if settings.show_mapping_details:
                if arm_obj and arm_obj.type == 'ARMATURE':
                    # 加载预设进行 UI 反馈
                    mapper.load_preset(settings.import_preset_enum, is_import_x=True)
                    
                    # 绘制三级结构
                    preview_box = col.box()
                    for group_name, group_data in ui_config.UI_HIERARCHY.items():
                        g_box = preview_box.box()
                        g_box.label(text=group_name, icon=group_data['icon'])
                        
                        for sub_name, bones in group_data['subsections'].items():
                            sub_col = g_box.column(align=True)
                            sub_col.label(text=sub_name)
                            
                            for std_key in bones:
                                main_bone, aux_list = mapper.get_matches_for_standard(arm_obj, std_key)
                                m_row = sub_col.row(align=True)
                                m_row.label(text=f"  {std_key}")
                                
                                if main_bone:
                                    status = f"{main_bone}"
                                    if aux_list: status += f" (+{len(aux_list)})"
                                    m_row.label(text=status, icon='CHECKMARK')
                                else:
                                    m_row.label(text="缺失", icon='CANCEL')
                else:
                    col.label(text="请选中骨架以预览", icon='INFO')

        layout.separator()

        # =========================================
        # 4. 游戏专用工具栏 (Game Specific)
        # =========================================
        
        # --- MHWI ---
        if settings.show_mhwi:
            box = layout.box()
            box.label(text="MHWI Tools", icon='ARMATURE_DATA')
            col = box.column(align=True)
            col.operator("mhwi.align_non_physics", text="对齐非物理骨骼", icon='BONE_DATA')

        # --- MHW Wilds ---
        if settings.show_mhws:
            box = layout.box()
            box.label(text="MHWilds Tools", icon='WORLD')
            box.operator("mhwilds.tpose_convert", text="转为 MHWI T-Pose", icon='ARMATURE_DATA')
             
        # --- RE4 ---
        if settings.show_re4:
            box = layout.box()
            box.label(text="RE4 Tools", icon='GHOST_ENABLED')

            box_fake = layout.box()
            box_fake.label(text="假骨与对齐 (FakeBone)", icon='BONE_DATA')
            col_fake = box_fake.column(align=True)
            col_fake.label(text="1. 创建 End 骨骼:")
            row1 = col_fake.row(align=True)
            row1.operator("re4.fake_body_process", text="身体", icon='ARMATURE_DATA')
            row1.operator("re4.fake_fingers_process", text="手指", icon='VIEW_PAN')
            
            col_fake.label(text="2. 合并与绑定:")
            row2 = col_fake.row(align=True)
            row2.operator("re4.fake_body_merge", text="身体", icon='LINKED')
            row2.operator("re4.fake_fingers_merge", text="手指", icon='LINKED')
            
            col_fake.label(text="3. 骨骼对齐 (含子级):")
            row3 = col_fake.row(align=True)
            row3.operator("re4.align_bones_full", text="完全对齐", icon='SNAP_ON')
            row3.operator("re4.align_bones_pos", text="仅对齐位置", icon='SNAP_VERTEX')

# ==========================================
# 注册/注销
# ==========================================
classes = [
    MHW_PT_SuiteSettings,
    MHW_OT_GeneralTools,
    MHW_PT_MainPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.mhw_suite_settings = bpy.props.PointerProperty(type=MHW_PT_SuiteSettings)

def unregister():
    del bpy.types.Scene.mhw_suite_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
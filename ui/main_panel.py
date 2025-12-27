import bpy

class MHW_PT_SuiteSettings(bpy.types.PropertyGroup):
    show_mhwi: bpy.props.BoolProperty(name="MHWI", default=True)
    show_mhws: bpy.props.BoolProperty(name="MHWs", default=False)
    show_re4: bpy.props.BoolProperty(name="RE4", default=False)
    
class MHW_OT_GeneralTools(bpy.types.Operator):
    """通用工具集合 Operator"""
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
    bl_label = "MHW Suite"
    bl_idname = "MHW_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MHW Suite'

    def draw(self, context):
        layout = self.layout
        settings = context.scene.mhw_suite_settings
        
        # 1. 顶部开关
        row = layout.row(align=True)
        row.prop(settings, "show_mhwi", toggle=True, text="MHWI")
        row.prop(settings, "show_mhws", toggle=True, text="Wilds") # 新增 Wilds
        row.prop(settings, "show_re4", toggle=True, text="RE4")
        
        # 2. 通用工具栏 (Always Visible)
        box = layout.box()
        box.label(text="通用工具", icon='TOOL_SETTINGS')
        
        col = box.column(align=True)
        col.operator("mhw.general_tools", text="扭转归零 (Roll=0)").action = 'ROLL_ZERO'
        
        row = col.row(align=True)
        row.operator("mhw.general_tools", text="添加尾骨").action = 'ADD_TAIL'
        row.operator("mhw.general_tools", text="镜像对齐 X").action = 'MIRROR_X'
        
        col.operator("mhw.general_tools", text="骨链简化 (隔1删1)").action = 'SIMPLIFY_CHAIN'
        
        # 3. 游戏专用栏 (动态显示)
        if settings.show_mhwi:
            self.draw_mhwi_tools(layout)
            
        if settings.show_mhws:
            box = layout.box()
            box.label(text="MHWilds Tools", icon='WORLD')
            box.operator("mhwilds.tpose_convert", icon='ARMATURE_DATA')
            
    def draw_mhwi_tools(self, layout):
        # ... 绘制 MHWI 按钮 ...
        pass
import bpy
from . import updater  # 导入 updater 以访问状态和 Operator

class MT_Preferences(bpy.types.AddonPreferences):
    # 这里的名字必须和插件文件夹名称一致！
    # 动态获取包名，确保你的文件夹叫啥都没问题
    bl_idname = __package__.split(".")[0] 

    # --- 保存的设置 ---
    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Update",
        description="Check for updates automatically on startup (Not implemented yet)",
        default=False
    )
    
    check_interval: bpy.props.EnumProperty(
        name="Interval",
        items=[
            ('DAYS_7', "Every 7 Days", ""),
            ('DAYS_30', "Every Month", ""),
            ('ALWAYS', "Always", ""),
        ],
        default='DAYS_7'
    )
    
    last_check_time: bpy.props.StringProperty(
        name="Last Check Time",
        default="Never",
        options={'HIDDEN'} # 不在界面直接显示输入框
    )

    def draw(self, context):
        layout = self.layout
        
        # 模仿截图的 Updater Settings 区域
        box = layout.box()
        box.label(text="Updater Settings", icon='PREFERENCES')
        
        # 第一行：自动更新开关 + 间隔 (模仿截图布局)
        row = box.row()
        row.prop(self, "auto_check_update")
        
        sub = row.row()
        sub.enabled = self.auto_check_update
        sub.prop(self, "check_interval", text="Interval")
        
        box.separator()
        
        # 第二行：主要操作按钮 (模仿截图的大按钮布局)
        # 使用 split 将区域分为两半
        split = box.split(factor=0.6)
        
        # 左侧：检查更新按钮
        col_left = split.column()
        if updater.update_state["is_checking"]:
            col_left.enabled = False
            col_left.operator("mt.check_update", text="Checking...", icon='time')
        else:
            col_left.operator("mt.check_update", text="Check now for update", icon='FILE_REFRESH')
            
        # 右侧：根据状态显示不同内容
        col_right = split.column()
        if updater.update_state["has_update"]:
            col_right.alert = True # 红色显示
            ops = col_right.operator("mt.open_update_link", text=f"New: {updater.update_state['new_version']} (Download)", icon='URL')
        else:
            # 如果没有更新，或者是刚安装
            col_right.label(text="Addon is up to date", icon='CHECKMARK')

        # 底部：上次检查时间
        box.separator()
        row_bottom = box.row()
        row_bottom.alignment = 'LEFT'
        # 稍微变灰一点的文字感觉
        row_bottom.label(text=f"Last update check: {self.last_check_time}", icon='TIME')

# 注册逻辑
def register():
    bpy.utils.register_class(MT_Preferences)

def unregister():
    bpy.utils.unregister_class(MT_Preferences)
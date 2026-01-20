import bpy
import urllib.request
import json
import threading
import webbrowser
from datetime import datetime

# 你的 version.json 地址
REPO_URL = "https://raw.githubusercontent.com/Dimcirui/Modding-Toolkit/refs/heads/feat/func_simplify/version.json"

# 运行时状态（不需要保存）
update_state = {
    "is_checking": False,
    "has_update": False,
    "new_version": "",
    "link": ""
}

def get_preferences(context):
    """获取当前插件的偏好设置"""
    # __package__ 通常是文件夹名 "MHW-MODDING-TOOLKIT"
    return context.preferences.addons[__package__.split('.')[0]].preferences

def check_updates_thread(context_window_manager):
    """后台线程：检查更新"""
    global update_state
    update_state["is_checking"] = True
    
    try:
        # print(f"正在检查更新: {REPO_URL}")
        response = urllib.request.urlopen(REPO_URL, timeout=5)
        data = json.loads(response.read().decode('utf-8'))
        
        remote_version = tuple(data['version'])
        
        # 获取本地版本
        # 注意：这里需要一种方法获取主包的 bl_info，或者硬编码
        # 为了通用，我们假设本地版本小于远程版本来测试
        # 实际代码中建议从 __init__ 传递版本，或者使用 sys.modules 获取
        # 这里简化处理，你可以根据需要完善 get_current_version
        local_version = (0, 0, 0) 
        try:
            mod = bpy.context.preferences.addons[__package__.split('.')[0]]
            local_version = mod.bl_info.get('version', (0, 0, 0))
        except:
            pass

        if remote_version > local_version:
            update_state["has_update"] = True
            update_state["new_version"] = ".".join(map(str, remote_version))
            update_state["link"] = data['link']
        else:
            update_state["has_update"] = False
            
    except Exception as e:
        print(f"检查更新失败: {e}")
    
    update_state["is_checking"] = False
    
    # 更新“上次检查时间” (需要切回主线程上下文，或者利用闭包)
    # 这一步在线程里直接修改属性可能会有风险，但在 Blender Python 中通常对于 StringProperty 是安全的
    # 为了安全，我们在 Operator 结束时或者下一次 draw 时刷新时间，
    # 这里我们只记录时间字符串，由主线程的 Operator 调用完后更新会更安全，
    # 但为了简单，我们在这里不做属性写入，只修改全局 state，让 Operator 处理属性写入。
    
    # 强制刷新 UI
    for window in context_window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()

class MT_OT_CheckUpdate(bpy.types.Operator):
    """点击按钮：立即检查更新"""
    bl_idname = "mt.check_update"
    bl_label = "Check Now"
    bl_description = "Check for updates immediately"
    
    def execute(self, context):
        # 更新“上次检查时间”
        prefs = get_preferences(context)
        prefs.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 启动线程
        thread = threading.Thread(target=check_updates_thread, args=(context.window_manager,))
        thread.start()
        
        self.report({'INFO'}, "Checking for updates...")
        return {'FINISHED'}

class MT_OT_OpenUpdateLink(bpy.types.Operator):
    """打开下载链接"""
    bl_idname = "mt.open_update_link"
    bl_label = "Go to Download"
    
    def execute(self, context):
        if update_state["link"]:
            webbrowser.open(update_state["link"])
        return {'FINISHED'}

# 注册类
classes = (
    MT_OT_CheckUpdate,
    MT_OT_OpenUpdateLink,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
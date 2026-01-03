import bpy

class ModderBatchSettings(bpy.types.PropertyGroup):
    # 存储 X 预设文件名 (assets/import_presets/)
    import_preset_enum: bpy.props.EnumProperty(
        name="Source Preset (X)",
        description="Select the source mapping preset",
        items=[('vrc_x.json', 'VRChat', ''), ('mmd_x.json', 'MMD (JP/EN)', ''), ('endfield_x.json', 'Endfield', '')]
    )
    
    # 存储 Y 预设文件名 (assets/bone_presets/)
    target_preset_enum: bpy.props.EnumProperty(
        name="Target Preset (Y)",
        description="Select the target game preset",
        items=[('mhwi_y.json', 'MHWI', ''), ('mhr_y.json', 'MHR', '')]
    )
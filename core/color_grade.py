"""core/color_grade.py — 生成贴图前对**色彩类贴图**做的整体色调处理。

为什么这是一个选项，而不是默认做掉
----------------------------------
实测原版 MHW 贴图 ``md_wood000_BML.tex`` 的格式是 ``BC1UNORMSRGB``，法线是
``BC5UNORM`` —— 也就是说 MHW 的 BML **就是 sRGB 标记 + sRGB 编码**，和生成器现在
的做法一致。所以把 sRGB 源图原样搬进 .tex 在色彩学上**是正确的**，这里的处理不是
在修正什么，而是在补 UE 之类的源游戏与 MHW 之间的**美术口径差**：源素材的反照率
普遍更亮，直接搬过来在 MHW 的光照下发白发灰。

既然是口径差而不是错误，就必须由使用者选。默认给的是 ``SRGB`` 而不是 ``NONE``——
实测下来源素材（UE 解包那类）绝大多数需要这一档，让多数人开箱即用比"默认不动任何
数据"更有用。代价是少数本来就在游戏口径里的素材会被做黑，所以 ``NONE`` 那一项的
名字里直接写了这个症状（"做出的贴图发黑再选这个"），照着选就行。

为什么在浮点缓冲上做
--------------------
对已经 8bit 的成品做 sRGB→线性会碾掉暗部：实测一张 median 66 的布料贴图转完变成
median 14，暗部挤进十几个色阶，再也调不回来。所以这里接在合成/编码之前的浮点数据
上，量化只发生一次。

三档的定义
----------
``NONE``      原样直通。色彩学正确的那一档。
``SRGB``      一次 sRGB→线性。幂曲线：压中间调与暗部，**白点不动**（255→255）。
``EXPOSURE``  曝光 −1.5EV + 亮度 −30 + 自然饱和度 +30，社区里流传的那套手调口径。
              乘法+平移：整条线一起压，**白点也被拉下来**（255→160→130）。

两者不是一回事，也不该被当成互相的近似：实测最大差 124.6/255、RMS 52.1，用纯曝光
去逼近 sRGB 曲线最优也只能到 −1.14EV、平均残差仍有 27.7。选哪个是审美，不是对错。
"""

import numpy as np

#: EnumProperty 的 items 用；显示名由调用方经 i18n 取，这里只定标识与顺序。
MODES = ('NONE', 'SRGB', 'EXPOSURE')

#: EXPOSURE 档的三个参数。写成常量是为了让"社区口径"这件事在代码里有个确切定义，
#: 而不是散在某次提交的说明里。
EXPOSURE_EV = -1.5
BRIGHTNESS_OFFSET = -30.0 / 255.0
VIBRANCE = 0.30


def srgb_to_linear(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * (x ** (1 / 2.4)) - 0.055)


def _vibrance(rgb, amount):
    """自然饱和度：低饱和的像素提得多，高饱和的几乎不动。

    Photoshop 的 Vibrance 没有公开定义，这里用通行的近似——按 HSV 饱和度缩放，
    缩放系数随饱和度衰减，明度(max)保持不变，所以它只改颜色不改亮度。
    """
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    with np.errstate(divide='ignore', invalid='ignore'):
        sat = np.where(mx > 0.0, (mx - mn) / np.maximum(mx, 1e-8), 0.0)
    new_sat = np.clip(sat * (1.0 + amount * (1.0 - sat)), 0.0, 1.0)
    # 保持 max 不变，按新旧饱和度之比拉开各通道与 max 的距离
    with np.errstate(divide='ignore', invalid='ignore'):
        k = np.where(sat > 1e-6, new_sat / np.maximum(sat, 1e-8), 1.0)
    out = mx[:, :, None] - (mx[:, :, None] - rgb) * k[:, :, None]
    return np.clip(out, 0.0, 1.0)


def grade(arr, mode):
    """对 ``(h, w, 4)`` 的 0..1 浮点 RGBA 施加色调处理，返回新数组。

    **Alpha 不动**：它不是颜色，承载的是不透明度或被打包进去的第四个量，
    跟着做伽马会把遮罩弄坏。
    """
    if mode == 'NONE' or mode not in MODES:
        return arr
    out = np.array(arr, dtype=np.float32, copy=True)
    rgb = np.clip(out[:, :, :3], 0.0, 1.0)

    if mode == 'SRGB':
        rgb = srgb_to_linear(rgb)
    else:  # EXPOSURE
        # 曝光在**线性光**里是乘法，所以先解码、乘、再编码回显示域
        lit = srgb_to_linear(rgb) * (2.0 ** EXPOSURE_EV)
        rgb = linear_to_srgb(lit)
        rgb = np.clip(rgb + BRIGHTNESS_OFFSET, 0.0, 1.0)
        rgb = _vibrance(rgb, VIBRANCE)

    out[:, :, :3] = rgb
    return out


def is_color_format(dxgi_format_name):
    """这个槽位算不算"色彩类" —— 以 DXGI 格式名是否带 sRGB 为准。

    不另立一张槽位名单：``slot_resolver.resolve_dds_format`` 已经用
    ``SRGB_SLOT_TYPES`` 做过这个判断了，再抄一份必然漂移。
    """
    return bool(dxgi_format_name) and dxgi_format_name.upper().endswith('_SRGB')


#: EnumProperty 的默认下标。动态 items（items=callback）的 default 只能是 int，
#: 所以"默认选哪一档"由**顺序**决定 —— 改 MODES 的顺序就等于悄悄改了所有人的默认值。
#: tests/test_color_grade.py 有一条断言钉着 MODES[DEFAULT_MODE_INDEX] == 'SRGB'。
#:
#: 默认给 SRGB 而不是 NONE：实测下来源素材（UE 解包那类）绝大多数需要这一档，
#: 让多数人开箱即用比"默认不动任何数据"更有用；不需要的那少数人会看到贴图发黑，
#: 而 NONE 那一项的名字里直接写了这个症状，照着选就行。
DEFAULT_MODE_INDEX = 1


def color_grade_items():
    """三档的 EnumProperty items。

    放在这里而不是每个设置组各写一份：这个列表出现在 11 个地方（5 个生成器、
    5 个贴图处理器、贴图转换对话框），各抄一份必然漂移，而漂移的表现是"同一个选择
    在不同入口给出不同像素"。

    T() 在函数内部 import：本模块要能脱离 Blender 加载（离线测试跑的就是它），
    而 i18n 依赖 bpy。离线测试不会调用这个函数。
    """
    from .i18n import T
    return [
        ('NONE',     T("core.color_grade.none"),     T("core.color_grade.none_desc")),
        ('SRGB',     T("core.color_grade.srgb"),     T("core.color_grade.srgb_desc")),
        ('EXPOSURE', T("core.color_grade.exposure"), T("core.color_grade.exposure_desc")),
    ]

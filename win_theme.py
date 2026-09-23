"""Windows 主题集成 + Fluent (WinUI) 精确配色与动画时长。

配色与时长全部取自 RinUI / Class-Widgets 的 QML 主题文件 (themes/dark.qml,
themes/light.qml, themes/utils.qml), 数值逐项对齐, 不是估算。

三件事:
  1. 读明暗模式: HKCU\\...\\Themes\\Personalize\\AppsUseLightTheme (0=深色 1=浅色)
  2. 读主题色:   HKCU\\Software\\Microsoft\\Windows\\DWM\\AccentColor (ABGR 打包)
                 兜底 DwmGetColorizationColor, 再兜底 Windows 默认蓝 #0078D4
  3. 实时监听:   轮询 + WM_SETTINGCHANGE 双保险, 变了就发信号让界面重刷。

为什么用轮询: 注册表没有变更通知 API, 而 WM_SETTINGCHANGE 在"改主题色"时
不一定广播 (实测只有切换明暗/壁纸才发)。1.5s 轮询开销可忽略, 且绝对可靠。
"""
import ctypes
import sys
import winreg

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QColor

DEFAULT_ACCENT = "#0078d4"

_ACCENT_KEY = r"Software\Microsoft\Windows\DWM"
_PERSONALIZE_KEY = (r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Themes\Personalize")

# --------------------------------------------------------------------------- 动画时长
# 取自 RinUI/themes/utils.qml, 单位 ms
ANIM_FAST = 167          # animationSpeedFaster
ANIM_APPEARANCE = 187    # appearanceSpeed  (界面/悬停切换)
ANIM = 250               # animationSpeed   (导航折叠、指示条淡入)
ANIM_EXPANDER = 333      # animationSpeedExpander
ANIM_MIDDLE = 667        # animationSpeedMiddle (原为指示条生长/页面上滑)

# 指示条生长原来用 ANIM_MIDDLE(667ms)。但导航切换是每天几十次的高频操作,
# 667ms 会让每次点击都"等它长出来"。收敛到 333ms —— 仍是"从中心生长"的观感,
# 但不再拖沓。页面上滑同理 (见 SettingsWindow._switch_page)。
ANIM_INDICATOR = 333


def animations_enabled():
    """Windows 辅助功能里的「在 Windows 中显示动画」是否开启。

    等价于 Web 的 prefers-reduced-motion: 关掉时应当跳过动画。
    读不到时返回 True (默认开)。
    """
    try:
        v = ctypes.c_int()
        # SPI_GETCLIENTAREAANIMATION = 0x1042
        if ctypes.windll.user32.SystemParametersInfoW(
                0x1042, 0, ctypes.byref(v), 0):
            return bool(v.value)
    except Exception:
        pass
    return True


_ANIM_ON = None


def dur(ms):
    """按系统辅助功能开关决定动画时长: 关掉动画时返回 0。"""
    global _ANIM_ON
    if _ANIM_ON is None:
        _ANIM_ON = animations_enabled()
    return int(ms) if _ANIM_ON else 0


# --------------------------------------------------------------------------- 读取
def _read_dword(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            v, _ = winreg.QueryValueEx(k, name)
            return int(v)
    except Exception:
        return None


def is_light_mode():
    """系统是否为浅色模式。读不到时按深色处理。"""
    v = _read_dword(winreg.HKEY_CURRENT_USER, _PERSONALIZE_KEY,
                    "AppsUseLightTheme")
    return bool(v) if v is not None else False


def _abgr_to_rgb(v):
    """DWM\\AccentColor 是 ABGR 打包 (0xAABBGGRR)。"""
    return v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF


def _argb_to_rgb(v):
    """DwmGetColorizationColor 返回 ARGB (0xAARRGGBB)。"""
    return (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF


def get_accent_rgb():
    """当前系统主题色 (r,g,b)。多级兜底, 永远返回可用颜色。"""
    v = _read_dword(winreg.HKEY_CURRENT_USER, _ACCENT_KEY, "AccentColor")
    if v:
        rgb = _abgr_to_rgb(v)
        if rgb != (0, 0, 0):
            return rgb
    try:
        color = ctypes.c_ulong()
        opaque = ctypes.c_int()
        if ctypes.windll.dwmapi.DwmGetColorizationColor(
                ctypes.byref(color), ctypes.byref(opaque)) == 0 and color.value:
            return _argb_to_rgb(color.value)
    except Exception:
        pass
    return (0x00, 0x78, 0xD4)


def _hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _rgba(rgb, a):
    """Fluent 的叠加色写法: rgba(r,g,b,α) 直接写进 QSS (α 为 0..1)。"""
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {a:.4f})"


# --------------------------------------------------------------------------- 调色板
class Palette:
    """一套 Fluent 配色。数值对齐 RinUI themes/dark.qml 与 light.qml。"""

    def __init__(self, light, accent_rgb):
        self.light = light
        self.accent_rgb = accent_rgb
        self.accent = _hex(accent_rgb)

        # 主色的明暗变体: 深色主题提亮 (RinUI: lighter(1.6).darker(1.2))
        c = QColor(*accent_rgb)
        if light:
            self.accent_ui = self.accent
        else:
            v = min(255, int(c.value() * 1.6))
            c2 = QColor.fromHsv(c.hue(), c.saturation(), v)
            v2 = int(c2.value() / 1.2)
            c3 = QColor.fromHsv(c.hue(), c.saturation(), max(0, v2))
            self.accent_ui = c3.name()
        # 主色上的文字: Fluent 深色主题用黑字
        self.on_accent = "#000000" if light or c.value() > 160 else "#ffffff"

        if light:
            self.bg = "#f3f3f3"
            self.acrylic_bg = "#f9f9f9"
            self.card_alpha = 0.70
            self.card_rgb = (255, 255, 255)
            self.card_border_alpha = 0.0578
            self.card_border_rgb = (0, 0, 0)
            self.text = "#1b1b1b"
            self.text_rgb = (0, 0, 0)
            self.text_secondary_alpha = 0.6063
            self.text_tertiary_alpha = 0.4458
            self.control_alpha = 0.70
            self.control_rgb = (255, 255, 255)
            self.control_border_alpha = 0.06
            self.control_border_rgb = (0, 0, 0)
            self.divider_alpha = 0.0803
            self.divider_rgb = (0, 0, 0)
            self.subtle_alpha = 0.0
            self.subtle_rgb = (255, 255, 255)
            self.subtle_hover_alpha = 0.0373    # subtleSecondary
            self.subtle_press_alpha = 0.0241    # subtleTertiary
            self.sel_rgb = (0, 0, 0)
            self.window_border_alpha = 0.0924
            self.scroll_rgb = (0, 0, 0)
            self.scroll_alpha = 0.35
            self.menu_bg = "#f9f9f9"
            self.close_hover = "#c42b1c"
        else:
            self.bg = "#202020"
            self.acrylic_bg = "#2c2c2c"
            self.card_alpha = 0.0512
            self.card_rgb = (255, 255, 255)
            self.card_border_alpha = 0.10
            self.card_border_rgb = (0, 0, 0)
            self.text = "#ffffff"
            self.text_rgb = (255, 255, 255)
            self.text_secondary_alpha = 0.6047
            self.text_tertiary_alpha = 0.5442
            self.control_alpha = 0.0605
            self.control_rgb = (255, 255, 255)
            self.control_border_alpha = 0.09
            self.control_border_rgb = (0, 0, 0)
            self.divider_alpha = 0.0837
            self.divider_rgb = (255, 255, 255)
            self.subtle_alpha = 0.0
            self.subtle_rgb = (255, 255, 255)
            self.subtle_hover_alpha = 0.0605    # subtleSecondary
            self.subtle_press_alpha = 0.0419    # subtleTertiary
            self.sel_rgb = (255, 255, 255)
            self.window_border_alpha = 0.0698
            self.scroll_rgb = (255, 255, 255)
            self.scroll_alpha = 0.45
            self.menu_bg = "#2c2c2c"
            self.close_hover = "#c42b1c"

        # 文本色的次要/三级变体 (叠加色)
        self.text_secondary = _rgba(self.text_rgb, self.text_secondary_alpha)
        self.text_tertiary = _rgba(self.text_rgb, self.text_tertiary_alpha)

        # ---- 供 QSS 使用的半透明色 ----
        self.card = _rgba(self.card_rgb, self.card_alpha)
        self.card_hover = _rgba(self.card_rgb, self.card_alpha + 0.03)
        self.card_border = _rgba(self.card_border_rgb, self.card_border_alpha)
        self.control = _rgba(self.control_rgb, self.control_alpha)
        self.control_hover = _rgba(self.control_rgb, self.control_alpha + 0.03)
        self.control_border = _rgba(self.control_border_rgb, self.control_border_alpha)
        self.divider = _rgba(self.divider_rgb, self.divider_alpha)
        self.subtle = _rgba(self.subtle_rgb, self.subtle_alpha)
        self.subtle_hover = _rgba(self.subtle_rgb, self.subtle_hover_alpha)
        self.subtle_press = _rgba(self.subtle_rgb, self.subtle_press_alpha)
        self.scroll = _rgba(self.scroll_rgb, self.scroll_alpha)
        self.window_border = _rgba((117, 117, 117), self.window_border_alpha)

        # 窗口整体 scrim: DWM Mica 已经把材质画在窗口背后, 这里只叠薄薄一层压暗,
        # 让材质与壁纸色调透出来。实测太薄 (<0.4) 会看不清内容。
        self.scrim_rgb = (243, 243, 243) if light else (32, 32, 32)
        self.scrim_alpha = 0.55 if light else 0.45

        # 内容区图层 (RinUI NavigationView 的 appLayer / colors.layerColor)
        # 它比导航栏+标题栏**亮一档**, 是这两个区域深浅差异的来源。
        # 实测标定: 叠 this 后再叠卡片色, 内容区应比导航区亮约 +18 色阶。
        self.layer_rgb = (255, 255, 255) if light else (255, 255, 255)
        self.layer_alpha = 0.50 if light else 0.035
        self.layer = _rgba(self.layer_rgb, self.layer_alpha)

        # 滑块圆球的外圈色 (与卡片底色一致, 做出"挖空"观感)
        self.slider_ring = self.acrylic_bg

        # ---- 滑块三件套 (对齐 RinUI Slider.qml) ----
        # 轨道 = controlStrongColor; 手柄外圈 = controlQuaternaryColor;
        # 手柄中圈 = controlSolidColor; 中心圆点 = accent
        if light:
            self.control_strong = (0, 0, 0, 0.4458)
            self.control_quaternary = (243, 243, 243, 0.76)
            self.control_solid = "#ffffff"
        else:
            self.control_strong = (255, 255, 255, 0.5442)
            self.control_quaternary = (255, 255, 255, 0.0698)
            self.control_solid = "#454545"

    # 供窗口绘制用 (QColor)
    def scrim_color(self, mica_active):
        a = self.scrim_alpha if mica_active else 1.0
        return QColor(self.scrim_rgb[0], self.scrim_rgb[1], self.scrim_rgb[2],
                      int(round(a * 255)))

    def panel_scrim_color(self, mica_active):
        """控制面板是浮在桌面内容之上的小窗, 不透明度要高一些才看得清。"""
        a = 0.90 if mica_active else 1.0
        return QColor(self.scrim_rgb[0], self.scrim_rgb[1], self.scrim_rgb[2],
                      int(round(a * 255)))

    def text_color(self):
        return QColor(self.text)

    def secondary_color(self):
        if self.light:
            return QColor(0, 0, 0, int(self.text_secondary_alpha * 255))
        return QColor(255, 255, 255, int(self.text_secondary_alpha * 255))


def build_palette(light=None, accent_rgb=None):
    if light is None:
        light = is_light_mode()
    if accent_rgb is None:
        accent_rgb = get_accent_rgb()
    return Palette(light, accent_rgb)


def snapshot():
    """当前系统主题的指纹, 用于判断有没有变化。"""
    return (is_light_mode(), get_accent_rgb())


# --------------------------------------------------------------------------- 监听
class ThemeWatcher(QObject):
    """监听系统主题色 / 明暗模式变化, 变化时发 changed 信号。

    轮询为主 (注册表无变更通知), 原生事件过滤器做即时响应; 两者都调 _check(),
    靠指纹比对自动去重。
    """

    changed = Signal()

    def __init__(self, interval_ms=1500, parent=None):
        super().__init__(parent)
        self._fp = snapshot()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._check)
        self._filter = None

    def start(self):
        self._timer.start()
        self._install_filter()

    def stop(self):
        self._timer.stop()

    def _install_filter(self):
        if sys.platform != "win32":
            return
        try:
            from PySide6.QtCore import QAbstractNativeEventFilter

            watcher = self

            class _Filter(QAbstractNativeEventFilter):
                def nativeEventFilter(self, event_type, message):
                    try:
                        # MSG.hwnd, MSG.message, ...
                        msg = ctypes.cast(int(message),
                                          ctypes.POINTER(ctypes.c_uint))[1]
                        if msg in (0x001A, 0x0320):  # WM_SETTINGCHANGE / WM_THEMECHANGED
                            watcher._check()
                    except Exception:
                        pass
                    return False, 0

            self._filter = _Filter()
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._filter)
        except Exception:
            self._filter = None

    def _check(self):
        fp = snapshot()
        if fp != self._fp:
            self._fp = fp
            self.changed.emit()

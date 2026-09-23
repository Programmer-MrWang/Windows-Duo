"""设置窗口: QML + RinUI 实现 (与 Class-Widgets 同框架、同控件库)。

本文件只是**启动器** —— 界面全部在 qml/ 下:
    qml/Settings.qml                  FluentWindow + 导航栏
    qml/pages/*.qml                   5 个设置页 (FluentPage + SettingCard)
    qml/components/SliderField.qml    可复用的"标签+数值+滑块"卡片

对外仍保持原来的构造签名 SettingsWindow(cfg, on_apply, on_saved=None),
所以 glass_overlay.py 不需要改。
"""
import sys
from pathlib import Path

from qml_bridge import ConfigBridge


def _app_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _qml_dir():
    """QML 资源目录 (打包后由 PyInstaller 解到 _MEIPASS)。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", _app_dir()))
        return base / "qml"
    return Path(__file__).parent / "qml"


CFG_PATH = _app_dir() / "config.json"


def _sync_rinui_theme(win):
    """把 Windows 的强调色与明暗模式同步给 RinUI。

    RinUI 自带主题系统 (默认主色 #605ed2); 本项目的约定是跟随 Windows,
    所以启动时和系统主题变化时都要覆盖一次。
    """
    import win_theme
    p = win_theme.build_palette()
    try:
        win.theme_manager.set_theme_color(p.accent)
        win.theme_manager.toggle_theme("Light" if p.light else "Dark")
    except Exception as e:  # noqa
        print("[主题] 同步给 RinUI 失败:", e)
    return p


def _create_rinui_window(qml_path, bridge):
    """创建 RinUIWindow, 并在 load() 之前把 bridge 注册成上下文属性。

    RinUIWindow(qml_path) 会在构造里直接 load(), 那样就来不及挂上下文属性;
    所以分两步: 先建空窗口 -> setContextProperty -> 再 load()。
    主题色也要在 load() 前设, 否则首帧会用 RinUI 默认色再跳变。
    """
    from RinUI import RinUIWindow
    import app_info
    win = RinUIWindow()
    win.engine.rootContext().setContextProperty("Config", bridge)
    app_info.register_context(win.engine, CFG_PATH)   # QML 里的 App.* (标题栏图标 / 关于页)
    _sync_rinui_theme(win)
    win.load(qml_path)
    return win


class SettingsWindow:
    """QML 设置窗口的 Python 侧封装 (接口与原来的 Qt Widgets 版一致)。"""

    def __init__(self, cfg, on_apply, on_saved=None):
        self.cfg = cfg
        self.on_apply = on_apply
        self.on_saved = on_saved
        self.bridge = ConfigBridge(cfg, CFG_PATH, on_apply, on_saved)
        self._win = None
        self._qml_path = _qml_dir() / "Settings.qml"
        # 系统主题 (明暗/主色) 变化时同步给 RinUI
        import win_theme
        self._watcher = win_theme.ThemeWatcher(parent=self.bridge)
        self._watcher.changed.connect(self._on_system_theme_changed)
        self._watcher.start()

    def _on_system_theme_changed(self):
        if self._win is not None:
            _sync_rinui_theme(self._win)

    def show(self):
        if self._win is None:
            self._win = _create_rinui_window(self._qml_path, self.bridge)
        w = self._win.root_window
        w.show()
        w.requestActivate()
        return w

    def raise_(self):
        if self._win is not None:
            self._win.root_window.show()
            self._win.root_window.raise_()

    def activateWindow(self):
        if self._win is not None:
            self._win.root_window.requestActivate()

    def refresh_from_cfg(self):
        """外部 (如控制面板的翻转/灵敏度) 改了 cfg 后, 让 QML 重读。"""
        self.bridge.valuesChanged.emit()

    def close(self):
        if self._win is not None:
            self._win.root_window.close()

    @property
    def isVisible(self):
        return self._win is not None and self._win.root_window.isVisible()

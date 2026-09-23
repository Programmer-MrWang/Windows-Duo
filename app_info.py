"""应用元信息 · 图标 · 版本 —— 单一事实来源。

标题栏图标、任务栏图标、EXE 图标、「关于」页面里的版本号都从这里取, 不在各处
各写一份 (版本号写两遍必然会写歪)。

图标资源:
    icon.png / icon.ico   仓库根目录的原始素材 (2017px / 256px)
    assets/icon.png       256px, 供 QML 与窗口图标使用 (原图 4.6MB, 直接加载太浪费)
    assets/icon.ico       16~256 多尺寸, 供 EXE 与任务栏使用
后两份由 build_exe.py 从原图生成, 也一并提交到仓库, 源码运行时不依赖生成步骤。

路径要在「源码运行」和「打包运行」两种形态下都对:
  - 源码运行: 项目目录 / assets
  - 打包运行: PyInstaller 把 assets 解到 sys._MEIPASS (只读副本),
    而 config.json 仍在 EXE 旁边 (用户要能改)。两者不是同一个目录, 别混。
"""
import ctypes
import platform
import sys
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Slot

# --------------------------------------------------------------------------- 元信息
# 软件名只有一个: 界面、对话框、EXE、日志、任务栏全部从这里取。
#   APP_NAME  对外名称 (界面文字)
#   APP_SLUG  紧凑标识符 (EXE / 日志 / 打包名 —— 文件名里不放空格)
APP_NAME = "Windows Duo"
APP_SLUG = "WindowsDuo"
LOG_NAME = "windows_duo.log"
APP_TAGLINE = "让桌面，拥有折叠屏的纵深"
APP_VERSION = "0.0.0.1"
APP_ORG = "Programmer-MrWang"
# 仓库地址: 这是"地址"不是"名字", 仓库没改名之前不要动, 否则关于页的链接会 404
APP_HOMEPAGE = "https://github.com/Programmer-MrWang/foldable-screen-sim"
# 本项目按 GPL-3.0 发布 (仓库根目录的 LICENSE); 上游 WindowsDuo 是 MIT,
# MIT 允许派生作品改用 GPL, 致谢里保留上游署名即可。
APP_LICENSE = "GPL-3.0"
# Windows 任务栏靠 AppUserModelID 区分应用: 不设的话本进程会被并进 python.exe,
# 任务栏显示的是 Python 的图标而不是我们的。
APP_ID = "ProgrammerMrWang.WindowsDuo"


# --------------------------------------------------------------------------- 路径
def _app_dir():
    """程序所在目录 (EXE 目录 / 源码目录)。config.json 在这里。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _res_dir():
    """随包资源目录。打包后是 PyInstaller 的解包目录。"""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", _app_dir()))
    return Path(__file__).parent


def asset_path(name):
    """assets/ 下的资源; 找不到返回 None。"""
    p = _res_dir() / "assets" / name
    if p.exists():
        return p
    # 兜底: 直接跑源码而 assets/ 还没生成时, 退回根目录的原始素材
    legacy = Path(__file__).parent / name
    return legacy if legacy.exists() else None


def icon_png():
    p = asset_path("icon.png")
    if p:
        return p
    legacy = Path(__file__).parent / "icon.png"
    return legacy if legacy.exists() else None


def icon_ico():
    p = asset_path("icon.ico")
    if p:
        return p
    legacy = Path(__file__).parent / "icon.ico"
    return legacy if legacy.exists() else None


def icon_url():
    """QML 用的 file:// URL (QML 不认 Windows 反斜杠路径)。"""
    p = icon_png()
    return QUrl.fromLocalFile(str(p)).toString() if p else ""


# --------------------------------------------------------------------------- 图标
def apply_app_icon(app=None):
    """把图标装到「任务栏 + 所有窗口」。

    必须在 QApplication 创建后调用, 且越早越好 —— 窗口先建再设图标的话,
    任务栏上那一格会一直停留在旧图标 (Windows 缓存了窗口的 icon)。
    """
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception as e:  # noqa
            print("[图标] 设置 AppUserModelID 失败:", e)

    if app is None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
    if app is None:
        return
    from PySide6.QtGui import QIcon
    p = icon_ico() or icon_png()
    if p is not None:
        app.setWindowIcon(QIcon(str(p)))
        app.setApplicationName(APP_SLUG)
        app.setApplicationVersion(APP_VERSION)
        # 注意: 别设 setApplicationDisplayName —— Qt 会把它拼到每个窗口标题后面
        # ("Duo 控制面板 - Windows Duo"), 控制面板标题栏只有 344px 宽,
        # 拼上去标题就被挤没了。窗口标题一律以 QML 里声明的为准。
    else:
        print("[图标] 没找到 icon.ico / icon.png, 任务栏将使用默认图标")


# --------------------------------------------------------------------------- 运行环境
def _windows_name():
    if sys.platform != "win32":
        return platform.system()
    v = sys.getwindowsversion()
    if v.build >= 22000:
        name = "Windows 11"
    elif v.major >= 10:
        name = "Windows 10"
    else:
        name = f"Windows {v.major}.{v.minor}"
    return f"{name} (build {v.build})"


def _qt_version():
    try:
        from PySide6.QtCore import qVersion
        return qVersion()
    except Exception:  # noqa
        return "?"


def runtime_info():
    """一行运行环境, 用于「关于」页 —— 报 bug 时这一行就够了。"""
    try:
        import PySide6
        pyside = PySide6.__version__
    except Exception:  # noqa
        pyside = "?"
    return (f"Python {platform.python_version()} · PySide6 {pyside} · "
            f"Qt {_qt_version()} · {platform.machine()}")


# --------------------------------------------------------------------------- QML 桥
class AppInfo(QObject):
    """暴露给 QML 的应用信息 (上下文属性名 `App`)。

    只读元信息 + 两个「打开目录」动作; 会变的运行数据不在这里 (那是 Config 的活)。
    """

    def __init__(self, config_path=None, parent=None):
        super().__init__(parent)
        self._config_path = Path(config_path) if config_path else (_app_dir() / "config.json")

    def set_config_path(self, path):
        self._config_path = Path(path)

    # ---- 只读属性 ----
    @Property(str, constant=True)
    def name(self):
        return APP_NAME

    @Property(str, constant=True)
    def tagline(self):
        return APP_TAGLINE

    @Property(str, constant=True)
    def version(self):
        return APP_VERSION

    @Property(str, constant=True)
    def versionTag(self):
        return "v" + APP_VERSION

    @Property(str, constant=True)
    def homepage(self):
        return APP_HOMEPAGE

    @Property(str, constant=True)
    def license(self):
        return APP_LICENSE

    @Property(str, constant=True)
    def iconUrl(self):
        return icon_url()

    @Property(str, constant=True)
    def platformName(self):
        return _windows_name()

    @Property(str, constant=True)
    def runtime(self):
        return runtime_info()

    @Property(str, constant=True)
    def mode(self):
        return "打包版（单文件 EXE）" if getattr(sys, "frozen", False) else "源代码运行"

    @Property(str, constant=True)
    def configPath(self):
        return str(self._config_path)

    @Property(str, constant=True)
    def appDir(self):
        return str(_app_dir())

    # ---- 动作 ----
    @Slot()
    def openConfigDir(self):
        self._reveal(self._config_path)

    @Slot()
    def openAppDir(self):
        self._reveal(_app_dir())

    @staticmethod
    def _reveal(path):
        """在资源管理器里定位到该文件/目录。

        explorer 的 /select 即使成功也常返回非 0 退出码, 所以不看返回值;
        失败时退回打开父目录, 至少别让按钮点了没反应。
        """
        import subprocess
        path = Path(path)
        if not path.exists():
            path = path.parent
        try:
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                subprocess.Popen(["explorer", str(path)])
        except Exception as e:  # noqa
            print("[关于] 打开资源管理器失败:", e)


_bridge = None


def bridge(config_path=None):
    """全局单例 —— 设置窗口与控制面板共享同一个 QML 引擎, 重复注册会互相覆盖。"""
    global _bridge
    if _bridge is None:
        _bridge = AppInfo(config_path)
    elif config_path is not None:
        _bridge.set_config_path(config_path)
    return _bridge


def register_context(engine, config_path=None):
    """把 AppInfo 注册成 QML 上下文属性 `App`。"""
    engine.rootContext().setContextProperty("App", bridge(config_path))

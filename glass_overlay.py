"""
Windows Duo · 摄像头驱动「悬浮玻璃」
================================================================
以 WindowsDuo (win/glass_overlay.py) 为骨架改造, 只把角度来源换成摄像头:

  角度来源   串口 ESP32+MPU6050  ->  笔记本上盖摄像头 ORB 特征匹配 (tracker.py)
  其余       逆投影着色器 / Vogel 盘模糊 / mip LOD / 边缘覆盖率 / 自排除 / 工程化 全部照搬

模型 (与 WindowsDuo 逐行一致): 界面固定在世界空间平面上不动; 屏幕是一块玻璃, 绕
"铰链"(屏幕底边) 向观察者方向转开。每个像素: 眼睛 → 玻璃像素 → 延长交到界面平面
= 采样点。间隙越大 → 模糊半径越大、越暗; 视线完全出界 → 纯黑。靠近铰链处始终清晰,
远离铰链处(屏幕上部)先模糊、先消失。

与 WindowsDuo win 端的差异 (按需求):
  1. 角度来自摄像头 ORB (tracker.AngleTracker), 无需任何外接硬件。
  2. 连续控制: 折叠程度随角度平滑变化, 可停在任意角度悬停 (无意图识别状态机)。
  3. 只在"起效"时才显示叠加层; 不折叠时窗口隐藏, 桌面保持原生清晰。
  4. 背景为纯黑 (视线出界即黑), 不做壁纸兜底。

线程:
  CameraAngleReader : 摄像头 ~30Hz 读帧 -> ORB 估角 -> 折叠浓度
  CaptureWorker     : mss 截屏原始帧 (自带窗口已从捕获中排除)
  GL 主线程          : 上传纹理(带 mipmap) → 单 pass Duo 折叠着色器

用法:
  run_overlay.bat        摄像头驱动 (默认)
  run_manual.bat         键盘手动 (↑↓←→, 无需摄像头)
  --selftest             无窗口自检 (摄像头 / 截屏 / OpenGL)
  --smoke 4s 全屏演示自退, 抓帧存 PNG

控制台按键 (需先点一下控制台窗口获得焦点):
  标定基准帧 / 翻转方向 / 切自动 一律走控制面板按钮 (已停用对应键盘键)
  +/- 调灵敏度
  ↑/↓ 浓度 ±3%   ← 清空   → 拉满   r 切手动/角度自动   Esc 退出
"""
import json
import sys
import threading
import time
from pathlib import Path

# 打包成 --windowed EXE 时没有控制台: sys.stdout/stderr 为 None (或不可写),
# print 里任何非 GBK 字符 (如 "✔") 都会抛 UnicodeEncodeError 并中止程序。
# 只在真正没有可用控制台时才重定向到 UTF-8 日志文件, 开发时保留终端输出。
def _stdout_broken():
    if getattr(sys, "frozen", False):
        return True
    if sys.stdout is None or sys.stderr is None:
        return True
    try:
        "✔".encode(sys.stdout.encoding or "utf-8")
        return False
    except (UnicodeEncodeError, LookupError, AttributeError):
        return True


if _stdout_broken():
    try:
        from app_info import LOG_NAME
        _log_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        _log = open(_log_dir / LOG_NAME, "w", encoding="utf-8", buffering=1)
    except Exception:
        _log = open(__import__("os").devnull, "w", encoding="utf-8")
    sys.stdout = _log
    sys.stderr = _log
    # 输出被重定向到文件时, 关掉每 0.1s 的状态行 (否则日志会无限膨胀);
    # 状态仍会显示在屏幕上的控制面板里, 信息不丢失。
    _QUIET_STDOUT = True
else:
    _QUIET_STDOUT = False

import cv2
import mss
import numpy as np
from OpenGL import GL
from PySide6.QtCore import Property, QObject, QRectF, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import gl_core
import app_info
import tracker
import win_theme
from settings_window import SettingsWindow

def _app_dir():
    """程序所在目录: 打包成 EXE 后是 EXE 所在目录, 否则是脚本所在目录。

    config.json 必须和它同级 —— 用户要能编辑、程序要能写回。
    (PyInstaller 的 --onefile 会把资源解到临时目录 sys._MEIPASS, 那是只读副本,
    所以配置文件不能随包, 必须放在 EXE 旁边。)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _load_cfg(path):
    """读 config.json; 没有 / 读坏了就用出厂默认值, 并在旁边生成一份。

    这样发布时 dist/ 里只需要一个 EXE —— 首次运行自己长出配置文件, 也免得
    「用户把 config.json 删了程序就起不来」。默认值取自 qml_bridge.DEFAULTS,
    与设置窗口「恢复默认」用的是同一份, 两边不会打架。
    """
    from qml_bridge import DEFAULTS
    try:
        cfg = json.loads(path.read_text("utf-8"))
        if not isinstance(cfg, dict):
            raise ValueError("顶层不是对象")
        return cfg
    except FileNotFoundError:
        print(f"[配置] 没找到 {path.name}, 用出厂默认值生成一份")
    except Exception as e:  # noqa
        # 内容坏了 (手改出错/上次写到一半断电): 留个 .bak 再重建, 别让程序起不来
        print(f"[配置] {path.name} 读不出来 ({e}), 备份为 {path.name}.bak 后重建")
        try:
            path.replace(path.with_name(path.name + ".bak"))
        except Exception:  # noqa
            pass
    cfg = dict(DEFAULTS)
    try:
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    except Exception as e:  # noqa
        # EXE 放在只读目录 (如 Program Files) 时写不进去, 用内存里的默认值继续跑
        print(f"[配置] 写入失败 ({e}), 本次运行使用默认值")
    return cfg


APP_DIR = _app_dir()
CFG_PATH = APP_DIR / "config.json"
CFG = _load_cfg(CFG_PATH)

DEG2RAD = 3.14159265358979 / 180.0

# config.json 是唯一参数入口: 把 tracker.py 的模块级常量按配置注入
tracker.MIN_MATCHES = int(CFG.get("min_matches", 12))
tracker.REKEY_RAD = float(CFG.get("rekey_deg", 6.9)) * DEG2RAD
tracker.MAX_STEP_RAD = float(CFG.get("max_step_deg", 17.2)) * DEG2RAD
tracker.ANCHOR_SPACING = float(CFG.get("anchor_spacing_deg", 12.0)) * DEG2RAD
tracker.ANCHOR_MATCH_RANGE = float(CFG.get("anchor_match_range_deg", 25.0)) * DEG2RAD
tracker.ANCHOR_MIN_INLIERS = int(CFG.get("anchor_min_inliers", 15))


def _make_format():
    """请求 3.3 core。本机 Intel 驱动只提供 forward-compatible 上下文,
    compatibility 的固定管线不可用, 故用 core + VAO/VBO (见 shaders.py)。"""
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapInterval(1)
    return fmt




# ---------------------------------------------------------------- 键盘控制
class ManualControl(threading.Thread):
    """键盘控制玻璃浓度 + 摄像头标定/调参。

    ↑/w +3%   ↓/s -3%   →/d 100%   ←/a 0%   r 切角度自动   Esc/q 退出
    标定/翻转方向/切自动 只走控制面板按钮; 键盘保留浓度与灵敏度调节。
    默认为"角度自动"(跟随摄像头); 任何调节键都切回手动覆盖。
    """

    def __init__(self, auto=True):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.target = 0.0
        self.last_key = ""
        self.quit_flag = False
        self.auto = auto
        self.calib_event = threading.Event()
        self.flip_sign = False
        self.scale_delta = 0.0
        self.enabled = True

    def get(self):
        with self.lock:
            return self.target, self.last_key, self.auto

    def take_calib(self):
        if self.calib_event.is_set():
            self.calib_event.clear()
            return True
        return False

    def take_flip(self):
        with self.lock:
            v = self.flip_sign
            self.flip_sign = False
            return v

    def take_scale_delta(self):
        with self.lock:
            v = self.scale_delta
            self.scale_delta = 0.0
            return v

    def _apply(self, value, key, absolute=False):
        """absolute=True 时 value 是目标浓度 (清零/拉满); 否则是增量 (±0.03)。"""
        with self.lock:
            self.auto = False
            if absolute:
                self.target = max(0.0, min(1.0, value))
            else:
                self.target = max(0.0, min(1.0, self.target + value))
            self.last_key = key

    def run(self):
        import msvcrt
        while not self.quit_flag:
            ch = msvcrt.getwch()
            absolute = False
            if ch in ("\xe0", "\x00"):
                k = msvcrt.getwch()
                # (值, 是否绝对量): K=←清零, M=→拉满
                mapping = {"H": (0.03, False), "P": (-0.03, False),
                           "M": (1.0, True), "K": (0.0, True)}
                got = mapping.get(k)
                value, absolute = got if got is not None else (None, False)
                key = {"H": "↑", "P": "↓", "M": "→", "K": "←"}.get(k, k)
            else:
                if ch in ("\x1b", "q", "Q"):
                    self.quit_flag = True
                    break
                low = ch.lower()
                # 说明: SPACE/F/R 已按需求停用 —— 标定、翻转方向、切自动
                # 一律只走控制面板的按钮, 避免键盘与面板两条路径不一致。
                if ch in ("+", "="):
                    with self.lock:
                        self.scale_delta = 0.1
                        self.last_key = "SCALE+"
                    continue
                if ch in ("-", "_"):
                    with self.lock:
                        self.scale_delta = -0.1
                        self.last_key = "SCALE-"
                    continue
                # w/s 增量, a 清零, d 拉满
                mapping = {"w": (0.03, False), "s": (-0.03, False),
                           "d": (1.0, True), "a": (0.0, True)}
                got = mapping.get(low)
                value, absolute = got if got is not None else (None, False)
                key = ch
            if value is not None:
                self._apply(value, key, absolute)


# ---------------------------------------------------------------- 摄像头角度线程
class CameraAngleReader(threading.Thread):
    """摄像头 → ORB 估角 → 折叠浓度 (0..1)。接口对齐 WindowsDuo AngleReader.get()。

    get() 返回 (concentration, fold_angle, pitch_deg, fps, status)
      concentration 0=完全展开(无效果) .. 1=完全折叠
    """

    def __init__(self, manual: ManualControl):
        super().__init__(daemon=True)
        self.manual = manual
        self.lock = threading.Lock()
        self.conc = 0.0
        self.fold = 180.0
        self.pitch = 0.0
        self.matches = 0
        self.fps = 0.0
        self.status = "starting"
        self.last_gray = None
        self.scale = float(CFG.get("scale", 1.1))
        self.sign = int(CFG.get("sign", -1))
        self._stop_requested = False

        # 摄像头打开失败不应让整个程序崩溃: 捕获异常, 线程进入"无摄像头"状态,
        # 用户仍可用 r 键切手动模式或换 camera_index 后重启。
        try:
            self.tracker = tracker.AngleTracker(
                camera_index=int(CFG.get("camera_index", 0)),
                nfeatures=int(CFG.get("nfeatures", 1200)),
                ratio=float(CFG.get("ratio", 0.75)),
            )
            self.tracker_error = None
        except Exception as e:  # noqa
            self.tracker = None
            self.tracker_error = str(e)
            self.status = "摄像头打开失败"
            print(f"[摄像头] 打开失败: {e}")
            print("         请确认摄像头未被其它程序占用, 或改 config.json 的 camera_index。")

    def get(self):
        with self.lock:
            return self.conc, self.fold, self.pitch, self.fps, self.status

    def stop(self):
        self._stop_requested = True

    def apply_config(self, cfg):
        """识别参数热更新 (设置窗口调用)。摄像头索引改不了, 需重启。"""
        with self.lock:
            self.scale = float(cfg.get("scale", self.scale))
            self.sign = int(cfg.get("sign", self.sign))
        # tracker.py 的模块级常量按新配置重新注入
        tracker.MIN_MATCHES = int(cfg.get("min_matches", 12))
        tracker.REKEY_RAD = float(cfg.get("rekey_deg", 6.9)) * DEG2RAD
        tracker.MAX_STEP_RAD = float(cfg.get("max_step_deg", 17.2)) * DEG2RAD
        tracker.ANCHOR_SPACING = float(cfg.get("anchor_spacing_deg", 12.0)) * DEG2RAD
        tracker.ANCHOR_MATCH_RANGE = float(cfg.get("anchor_match_range_deg", 25.0)) * DEG2RAD
        tracker.ANCHOR_MIN_INLIERS = int(cfg.get("anchor_min_inliers", 15))

    def run(self):
        if self.tracker is None:
            # 无摄像头: 线程立即结束, 主循环靠手动模式仍可运行
            with self.lock:
                self.status = "摄像头打开失败"
            return

        n, t0 = 0, time.perf_counter()
        while not self._stop_requested:
            # 运行期调参 (来自键盘或控制面板按钮)。
            # 同时写回 CFG: 否则设置窗口里任何一次改动都会用旧 cfg 值覆盖这里的方向/灵敏度,
            # 且设置窗口的复选框会显示与实际生效相反的状态。
            if self.manual.take_flip():
                with self.lock:
                    self.sign = -self.sign
                    sign_now = self.sign
                CFG["sign"] = sign_now
            d = self.manual.take_scale_delta()
            if d:
                with self.lock:
                    self.scale = round(max(0.1, self.scale + d), 2)
                    scale_now = self.scale
                CFG["scale"] = scale_now

            # 单帧任何异常都不能杀死识别线程 (否则效果冻结、状态停在最后一帧)
            try:
                frame = self.tracker.read()
                if frame is None:
                    with self.lock:
                        self.status = "摄像头无画面"
                    time.sleep(0.05)
                    continue
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                self.last_gray = gray

                # 标定请求
                if self.manual.take_calib():
                    ok = self.tracker.set_reference(gray)
                    with self.lock:
                        self.status = "已标定" if ok else "标定失败(特征不足)"
                    print(f"\n[标定] 基准帧 {'成功' if ok else '失败(特征点不足)'}")

                pitch_rad = self.tracker.estimate(gray)
                matches = len(self.tracker.last_good)
                with self.lock:
                    scale, sign = self.scale, self.sign
                    self.matches = matches
                    if pitch_rad is not None:
                        pitch_deg = float(np.degrees(pitch_rad))
                        fold = float(np.clip(180.0 + sign * scale * pitch_deg, 0.0, 180.0))
                        self.pitch = pitch_deg
                        self.fold = fold
                        self.conc = float(np.clip((180.0 - fold) / 180.0, 0.0, 1.0))
                        self.status = "追踪中"
                    elif not self.tracker.has_reference:
                        self.status = "未标定"
            except Exception as e:  # noqa
                with self.lock:
                    self.status = f"识别异常: {e}"
                time.sleep(0.2)

            n += 1
            now = time.perf_counter()
            if now - t0 >= 1.0:
                with self.lock:
                    self.fps = n / (now - t0)
                n, t0 = 0, now

        if self.tracker is not None and self.tracker.cap is not None:
            self.tracker.cap.release()


# ---------------------------------------------------------------- 截图线程
class CaptureWorker(threading.Thread):
    def __init__(self, region):
        super().__init__(daemon=True)
        self.region = region
        self.request = threading.Event()
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.frame = None          # (bytes, w, h, seq)
        self.busy = False

    def latest(self):
        with self.lock:
            return self.frame

    def kick(self):
        # busy 必须在锁内读: 否则 request.clear() 与 set() 交错时会丢掉一次请求
        with self.lock:
            if self.busy:
                return
        self.request.set()

    def run(self):
        seq = 0
        with mss.MSS() as sct:
            while True:
                self.request.wait()
                self.request.clear()
                self.done.clear()
                with self.lock:
                    self.busy = True
                try:
                    shot = sct.grab(self.region)
                    raw = shot.raw                     # BGRA
                    seq += 1
                    with self.lock:
                        self.frame = (raw, shot.width, shot.height, seq)
                except Exception as e:  # noqa
                    print("[capture] error:", e)
                finally:
                    with self.lock:
                        self.busy = False
                    self.done.set()


# ---------------------------------------------------------------- 控制面板 (QML)
class PanelBridge(QObject):
    """控制面板的 QML 桥接。

    面板界面在 qml/ControlPanel.qml, 用 RinUI 控件; 这里只负责状态与动作转发。
    放在本文件 (而不是 qml_bridge.py) 是为了避开循环导入 —— 它需要 ManualControl。
    """

    statusChanged = Signal()
    stateChanged = Signal()
    pinnedChanged = Signal()

    def __init__(self, manual, on_quit=None, on_settings=None, reader=None, parent=None):
        super().__init__(parent)
        self.manual = manual
        self.on_quit = on_quit
        self.on_settings = on_settings
        self.reader = reader
        self._status = "启动中…"
        self._hint = "上盖完全展开、对准有纹理的场景 → 点「标定基准帧」"
        self._win = None          # 由 ControlPanel.show() 注入
        self._pinned = False

    def attach_window(self, win):
        self._win = win

    # ---- 置顶开关 ----
    def _get_pinned(self):
        return self._pinned

    pinned = Property(bool, _get_pinned, notify=pinnedChanged)

    @Slot()
    def togglePin(self):
        """切换窗口置顶。

        改窗口 flags 后 Qt 会把窗口隐藏, 必须重新 show() 才会回来。
        """
        from PySide6.QtCore import Qt as _Qt
        if self._win is None:
            return
        self._pinned = not self._pinned
        flags = self._win.flags()
        if self._pinned:
            flags |= _Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~_Qt.WindowType.WindowStaysOnTopHint
        self._win.setFlags(flags)
        self._win.show()
        self.pinnedChanged.emit()
        self.set_status(self._status)   # 触发一次重绘

    # ---- 状态文本 ----
    def _get_status(self):
        return self._status

    status = Property(str, _get_status, notify=statusChanged)

    def set_status(self, text):
        if text != self._status:
            self._status = text
            self.statusChanged.emit()

    def _get_hint(self):
        return self._hint

    hint = Property(str, _get_hint, notify=statusChanged)

    # ---- 只读状态 (供按钮文案) ----
    def _get_scale(self):
        return float(self.reader.scale) if self.reader is not None else 1.0

    scaleValue = Property(float, _get_scale, notify=stateChanged)

    def _get_auto(self):
        return bool(self.manual.auto)

    autoMode = Property(bool, _get_auto, notify=stateChanged)

    def notify_state(self):
        self.stateChanged.emit()

    # ---- 动作 ----
    @Slot()
    def calibrate(self):
        self.manual.calib_event.set()

    @Slot()
    def flip(self):
        with self.manual.lock:
            self.manual.flip_sign = True

    @Slot(float)
    def scale(self, delta):
        with self.manual.lock:
            self.manual.scale_delta = float(delta)

    @Slot(float)
    def conc(self, v):
        with self.manual.lock:
            self.manual.auto = False
            self.manual.target = float(v)
        self.stateChanged.emit()

    @Slot()
    def toggleAuto(self):
        with self.manual.lock:
            self.manual.auto = not self.manual.auto
        self.stateChanged.emit()

    @Slot()
    def openSettings(self):
        if self.on_settings is not None:
            self.on_settings()

    @Slot()
    def quit(self):
        if self.on_quit is not None:
            self.on_quit()


def _qml_dir():
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "qml"
    return Path(__file__).parent / "qml"


class ControlPanel:
    """玻璃控制面板 (QML + RinUI 实现)。接口与原 Qt Widgets 版一致。"""

    def __init__(self, manual, on_quit=None, on_settings=None, reader=None):
        self.bridge = PanelBridge(manual, on_quit, on_settings, reader)
        self._win = None

    def show(self):
        if self._win is None:
            from RinUI import RinUIWindow
            import app_info
            self._win = RinUIWindow()
            self._win.engine.rootContext().setContextProperty("Panel", self.bridge)
            app_info.register_context(self._win.engine, CFG_PATH)
            import settings_window as _sw
            _sw._sync_rinui_theme(self._win)
            self._win.load(_qml_dir() / "ControlPanel.qml")
        w = self._win.root_window
        self.bridge.attach_window(w)
        w.show()
        self._sync_track_size(w)
        # 换到别的显示器 (不同缩放) 时边框厚度会变, 需要重新量一次
        try:
            w.screenChanged.connect(lambda *_: self._sync_track_size(w))
        except Exception:  # noqa
            pass
        return w

    # ---- 让 RinUI 上报的窗口尺寸上限落在"外框"上 (见 qml/ControlPanel.qml 顶部注释) ----
    def _sync_track_size(self, w, tries=4):
        """把实测的原生边框厚度写回 QML 的 framePadW/H。

        RinUI 的 WM_GETMINMAXINFO 把 QML 的 minimum/maximumWidth 直接当 Win32 的
        min/max track size (外框尺寸) 用, 而 Qt 给窗口加的边框没算在里面。差这一个
        边框厚度, 用户一拖动窗口就会被 Windows 按上限夹回去: 窗口突然缩小一点,
        标题栏里置顶按钮的可用宽度从 21px 掉到 8px (图标整个消失)。
        show() 之后窗口尺寸未必立刻带上边框, 所以量不到就退避重试几次。
        """
        pending = False
        for pad_key, declared_prop, axis in (("framePadW", "panelWidth", "width"),
                                             ("framePadH", "panelHeight", "height")):
            try:
                declared = int(w.property(declared_prop) or 0)
                actual = w.width() if axis == "width" else w.height()
            except Exception:  # noqa
                continue
            if declared <= 0:
                continue
            pad = actual - declared
            if pad > 0:
                try:
                    w.setProperty(pad_key, pad)
                except Exception as e:  # noqa
                    print(f"[面板] 写入 {pad_key} 失败:", e)
            else:
                pending = True
        if pending and tries > 1:
            QTimer.singleShot(120, lambda: self._sync_track_size(w, tries - 1))

    def raise_(self):
        if self._win is not None:
            self._win.root_window.show()
            self._win.root_window.raise_()

    def hide(self):
        if self._win is not None:
            self._win.root_window.hide()

    # ---- 兼容原接口 ----
    def set_status(self, text):
        self.bridge.set_status(text)

    def set_scale(self, scale):
        self.bridge.notify_state()

    def set_auto(self, auto):
        self.bridge.notify_state()



# ---------------------------------------------------------------- GL 窗口
class GlassGLWidget(QOpenGLWidget):
    def __init__(self, screen, reader, capturer, manual=None, hud=None):
        super().__init__()
        self.reader = reader
        self.capturer = capturer
        self.manual = manual
        self.hud = hud
        self.g = 0.0
        self._visible = False
        self._uploaded_seq = -1
        self._last_kick = 0.0
        self._last_print = 0.0
        self._gl_ready = False
        self._no_exclude = False
        self._timer = None

        self.refresh_hz = float(CFG.get("refresh_hz", 3))
        self.max_tilt = float(CFG.get("max_tilt_deg", 88.0)) * DEG2RAD
        self.eye_h = float(CFG.get("eye_dist_h", 2.0))
        self.spread = float(CFG.get("blur_spread", 0.42))
        self.dark = float(CFG.get("darkening", 0.001))
        self.max_taps = int(CFG.get("max_taps", 32))
        self.smoothing = float(CFG.get("smoothing", 0.22))
        self.show_threshold = float(CFG.get("show_threshold", 0.002))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(screen.geometry())
        self.setWindowTitle("duo-glass")

    def showEvent(self, _ev):
        # 关键: 把自己从屏幕捕获中排除, 否则截图会抓到上一次的渲染结果,
        # 反馈几帧后收敛成一片纯色 ("白屏" 的根因之一)
        if not self._no_exclude:
            try:
                import ctypes
                WDA_EXCLUDEFROMCAPTURE = 0x11
                r = ctypes.windll.user32.SetWindowDisplayAffinity(
                    int(self.winId()), WDA_EXCLUDEFROMCAPTURE)
                if not r:
                    print("[警告] SetWindowDisplayAffinity 失败, 截图可能包含自身")
            except Exception as e:  # noqa
                print("[警告] 显示排除设置异常:", e)

        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.tick)
            self._timer.start(16)

    # ---------- 参数热更新 (设置窗口调用) ----------
    def apply_config(self, cfg):
        """从 cfg 重新读取渲染参数, 立即生效 (不需要重启)。"""
        self.refresh_hz = float(cfg.get("refresh_hz", 3))
        self.max_tilt = float(cfg.get("max_tilt_deg", 62.0)) * DEG2RAD
        self.eye_h = float(cfg.get("eye_dist_h", 2.0))
        self.spread = float(cfg.get("blur_spread", 0.42))
        self.dark = float(cfg.get("darkening", 0.001))
        self.max_taps = int(cfg.get("max_taps", 32))
        self.smoothing = float(cfg.get("smoothing", 0.22))
        self.show_threshold = float(cfg.get("show_threshold", 0.002))

    # ---------- GL (core profile: VAO/VBO, 见 shaders.py) ----------
    def initializeGL(self):
        # 任何异常都不能逃出去: Python 绑定对槽内未捕获异常会直接 abort() 进程。
        try:
            self.prog = gl_core.compile_program()
            self.vao, _ = gl_core.make_quad()
            self.cap_tex = gl_core.make_texture()
        except Exception as e:  # noqa
            # 关键: 失败后绝不能让窗口显示 —— 未绘制的 QOpenGLWidget 会合成成
            # 不透明全屏纯黑, 把用户的桌面整个盖住 (只能杀进程)。
            self.prog = None
            self._gl_ready = False
            self._gl_error = str(e)
            print("[GL] 初始化失败, 叠加层已禁用:", e)
            return
        self._gl_error = None
        self._gl_ready = True

    def paintGL(self):
        if not self._gl_ready:
            # 不绘制, 但也不能让 Qt 合成出不透明黑: 清成透明并请求隐藏 (见 tick)。
            GL.glClearColor(0.0, 0.0, 0.0, 0.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            return
        dpr = self.devicePixelRatioF()
        w = max(1, int(self.width() * dpr))
        h = max(1, int(self.height() * dpr))

        frame = self.capturer.latest()
        if frame and frame[3] != self._uploaded_seq:
            raw, fw, fh, seq = frame
            gl_core.upload_bgra(self.cap_tex, raw, fw, fh)
            self._uploaded_seq = seq

        if self._uploaded_seq == -1 or frame is None:
            GL.glClearColor(0, 0, 0, 1)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            return

        GL.glViewport(0, 0, w, h)
        GL.glUseProgram(self.prog)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.cap_tex)
        gl_core.set_uniforms(
            self.prog, frame[1], frame[2],
            tilt=self.g * self.max_tilt,
            eye_z=self.eye_h * frame[2],
            spread=self.spread, dark=self.dark, max_taps=self.max_taps,
        )
        gl_core.draw_quad(self.vao)

    # ---------- 主循环 ----------
    def tick(self):
        if self.manual is not None and self.manual.quit_flag:
            QApplication.quit()
            return

        target_m, _key, auto = self.manual.get() if self.manual is not None else (0.0, "", True)
        conc, fold, pitch, fps, status = (
            self.reader.get() if self.reader is not None else (0.0, 180.0, 0.0, 0.0, "manual"))

        if getattr(self, "_freeze", False):
            # 冒烟/调试: 冻结浓度, 忽略角度来源 (仍走显隐与刷新逻辑)
            mode = "演示"
            target = self.g
        elif auto and self.reader is not None:
            target = conc
            mode = "角度自动"
        else:
            target = target_m
            mode = "手动"

        # 连续控制: 平滑跟随 (褶皱可停在任意角度)
        if not getattr(self, "_freeze", False):
            self.g += (target - self.g) * self.smoothing
            if self.g < 1e-4:
                self.g = 0.0

        # 只在起效时显示: 不折叠时隐藏窗口, 桌面保持原生清晰
        # GL 初始化失败时必须永不显示 —— 未绘制的 QOpenGLWidget 会合成成全屏不透明黑。
        # 另外要等到有帧再显示, 否则 mss 首帧 (~50ms) 落地前会先闪一帧不透明黑。
        gl_broken = not self._gl_ready
        want = (not gl_broken) and (self.g > self.show_threshold or target > self.show_threshold)
        if want:
            self.capturer.kick()          # 先请求抓帧, 帧到了才 show
            have_frame = self.capturer.latest() is not None
            want = have_frame
        if want != self._visible:
            self._visible = want
            if want:
                self.show()
                # 叠加层是 WindowStaysOnTop 且不透明, 会把控制面板压在下面
                # (面板区域被盖成黑块/重糊)。每次显示后把面板重新置顶。
                if self.hud is not None:
                    self.hud.raise_()
            else:
                self.hide()

        if self._visible:
            now = time.time()
            if self.refresh_hz > 0 and now - self._last_kick >= 1.0 / self.refresh_hz:
                self._last_kick = now
                self.capturer.kick()
            self.update()

        # 控制台实时单行重绘 + 控制面板刷新。
        # 输出被重定向到日志文件时 (_QUIET_STDOUT, 即打包后的无控制台模式) 不打印状态行,
        # 否则日志会以 10Hz 无限膨胀; 状态仍显示在屏幕上的控制面板里。
        interval = 1.0 if _QUIET_STDOUT else 0.1
        if time.time() - self._last_print > interval:
            self._last_print = time.time()
            if gl_broken:
                msg = f"OpenGL 初始化失败，效果已禁用：{getattr(self, '_gl_error', '未知错误')}"
                print(f"[错误] {msg}")
                if self.hud is not None:
                    self.hud.set_status(msg)
                return
            if self.reader is not None:
                if not _QUIET_STDOUT:
                    print(f"\r[{mode}] fold={fold:5.1f}° pitch={pitch:+6.2f}° "
                          f"浓度={self.g*100:5.1f}% [m={self.reader.matches} {status} {fps:3.0f}Hz] "
                          f"[面板按钮: 标定/翻转/切自动]  +/- 灵敏度  Esc 退出   ", end="", flush=True)
                if self.hud is not None:
                    self.hud.set_status(
                        f"[{mode}]  fold={fold:5.1f}°   浓度={self.g*100:4.1f}%\n"
                        f"matches={self.reader.matches}   {fps:.0f}Hz   {status}")
                    self.hud.set_scale(self.reader.scale)
                    self.hud.set_auto(auto)
            else:
                if not _QUIET_STDOUT:
                    print(f"\r[{mode}] 玻璃={self.g*100:5.1f}%  "
                          f"[↑↓调节 ←清空 →拉满  Esc 退出]   ", end="", flush=True)
                if self.hud is not None:
                    self.hud.set_status(f"[{mode}]  玻璃={self.g*100:4.1f}%")
                    self.hud.set_auto(auto)


# ---------------------------------------------------------------- 自检
def run_selftest():
    print("=" * 62)
    print("自检: 摄像头 / ORB 标定 / 截屏 / OpenGL")
    print("-" * 62)
    ok = True
    cam_ok = orb_ok = cap_ok = gl_ok = False

    # 1. 摄像头 + ORB 标定
    manual = ManualControl(auto=False)
    reader = CameraAngleReader(manual)
    reader.start()
    time.sleep(2.5)
    if reader.tracker is None:
        print(f"  摄像头 : FAIL  {reader.tracker_error}")
        ok = False
        reader.stop()
        reader.join(timeout=2.0)
    else:
        conc, fold, pitch, fps, status = reader.get()
        if reader.last_gray is None:
            print("  摄像头 : FAIL  没有读到画面 (被占用? 或 index 不对)")
            ok = False
        else:
            h, w = reader.last_gray.shape[:2]
            cam_ok = True
            print(f"  摄像头 : OK    {w}x{h}, {fps:.0f}Hz")
            # 先停线程再标定: 否则主线程与 reader 线程并发改 ref_*/anchors/total_rad
            reader.stop()
            reader.join(timeout=2.0)
            ref_ok = reader.tracker.set_reference(reader.last_gray)
            n = len(reader.tracker.ref_kp) if reader.tracker.ref_kp is not None else 0
            if ref_ok:
                orb_ok = True
                print(f"  ORB    : OK    基准帧特征点 {n} 个")
            else:
                print(f"  ORB    : FAIL  特征点不足 ({n}), 换个有纹理的场景再试")
                ok = False
        if reader.is_alive():
            reader.stop()
            reader.join(timeout=2.0)

    # 2. 截屏
    worker = CaptureWorker(screen_region())
    worker.start()
    worker.kick()
    worker.done.wait(timeout=5)
    frame = worker.latest()
    if frame is None:
        print("  截屏   : FAIL  mss 抓帧失败")
        ok = False
    else:
        cap_ok = True
        print(f"  截屏   : OK    {frame[1]}x{frame[2]}")

    # 3. GL (core profile, 与真实窗口一致; 本机 Intel 驱动只给 forward-compatible 上下文)
    try:
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext
        fmt = _make_format()
        surf = QOffscreenSurface()
        surf.setFormat(fmt)
        surf.create()
        ctx = QOpenGLContext()
        ctx.setFormat(fmt)
        if not (ctx.create() and ctx.makeCurrent(surf)):
            raise RuntimeError("上下文创建失败")
        gl_core.compile_program()   # 编译不过会抛 RuntimeError
        gl_ok = True
        f = ctx.format()
        print(f"  OpenGL : OK    {GL.glGetString(GL.GL_VERSION).decode()} "
              f"({f.profile().name}) 着色器编译链接通过")
    except Exception as e:  # noqa
        print(f"  OpenGL : FAIL  {e}")
        ok = False

    # 4. RinUI 组件库与其图标字体 (设置窗口/控制面板依赖它)
    try:
        import RinUI  # noqa
        from pathlib import Path as _P
        _fonts = _P(RinUI.__file__).parent / "assets" / "fonts"
        _ttf = _fonts / "FluentSystemIcons-Resizable.ttf"
        _idx = _fonts / "FluentSystemIcons-Index.js"
        if _ttf.exists() and _idx.exists():
            print(f"  RinUI  : OK    {RinUI.__version__}  图标字体已就绪")
            icon_ok = True
        else:
            print("  RinUI  : FAIL  图标字体缺失")
            ok = False
    except Exception as e:  # noqa
        print(f"  RinUI  : FAIL  {e}")
        ok = False
    except Exception as e:  # noqa
        print(f"  图标   : FAIL  {e}")
        ok = False

    print("-" * 62)
    print(f"  => {'PASS' if ok else 'FAIL'}")
    print("=" * 62)

    # 打包成 --windowed EXE 时没有控制台, 结果只在日志里等于用户看不到, 所以弹窗。
    if getattr(sys, "frozen", False):
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                None, "自检结果",
                f"摄像头: {'OK' if cam_ok else 'FAIL'}\n"
                f"特征识别: {'OK' if orb_ok else 'FAIL'}\n"
                f"屏幕截取: {'OK' if cap_ok else 'FAIL'}\n"
                f"OpenGL: {'OK' if gl_ok else 'FAIL'}\n\n"
                f"总体: {'通过' if ok else '未通过'}\n\n"
                f"详细日志: {app_info.LOG_NAME}")
        except Exception:  # noqa
            pass
    return 0 if ok else 1


def screen_region():
    """mss 抓屏区域 (物理像素)。

    Qt 的 geometry() 是逻辑坐标, mss 要物理像素, 所以**四个分量都要乘 dpr**。
    只乘宽高会让非 (0,0) 原点的主屏 (外接屏在左侧/上方) 抓错区域。
    """
    app = QApplication.instance() or QApplication(sys.argv)
    screen = app.primaryScreen()
    dpr = screen.devicePixelRatio()
    geom = screen.geometry()
    return {"left": int(geom.x() * dpr), "top": int(geom.y() * dpr),
            "width": int(geom.width() * dpr), "height": int(geom.height() * dpr)}


# ---------------------------------------------------------------- 入口
def main():
    smoke = "--smoke" in sys.argv
    selftest = "--selftest" in sys.argv
    manual_mode = "--manual" in sys.argv

    fmt = _make_format()
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    # 任务栏图标 + AppUserModelID: 必须在建窗口之前设, 否则任务栏那一格会一直是
    # python.exe 的图标 (Windows 缓存了首个窗口的图标)。
    app_info.apply_app_icon(app)

    if selftest:
        return run_selftest()

    screen = app.primaryScreen()
    geom = screen.geometry()
    region = screen_region()

    kb = ManualControl(auto=not manual_mode)
    kb.start()

    reader = None
    if manual_mode:
        print("[手动模式] 不连接摄像头")
    else:
        reader = CameraAngleReader(kb)
        reader.start()
        time.sleep(0.5)

    capturer = CaptureWorker(region)
    capturer.start()

    print("=" * 62)
    print(f"{app_info.APP_NAME} · 摄像头驱动「悬浮玻璃」")
    print(f"  铰链=屏幕底边  最大转角 {CFG.get('max_tilt_deg')}°  眼距 {CFG.get('eye_dist_h')}x屏高")
    print(f"  blur_spread={CFG.get('blur_spread')}  darkening={CFG.get('darkening')}  "
          f"taps<={CFG.get('max_taps')}  scale={CFG.get('scale')} sign={CFG.get('sign')}")
    print("-" * 62)
    if not manual_mode:
        print("  上盖完全展开、对着有纹理的静止场景, 点面板「标定基准帧」, 再慢慢开合。")
        print("  不折叠时叠加层自动隐藏; 合盖才浮出玻璃效果。")
    print("  面板按钮: 标定 / 翻转方向 / 切自动 / 浓度 / 设置 / 退出")
    print("=" * 62)

    # 设置窗口: 改动实时生效 (写 CFG + 通知两个线程与渲染窗口)
    settings = {"win": None}

    def apply_cfg(cfg):
        widget.apply_config(cfg)
        if reader is not None:
            reader.apply_config(cfg)

    def open_settings():
        if settings["win"] is None:
            settings["win"] = SettingsWindow(CFG, apply_cfg)
        w = settings["win"]
        w.refresh_from_cfg()
        w.show()
        w.raise_()
        w.activateWindow()
        # 窗口材质 (圆角/明暗标题栏/云母) 由 SettingsWindow.showEvent 自己处理

    panel = ControlPanel(kb, on_quit=app.quit, on_settings=open_settings,
                         reader=reader)
    panel.show()

    widget = GlassGLWidget(screen, reader, capturer, manual=kb, hud=panel)
    widget.show()          # 触发 showEvent: 自排除 + 启动定时器
    widget._visible = True

    if smoke:
        # 调试: 保留自排除 (mss 抓到的是叠加层背后的真实桌面, 不被自身污染),
        # 冻结浓度, 2.5s 后抓自身 framebuffer 存 PNG 自退
        widget.refresh_hz = 0.0
        widget._freeze = True
        widget.g = 0.85
        widget.show()

        def dump_and_quit():
            try:
                img = widget.grabFramebuffer()
                out = str(Path(__file__).with_name("smoke_widget.png"))
                img.save(out)
                print(f"\n[smoke] grabFramebuffer -> {out} ({img.width()}x{img.height()})")
            except Exception as e:  # noqa
                print("\n[smoke] grabFramebuffer 失败:", e)
            app.quit()

        QTimer.singleShot(2500, dump_and_quit)
    else:
        # 正常模式: 立即按当前浓度决定显隐
        widget.tick()

    capturer.kick()
    rc = app.exec()
    if reader is not None:
        reader.stop()
        reader.join(timeout=2.0)
    kb.quit_flag = True
    print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
"""QML ↔ config.json 的桥接层。

QML 侧用法:
    Slider { Component.onCompleted: value = Config.get("max_tilt_deg")
             onMoved: Config.set("max_tilt_deg", value) }

设计:
  - 改动**立即生效** (写入 CFG 并通知主程序热更新), 磁盘写入做 300ms 防抖,
    避免拖动滑块时每帧都写文件。
  - 「恢复默认」回到代码里的出厂默认值 (不是本次启动时的值)。
"""
import json
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

# 出厂默认值 (与 config.json 的初始内容一致)
DEFAULTS = {
    "camera_index": 0, "nfeatures": 1200, "ratio": 0.75,
    "min_matches": 12, "rekey_deg": 6.9, "max_step_deg": 17.2,
    "anchor_spacing_deg": 12.0, "anchor_match_range_deg": 25.0,
    "anchor_min_inliers": 15,
    "scale": 1.1, "sign": -1,
    "refresh_hz": 3, "max_tilt_deg": 62.0, "eye_dist_h": 2.0,
    "blur_spread": 0.42, "darkening": 0.001, "max_taps": 32,
    "smoothing": 0.22, "show_threshold": 0.002,
}

INT_KEYS = ("max_taps", "camera_index", "refresh_hz", "min_matches",
            "nfeatures", "anchor_min_inliers")


class ConfigBridge(QObject):
    """把配置暴露给 QML, 并负责热更新 + 防抖存盘。"""

    statusChanged = Signal()
    valuesChanged = Signal()     # 值被批量改动 (恢复默认) 时通知 QML 重读

    def __init__(self, cfg, cfg_path, on_apply, on_saved=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.cfg_path = Path(cfg_path)
        self.on_apply = on_apply
        self.on_saved = on_saved
        self._status = "改动立即生效，并自动保存"
        self._dirty = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(300)
        self._save_timer.timeout.connect(self._flush)

    # ---------- 状态文本 ----------
    def _get_status(self):
        return self._status

    status = Property(str, _get_status, notify=statusChanged)

    def _set_status(self, text):
        if text != self._status:
            self._status = text
            self.statusChanged.emit()

    # ---------- 读写 ----------
    @Slot(str, result="QVariant")
    def get(self, key):
        return self.cfg.get(key, DEFAULTS.get(key, 0))

    @Slot(str, result=float)
    def getNum(self, key):
        try:
            return float(self.cfg.get(key, DEFAULTS.get(key, 0)))
        except (TypeError, ValueError):
            return float(DEFAULTS.get(key, 0))

    @Slot(str, result=bool)
    def getBool(self, key):
        try:
            return bool(float(self.cfg.get(key, DEFAULTS.get(key, 0))) > 0)
        except (TypeError, ValueError):
            return False

    @Slot(str, result=str)
    def getStr(self, key):
        return str(self.cfg.get(key, DEFAULTS.get(key, "")))

    @Slot(str, "QVariant")
    def set(self, key, value):
        if key in INT_KEYS:
            try:
                value = int(round(float(value)))
            except (TypeError, ValueError):
                return
        self.cfg[key] = value
        try:
            self.on_apply(self.cfg)
        except Exception as e:  # noqa
            self._set_status(f"应用失败：{e}")
            return
        self._dirty = True
        self._save_timer.start()
        self._set_status(f"已更新 {key} = {value}")

    # ---------- 存盘 ----------
    def _flush(self):
        if not self._dirty:
            return
        try:
            self.cfg_path.write_text(
                json.dumps(self.cfg, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            self._dirty = False
            self._set_status("已自动保存到 config.json")
            if self.on_saved is not None:
                self.on_saved()
        except Exception as e:  # noqa
            self._set_status(f"保存失败：{e}")

    # ---------- 供 QML 调用的动作 ----------
    @Slot()
    def resetDefaults(self):
        for k, v in DEFAULTS.items():
            self.cfg[k] = v
        try:
            self.on_apply(self.cfg)
        except Exception:  # noqa
            pass
        self._dirty = True
        self._flush()
        self.valuesChanged.emit()
        self._set_status("已恢复出厂默认值")

    @Slot()
    def saveNow(self):
        self._dirty = True
        self._flush()

    @Slot(result=str)
    def configName(self):
        return self.cfg_path.name

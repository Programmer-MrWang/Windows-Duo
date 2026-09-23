"""Windows Duo · 摄像头驱动「悬浮玻璃」启动器。

等价于直接运行 glass_overlay.py, 保留 `python main.py` 的使用习惯:
    python main.py              摄像头驱动
    python main.py --manual     键盘手动 (无需摄像头)
    python main.py --selftest   无窗口自检
    python main.py --smoke      4s 演示后自退并抓帧
"""
import sys

from glass_overlay import main

if __name__ == "__main__":
    sys.exit(main())
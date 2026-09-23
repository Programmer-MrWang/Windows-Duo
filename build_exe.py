"""打包成单文件 EXE (PyInstaller 包装器)。

用法:
    python build_exe.py

产物: dist/WindowsDuo.exe —— **dist/ 里只有这一个文件**。
      配置文件 / 运行日志 / RinUI 主题状态都在首次运行时由程序自己生成在 EXE 旁边,
      使用说明在程序内「设置 → 关于」, 所以发布目录不需要附带任何其它文件。

要点:
  - EXE 名取自 app_info.py (APP_SLUG), 不在这里另写一份, 否则改名时必有一处漏掉。
  - --windowed: 不弹控制台窗口 (双击直接运行)。
    代价是键盘快捷键收不到 (msvcrt 读不到控制台) —— 所以控制面板的按钮是
    完整功能的操作入口, 这也是当初把操作按钮化的原因。
  - config.json 不打包进 EXE, 也不随发布目录附带: 程序发现没有就按出厂默认值生成
    一份放在 EXE 旁边 (用户要能编辑它, 程序也要能把「保存为默认」写回去)。
  - 图标有两份: assets/ 里的显示用图标随包 (关于页要读), EXE 图标由 --icon 写进
    可执行文件的资源段。两份都从根目录的 icon.png 生成, 见 _ensure_assets()。
  - 排除用不到的重型模块 (matplotlib/scipy/tkinter 等), 显著缩小体积。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app_info import APP_LICENSE, APP_NAME, APP_ORG, APP_SLUG, APP_VERSION

ROOT = Path(__file__).parent
NAME = APP_SLUG
ASSETS = ROOT / "assets"

# EXE 与任务栏要用的所有尺寸。只有 256 一份的话, Windows 缩小到 16/32 会明显发糊。
ICO_SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48),
             (64, 64), (128, 128), (256, 256)]


def _ensure_assets():
    """从根目录的 icon.png 生成 assets/ 下的两份派生素材。

    assets/icon.png  256px —— QML 与运行时窗口图标用 (原图 2017px/4.6MB, 太大)
    assets/icon.ico  多尺寸 —— EXE 图标与任务栏用

    已经存在且不比原图旧就跳过, 免得每次打包都重跑一遍缩放。
    两份派生物是入库的 —— 根目录原图不入库 (太大), 所以这里找不到原图时
    直接沿用已提交的 assets/, 保证 clone 下来也能打出一个带图标的 EXE。
    """
    global ICO
    src = ROOT / "icon.png"
    png, ico = ASSETS / "icon.png", ASSETS / "icon.ico"
    if not src.exists():
        ICO = ico if ico.exists() else (png if png.exists() else None)
        print(f"[build] 根目录没有 icon.png, 沿用已提交的 assets/ "
              f"({'icon.ico' if ico.exists() else 'icon.png' if png.exists() else '无'})")
        return
    if png.exists() and ico.exists() and ico.stat().st_mtime >= src.stat().st_mtime:
        print("[build] assets/ 图标已是最新, 跳过生成")
        ICO = ico
        return

    try:
        from PIL import Image
    except ImportError:
        print("[build] 没装 Pillow, 跳过图标生成 (EXE 将用默认图标)")
        ICO = ico if ico.exists() else None
        return

    ASSETS.mkdir(exist_ok=True)
    im = Image.open(src).convert("RGBA")
    im.resize((256, 256), Image.LANCZOS).save(png, optimize=True)
    im.save(ico, format="ICO", sizes=ICO_SIZES)
    print(f"[build] 已生成 assets/icon.png (256px) 与 assets/icon.ico "
          f"({len(ICO_SIZES)} 种尺寸)")
    ICO = ico


def _version_file():
    """生成 PyInstaller 的版本资源文件 —— EXE 属性对话框里那份信息。

    版本号/名称/版权都取自 app_info, 与「关于」页显示的是同一个值。
    (StringTable 的键 '080404B0' = 简体中文(0x0804) + Unicode(0x04B0)。)
    """
    nums = [int(x) for x in APP_VERSION.split(".") if x.isdigit()][:4]
    nums += [0] * (4 - len(nums))
    ver = tuple(nums)
    path = ROOT / "build" / "version_info.txt"
    path.parent.mkdir(exist_ok=True)
    path.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={ver}, prodvers={ver}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('080404B0', [
        StringStruct('CompanyName', '{APP_ORG}'),
        StringStruct('FileDescription', '{APP_NAME}'),
        StringStruct('FileVersion', '{APP_VERSION}'),
        StringStruct('InternalName', '{NAME}'),
        StringStruct('LegalCopyright', '{APP_ORG} · {APP_LICENSE}'),
        StringStruct('OriginalFilename', '{NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{APP_VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])]
)
""", encoding="utf-8")
    return path


ICO = None


def main():
    _ensure_assets()
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed",                  # 无控制台
        "--name", NAME,
        # spec 是中间产物, 丢进 build/ 别放在仓库根目录碍事
        "--specpath", str(ROOT / "build"),
        # 版本资源: 右键 EXE -> 属性 -> 详细信息 里看到的那份
        "--version-file", str(_version_file()),
        # 项目自带的模块, 显式声明保证被收集
        "--hidden-import", "gl_core",
        "--hidden-import", "shaders",
        "--hidden-import", "tracker",
        "--hidden-import", "settings_window",
        "--hidden-import", "qml_bridge",
        "--hidden-import", "win_theme",
        "--hidden-import", "app_info",
        "--hidden-import", "RinUI",
        # QML 界面必须随包 (settings_window 从 sys._MEIPASS/qml 读)
        "--add-data", f"{ROOT / 'qml'}{os.pathsep}qml",
        # assets/ 也要随包: 关于页的应用图标、运行时窗口图标都从 _MEIPASS/assets 读
        "--add-data", f"{ASSETS}{os.pathsep}assets",
        # RinUI 的 QML 模块与图标字体由 --collect-all 收进包
        *("--collect-all", "RinUI"),
        # 去掉用不到的重型依赖。
        # 注意: QtQml / QtQuick / QtQuickControls 不能排除 —— 设置窗口和控制面板
        # 是 QML 写的, 排除掉直接起不来 (PyQt6 时代它们才是累赘)。
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "tkinter",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.QtMultimedia",
        "--exclude-module", "PySide6.QtBluetooth",
        "--exclude-module", "PySide6.QtDesigner",
        "--exclude-module", "PySide6.QtSql",
        "--exclude-module", "PySide6.QtTest",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "PySide6.QtCharts",
        # 入口
        str(ROOT / "main.py"),
    ]
    # EXE 图标写进可执行文件的资源段 (资源管理器/任务栏/开始菜单都读这里)
    if ICO is not None and ICO.exists():
        args[args.index("--name"): args.index("--name")] = ["--icon", str(ICO)]
    else:
        print("[build] 警告: 没有可用的 .ico, EXE 将使用 PyInstaller 默认图标")

    print("[build] " + " ".join(args[1:6]) + " ...")
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        print("[build] 失败")
        return r.returncode

    out_dir = ROOT / "dist"
    exe = out_dir / f"{NAME}.exe"
    if not exe.exists():
        print(f"[build] 没找到产物 {exe}")
        return 1
    # dist/ 里只留 EXE: 配置、日志、RinUI 主题都在首次运行时由程序自己生成,
    # 说明书就在程序内「设置 → 关于」, 没必要再往发布目录里塞文件。
    for stale in ("使用说明.txt", "config.json", "FoldableGlassSim.exe",
                  "windows_duo.log", "foldable_glass.log"):
        p = out_dir / stale
        if p.exists():
            p.unlink()
            print(f"[build] 清掉多余文件: {stale}")
    rinui_dir = out_dir / "RinUI"        # 运行时生成的主题状态, 不属于产物
    if rinui_dir.exists():
        shutil.rmtree(rinui_dir, ignore_errors=True)
        print("[build] 清掉多余目录: RinUI/")

    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"\n[build] 完成: {exe}  ({size_mb:.1f} MB)")
    print(f"[build] {out_dir.name}/ 里只有这一个文件; config.json / 日志 / 主题状态"
          f"都在首次运行时自动生成")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# AGENTS.md — AI 协作指南

面向在本仓库工作的 AI 编码代理（与人类贡献者）。改动前请先读完本文件，避免踩已知的坑。

## 项目是什么

本项目名为 **Windows Duo**（无空格写法 `WindowsDuo` 用于 EXE 名 / 日志名 / 打包名）。
名称与版本集中在 `app_info.py`：改 `APP_NAME` / `APP_SLUG` 就改了界面、EXE、日志、
任务栏四处；改 `APP_VERSION` 就同时改了「关于」页、页脚、EXE 版本资源（`--version-file`）。

> **别把两个名字搞混**：上游开源项目叫 **WindowsDuo**（`KaedeharaKazuha1029/WindowsDuo`，
> 串口 MPU6050 版，MIT），本项目是它的摄像头版复刻。文档里凡是 `WindowsDuo` 都是指上游，
> 指本项目时一律写 `Windows Duo`。

在 Windows 笔记本上复刻 iPhone Duo「悬浮玻璃」效果；**角度来源是笔记本上盖摄像头**，
无需任何外接硬件（这是与上游 WindowsDuo 的唯一本质区别）。

- **角度侧**（`tracker.py`）：摄像头 → ORB 特征匹配 + 纯旋转拟合 → 上盖俯仰角（弧度）。
  滑动关键帧 + 固定锚点校正消除漂移，One Euro 滤波平滑。
- **渲染侧**（`glass_overlay.py` / `shaders.py` / `gl_core.py`）：PyQt6 `QOpenGLWidget`
  全屏置顶透明叠加层，GLSL 逆投影 Duo 折叠着色器（铰链 = 屏幕底边，间隙越大越模糊越暗，
  视线出界纯黑）。鼠标穿透（`WindowTransparentForInput`），不影响桌面使用。

## 目录结构

```
tracker.py            角度识别: OneEuroFilter + AngleTracker (ORB + 锚点校正)
glass_overlay.py      主程序: CameraAngleReader + CaptureWorker + GlassGLWidget + PanelBridge
shaders.py            GLSL 着色器 (330 core) + 全屏四边形顶点数据
gl_core.py            Core profile GL 样板: 编译着色器 / VAO+VBO / 纹理上传 / 设 uniform
settings_window.py    设置窗口启动器 (QML 入口, 接口与原 QWidget 版一致)
qml_bridge.py         QML <-> config.json 的桥接 (读写/热更新/防抖存盘/恢复默认)
qml/Settings.qml      FluentWindow + 导航栏 (RinUI)
qml/pages/*.qml       5 个设置页 (FluentPage + SettingCard + Slider/ComboBox/CheckBox)
qml/ControlPanel.qml  玻璃控制面板 (RinUI 轻量 Window)
qml/components/       可复用卡片 (SliderField)
win_theme.py          Windows 主题集成: 明暗/主题色 -> 同步给 RinUI
config.json           全部运行参数 (唯一参数入口)
app_info.py           应用元信息: 名称/版本/图标路径 + QML 桥 App (标题栏·任务栏·EXE 图标同源)
assets/               应用图标 (icon.png 256px + icon.ico 多尺寸, 由 build_exe.py 从根目录 icon.png 生成)
offscreen_test.py     离屏渲染验证着色器 (不出窗口, 出 PNG)
build_exe.py          打包成单文件 EXE (PyInstaller 包装器)
run_overlay.bat       摄像头驱动启动  /  run_manual.bat  纯键盘启动
main.py               启动器 (python main.py [--manual|--selftest|--smoke])
```

## 技术栈

与 Class-Widgets 的设置窗口**同框架、同控件库**:

| 层 | 用什么 |
|---|---|
| Qt 绑定 | **PySide6** (Qt 官方) |
| 界面 | **QML / Qt Quick** (声明式, GPU 场景图) |
| 组件库 | **RinUI** (FluentWindow / NavigationView / SettingCard / Slider …) |
| 主题 | RinUI 自带 Mica + 明暗; 主色由 `win_theme` 从 Windows 取后覆盖 |
| 叠加层 | 仍是 PySide6 的 QOpenGLWidget + GLSL (核心功能, 不能换成 QML) |

## 运行

```
python main.py              摄像头驱动
python main.py --manual     键盘手动 (无需摄像头)
python main.py --selftest   无窗口自检 (摄像头 / ORB / 截屏 / OpenGL)
python main.py --smoke      2.5s 演示后自退并抓帧存 smoke_widget.png
python offscreen_test.py 60 离屏渲染着色器出图 offscreen_result.png
python build_exe.py         打包成 dist/WindowsDuo.exe
```

## 已知坑（改代码前必读）

1. **本机 Intel 驱动只提供 forward-compatible 上下文**：即使请求 `CompatibilityProfile`，
   实测 `GL_VERSION=3.3.0` 下 `gl_MultiTexCoord0` / `gl_ModelViewProjectionMatrix` /
   `gl_Vertex` / `varying` 全部编译失败（报 "removed in Forward Compatible context"）。
   所以**必须用 330 core + VAO/VBO 显式属性**，不能照抄 WindowsDuo win 端的
   compatibility 写法。着色器数学与它逐行一致，见 `shaders.py`。
   排查手法：离屏上下文里用原始 `glCreateShader` 编译一段 compat 着色器，看报错。

2. **GL 窗口必须继承 `QOpenGLWidget`**（`PyQt6.QtOpenGLWidgets`）。继承普通 `QWidget`
   时 `initializeGL/paintGL` 永远不会被调用，窗口只会显示默认底色——这是上游项目最大的历史坑。

3. **截图反馈污染**：Overlay 是不透明置顶窗口，mss 截屏会抓到自己上一帧，几帧后收敛成纯色。
   靠 `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE=0x11)` 把自己排除出捕获
   （见 `showEvent`）。改截图逻辑时别动它。`--smoke` 也不要关掉自排除，否则抓到的帧是黑的。

4. **`max_tilt_deg` 不要盲目照抄 88°**：角度接近 90° 时视线绝大部分出界，画面几乎全黑
   （物理正确，但观感像黑幕）。默认 62° 让效果全程可见。
   验证手法：`python offscreen_test.py 75` 会看到近乎全黑，`python offscreen_test.py 53` 正常。

5. **`_stop` 是 `threading.Thread` 的保留名**：自定义线程的停止标志要用 `_stop_requested`
   之类的名字，否则覆盖 `Thread._stop()` 会让 `join()` 抛 `TypeError`。

6. **`.bat` 里不要写裸 `python`**：本机 PATH 里 `WindowsApps` 有一个 **0 字节的
   Microsoft Store 占位符 `python.exe`**，裸调用可能命中它并报
   "程序 python.exe 无法运行: 系统找不到指定的路径"。bat 里用
   `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` 绝对路径（并保留 `py` 兜底）。

7. **未标定时必须有可见反馈 + 不依赖控制台操作**：玻璃叠加层按设计在浓度≈0 时隐藏，
   若不给任何屏幕提示，用户启动后会"什么都看不到"，误以为程序坏了。`ControlPanel`
   （左上角带按钮的小窗）就是为此存在：它显示状态，并把**全部操作做成按钮**。
   两个约束不能动：
   - 面板**不要加 `Qt.WindowType.Tool`**：Tool 窗口在 Windows 上不进 Alt+Tab、也难获焦，
     用户会"找不到窗口"。必须是普通 `Qt.WindowType.Window`。
   - 键盘走 `msvcrt.getwch()` 读**控制台**；当程序被重定向/无控制台启动时，键盘收不到键。
     所以按钮必须覆盖 100% 功能（标定/翻转/灵敏度/浓度/切自动/退出），不能只做键盘的补充。

8. **GL 初始化失败会让叠加层变成全屏不透明黑**：`QOpenGLWidget` 在 `paintGL` 未绘制时，
   Qt 合成出的是**不透明黑**。所以 `initializeGL` 必须捕获 `Exception`（不只是
   `RuntimeError`）并置 `_gl_ready=False`，且 `tick()` 里 `want` 要带上
   `not gl_broken` —— 否则着色器一编译失败，用户合盖就得到一块全屏黑幕，只能杀进程。

9. **首个抓帧落地前不能 show()**：mss 抓一帧 2560x1600 要 ~50ms，而定时器是 16ms。
   若先 `show()` 再等帧，会先闪一帧不透明黑。正确顺序：`kick()` → 检查
   `capturer.latest() is not None` → 再 `show()`。

10. **控制面板会被叠加层盖住**：叠加层是 `WindowStaysOnTopHint` 且不透明，会把面板压到
    下面（面板区域变成黑块 + 被重糊）。每次叠加层 `show()` 之后要 `self.hud.raise_()`；
    面板自身也要 `SetWindowDisplayAffinity` 排除出捕获，否则它的像素被抓进纹理再画一遍。

11. **键盘的绝对量 vs 增量不能用 `abs(delta)>=0.5` 猜**：清零的值是 `0.0`，
    `abs(0.0) >= 0.5` 为假会被当成"增量 0"从而完全无效。要在映射表里显式带
    `(值, 是否绝对量)` 标记。

12. **面板/键盘修正的参数必须写回 CFG**：否则设置窗口里任何一次改动都会用旧的 cfg 值
    覆盖掉用户刚做的翻转/灵敏度修正（`apply_config` 是按 cfg 绝对值覆盖的）。

13. **`min_matches` 不能低于 4**：`cv2.findHomography` 至少要 4 个点，否则抛
    `cv2.error` 而不是返回 None。`tracker._match_and_rotate` 里用
    `max(4, MIN_MATCHES)` 兜底，且 `CameraAngleReader.run()` 每轮要有 try/except，
    否则识别线程会被异常静默杀死、效果冻结。

14. **打包成 `--windowed` EXE 后 `print` 会崩**：没有控制台时 `sys.stdout` 不可用或指向
    GBK 流，任何非 GBK 字符（如 `✔`）抛 `UnicodeEncodeError` 直接中止程序。见文件顶部
    `_stdout_broken()`：只在真正没有可用控制台时才把输出重定向到 UTF-8 日志，
    并置 `_QUIET_STDOUT` 关掉 10Hz 状态行（否则日志无限膨胀）。

15. **config.json 必须放在 EXE 旁边，不能打进包**：`--onefile` 会把资源解到临时目录，
    那是只读副本；而用户要能编辑配置、程序要能把「保存为默认」写回去。见 `_app_dir()`。
    程序发现旁边没有 config.json 会按出厂默认值生成一份（`glass_overlay._load_cfg()`），
    所以**发布目录里不需要附带配置文件**，dist/ 只放一个 EXE 就行；用户删了配置也起得来。
    注意它是**运行时生成**的，别在 build_exe.py 里再复制一份进去。

16. **QSS 根容器必须有明确的不透明底**：若给根 `QWidget` 设 `background: transparent`，
    窗口会退回系统默认**浅色**底，整个深色主题看起来"完全没生效"。见 `win11_style.QSS`
    里的 `QWidget#root`，并在 `SettingsWindow.__init__` 里 `setObjectName("root")`。
    DWM 亚克力是增强而非必需，且必须在 `show()` 之后调用（那时 `winId()` 才有效）。

17. **设置页的卡片会被 QVBoxLayout 拉伸**：页面内容不满一页时，卡片会各自撑高、留出大片
    空白。每个页面构建完卡片后要 `lay.addStretch(1)` 把剩余空间吸到底部
    （见 `_page_*` 系列末尾）。

18. **数值标签别用中文后缀**：`cardValue` 用 Consolas 等宽字体，中文字符会 fallback 到
    别的字体、基线不一致，看起来像乱码（曾出现 `12 ↑`）。单位写进卡片说明文字里，
    数值标签保持纯数字。

19. **QSS 里别用 border 三角形画下拉箭头**：`width:0; height:0; border-left/right
    transparent + border-top solid` 这套 CSS 技巧在 Qt 里会渲染成**实心方块**。
    改用 `win11_style.chevron_icon()` 生成 PNG 再 `image: url(...)`。

20. **主题跟随要轮询 + WM_SETTINGCHANGE 双保险**：注册表没有变更通知，而
    WM_SETTINGCHANGE 在「只改主题色」时不广播（实测只有切明暗/换壁纸才发）。
    见 `win_theme.ThemeWatcher`：1.5s 轮询为主，原生事件过滤器做即时响应，
    两者都调同一个 `_check()`，靠指纹比对自动去重。

21. **DWM 属性必须在 show() 之后设**：`winId()` 在窗口显示后才有效，之前调用会
    静默失败。`SettingsWindow.showEvent` 里统一处理。

22. **界面要"复刻"就得读原版源码 + 量原图像素, 不能靠截图猜**：本项目的设置界面
    逐项对齐 Class-Widgets 使用的 RinUI 库。两个手段：
    - **读源码**：把 RinUI 的 wheel 下载解压后读 QML。
      ```
      python -m pip download RinUI --no-deps -d /tmp/rinui
      # 看 RinUI/themes/{dark,light,utils}.qml 与 components/
      ```
      关键数值: 窗口圆角 7/按钮圆角 5/标题栏 48, 导航项高 40/图标 19,
      以及下面那张动画时长表。
    - **量像素**：把目标图当数据读, `numpy` 扫行列找色值跳变与色块边界。
      实测标定出的三个数（逻辑 px, dpr=1.5）:
      指示条左缘 **6.7**、选中项高亮左缘 **9.3**、内容区比导航区亮 **+18 色阶**。
      靠眼睛估这三个值都会偏。

23. **Fluent 的动画时长 (ms), 取自 RinUI utils.qml**：见 `win_theme.py` 顶部常量。
    | 常量 | 值 | 用途 |
    |---|---|---|
    | `ANIM_APPEARANCE` | 187 | 界面/悬停切换（导航项背景色、文字淡出）|
    | `ANIM` | 250 | 导航折叠宽度、指示条淡入 |
    | `ANIM_MIDDLE` | 667 | 指示条生长、页面上滑 |
    缓动: 折叠 OutQuint、指示条生长 OutQuint、悬停变色 InOutQuart、页面淡入 InOutQuad。

24. **内容区必须是一个比导航栏更亮的独立图层**：这是 WinUI 观感的核心。RinUI 里叫
    `appLayer`，`color: colors.layerColor` + 1px 描边 + 圆角 = windowRadius，
    矩形向右下各外扩 `windowDragArea + radius`，这样**只有左上角露出圆角**。
    少了这一层，整个窗口就是一整块同色板，看着像"纯黑"。
    实测标定：导航区 (32,32,32) / 内容区 (50,50,50)，差值 +18。

25. **Fluent 配色是半透明叠加色, 不是实色**：`cardColor: Qt.alpha("#ffffff", 0.0512)`、
    `textSecondaryColor: Qt.alpha("#ffffff", 0.6047)`。用实色会让 Mica 完全被盖住,
    失去"淡淡透出桌面"的观感。见 `win_theme.Palette`。

26. **让 DWM 材质真正渲染, 光设 `SYSTEMBACKDROP_TYPE` 不够**：这是本项目排查最久的一个坑。
    实测对照（同一窗口、同一 alpha）:
    | 做法 | 窗口内像素 | 结论 |
    |---|---|---|
    | 只设 `DWMWA_SYSTEMBACKDROP_TYPE=Mica` | (36,36,36) | 材质**没画** |
    | 加 `WS_CAPTION\\|WS_THICKFRAME` + `DwmExtendFrameIntoClientArea(-1,-1,-1,-1)` | (227,227,227) | 材质**正常** |
    原因: **DWM 只对"带 frame 的窗口"绘制材质**, 而 Qt 的 `FramelessWindowHint`
    会把窗口变成 `WS_POPUP`, 材质就不画了。照搬 RinUI `core/window.py` 的
    `syncWindowFrame` + `extend_frame_into_client_area` 两步即可, 见
    `win11_style._enable_dwm_backdrop()`。帧扩展铺满客户区还有个副作用: 原生标题栏
    被"扩展掉"不显示, 同时白送圆角与原生缩放边框。

27. **窗口 scrim 透明度是"透过多少材质"的唯一旋钮**：`WA_TranslucentBackground` +
    Mica + 自绘 scrim。实测 **alpha < 0.4 时窗口几乎全透明, 会直接看到背后的其它程序**
    （不是材质）。可读区间 **0.45~0.85**。当前取 0.45(深)/0.55(浅), 好让材质透出来。

28. **控制面板被排除出屏幕捕获是故意的, 会导致截图看不到它**：`ControlPanel.showEvent`
    调 `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` 防止它自己的像素被 mss 抓进
    玻璃纹理再画一遍。**验证它外观时不能用整屏截图**, 要用 `widget.grab()`
    （或临时覆盖 showEvent 去掉排除）。

29. **图标用 FluentSystemIcons 字体 + 名称索引, 不用 Segoe**：名称形如
    `ic_fluent_board_20_regular`, 索引是 `FluentSystemIcons-Index.js` 里的
    `"名称": 码位` 映射（5656 个）。字体随项目打包在 `assets/fonts/`, 不依赖系统。
    打包时记得 `--add-data assets`，否则 EXE 里图标全空。

30. **折叠导航宽度用 WinUI 标准的 48px, 不是 40**：RinUI 源码写 `collapsed ? 40 : ...`,
    但对照目标图实测（以窗口边框为基准）折叠后导航栏 ≈ 50 逻辑 px。设 40 会让
    内容区比目标偏左约 10px。现在 `NAV_COLLAPSED = 48`。

31. **调试时注意残留进程**：多个测试进程各开一个窗口，会让截屏或状态诊断读到
    "另一个进程的窗口"，看起来像幽灵 bug。排查异常现象前先
    `Get-Process python,WindowsDuo` 确认没有残留。

32. **控制面板"卡在启动中" = 初始化语句被误吞进 `paintEvent`**（真实事故）：
    现象是面板永远显示"启动中…"，但控制台状态行照常刷新。根因是编辑代码时
    `__init__` 结尾的两行
    ```python
    self.set_status("启动中…")
    self.move(24, 24)
    ```
    被并进了 `paintEvent`，于是**每次重绘都把状态重置回初值**（tick 刚写进去的
    实时状态立刻被覆盖），顺带把窗口反复挪回 (24,24)。
    **教训**：改这种"方法末尾 + 下一个方法开头"的片段时，替换的字符串要带上
    下一个方法的定义行做锚点，别只匹配到 `p.end()` / `return` 这类通用结尾。
    **排查手法**：给方法插桩打调用栈——
    ```python
    orig = ControlPanel.set_status
    def traced(self, text):
        print(text[:30], "".join(traceback.format_stack()[-3:-1]))
        return orig(self, text)
    ```
    一眼就能看到是谁在写这个字段。

33. **图标三处显示必须同源, 且 assets/ 必须随包**: 标题栏 (`icon: App.iconUrl`)、
    任务栏 (`apply_app_icon()`)、EXE (`--icon assets/icon.ico`) 都从 `app_info.py` 取路径。
    三个坑:
    - 任务栏图标光设 `setWindowIcon` 不够, 还得 `SetCurrentProcessExplicitAppUserModelID`,
      否则本进程被并进 python.exe, 任务栏显示的是 Python 的图标; 且**必须在建窗口之前设**。
    - 打包时忘了 `--add-data assets`, 关于页的应用图标与窗口图标会全空 (那是 `_MEIPASS` 里的资源)。
    - 别直接用根目录那张 2017px/4.6MB 的 `icon.png` 当显示图标 —— 标题栏只要 16px。

34. **`SettingCard` 的 `description` 最多 3 行, 超出会被省略号截断**: 卡片左侧文字区最宽只有
    卡片宽的 60%, 一行约 41 个字。写说明文案要留余量, 否则用户看到的是半句话 + "…"。
    (窗口最小宽度 820 时一行只有 ~32 字, 按这个更严的标准写最稳。)

35. **`FluentPage` 里自定义「底板」卡片只能放一个直接子项**: `Frame` 的 `implicitHeight` 取的是
    `contentChildren.length === 1 ? contentChildren[0].implicitHeight : 0` —— 放了两个直接子项
    (比如在 QML 里又套一层 ColumnLayout), 卡片高度会算成 0 直接从界面上消失。
    所以 `About.qml` 的 `Panel` 自身不带布局, 由调用处给一个 `anchors.fill: parent` 的 ColumnLayout。

8. **摄像头打开失败不能崩**：`AngleTracker` 构造里 `cv2.VideoCapture` 打不开会抛异常。
   `CameraAngleReader` 已捕获并置 `tracker=None`，线程直接结束；用户仍可用 `r` 键转手动，
   或改 `camera_index` 重启。

9. **config.json 是唯一参数入口**，不要在代码里硬编码覆盖它。`tracker.py` 的模块级常量
   （`MIN_MATCHES` / `REKEY_RAD` 等）由 `glass_overlay.py` 在导入后按配置注入。

10. 调着色器先用 `offscreen_test.py` 离屏出图验证，再上真窗口；真窗口用 `--smoke` 的
    `grabFramebuffer()` 抓帧（不要用整屏截图验证 GL 内容）。`--smoke` 不要关自排除。

## 与 WindowsDuo 的对应关系

| 层 | WindowsDuo (win) | 本项目 |
|---|---|---|
| 角度来源 | ESP32 + MPU6050 串口 100Hz | 摄像头 ORB（`tracker.py`） |
| GL 管线 | 330 compatibility + glBegin/glEnd | 330 core + VAO/VBO |
| 角度→效果 | 线性 + 死区 + EMA | 线性 + EMA（连续控制） |
| 背景 | 纯黑（视线出界） | 纯黑（同） |
| 显示 | 常驻 overlay | 仅起效时显示 |

## 提交约定

- 主分支 `main`。
- 提交信息用中文、说明改动动机即可。
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/**
 * 设置窗口 (RinUI / FluentWindow)。
 *
 * 与 Class-Widgets 的设置窗口同框架、同控件库:
 *   FluentWindow 提供自绘标题栏 + NavigationView 导航栏,
 *   页面用 FluentPage + SettingCard, 控件用 RinUI 的 Slider/ComboBox/CheckBox。
 *
 * 配置读写走 Python 侧注入的 Config 上下文属性 (见 qml_bridge.py);
 * 应用信息 (版本 / 图标 / 路径) 走 App (见 app_info.py)。
 */
FluentWindow {
    id: settingsWindow
    title: "设置"
    width: 1000
    height: 700
    minimumWidth: 820
    minimumHeight: 560
    // 标题栏左侧的应用图标, 与任务栏 / EXE 图标同源 (app_info.py)。
    // 必须走 App 拿绝对路径: 打包后资源在 _MEIPASS 里, 相对路径解析不到。
    icon: App.iconUrl

    navigationItems: [
        {
            title: "折叠效果",
            page: Qt.resolvedUrl("pages/Fold.qml"),
            icon: "ic_fluent_board_20_regular"
        },
        {
            title: "模糊质感",
            page: Qt.resolvedUrl("pages/Quality.qml"),
            icon: "ic_fluent_paint_brush_sparkle_20_regular"
        },
        {
            title: "摄像头",
            page: Qt.resolvedUrl("pages/Camera.qml"),
            icon: "ic_fluent_camera_20_regular"
        },
        {
            title: "性能显示",
            page: Qt.resolvedUrl("pages/Perf.qml"),
            icon: "ic_fluent_gauge_20_regular"
        },
        {
            title: "关于",
            page: Qt.resolvedUrl("pages/About.qml"),
            icon: "ic_fluent_info_20_regular",
            position: Position.Bottom
        }
    ]
}

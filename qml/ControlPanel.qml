import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/**
 * 玻璃效果控制面板 (RinUI Window)。
 *
 * 与设置窗口同框架、同控件库; 用 RinUI 的轻量 Window (带自绘标题栏, 无导航栏)。
 * 状态与动作都走 Python 侧注入的 Panel 上下文属性 (见 glass_overlay.PanelBridge)。
 */
Window {
    id: panel
    title: "Duo 控制面板"

    // ---------- 尺寸 ----------
    // 用 height: layout.implicitHeight 会与 minimumHeight 形成绑定循环, 所以固定值。
    // 宽度不用给置顶按钮让位: 按钮挂的是"标题栏宿主右缘 + 48" (见下面 titleBarArea),
    // 落在那 48px 的布局间距里, 面板多宽都不影响它的位置。
    property int panelWidth: 344
    property int panelHeight: 300

    // 原生边框厚度补偿。Qt 会在客户区之外再加一圈原生边框 (本机 dpr=1.5 实测 13px),
    // 而 RinUI 的 WM_GETMINMAXINFO 直接把 QML 的 minimum/maximumWidth 当成 Win32 的
    // min/max track size (外框尺寸) 上报 —— 少算了这一圈, 用户一拖动窗口, Windows 就按
    // 上限把外框夹回去 (表现为"窗口突然缩小一点"), 顺带把标题栏里置顶按钮的可用宽度
    // 挤到 8px、图标整个消失。framePadW/H 由 glass_overlay.ControlPanel 显示后实测注入。
    property int framePadW: 0
    property int framePadH: 0

    width: panelWidth
    height: panelHeight
    minimumWidth: panelWidth
    maximumWidth: panelWidth + framePadW
    minimumHeight: panelHeight
    maximumHeight: panelHeight + framePadH
    maximizeEnabled: false

    // 窗口底色必须是不透明的。面板按主题走 mica (QML 的 background 矩形是 transparent),
    // 但轻量 Window 没有 backdropEnabled 属性、拿不到材质, 于是窗口边缘这些像素既不由
    // QML 绘制也没有材质, 全落到 DWM 兜底手里 —— 实测: 置顶 + 失焦后 DWM 会把窗口四周
    // 填成一圈 2~4px 白框, 且重获焦点也不会消失。给窗口一个不透明底色后窗口表面不再是
    // 半透明表面, DWM 不再插手, 白框消失 (实测)。
    color: Theme.currentTheme.colors.backgroundColor

    // 置顶按钮: 和右侧"最小化/最大化/关闭"并排, 紧挨最小化按钮左边。
    // 注意: RinUI 的 ToolButton 没有内在尺寸 (contentItem 依赖 parent 宽高),
    // 必须显式给宽高, 否则会画成 0x0 完全看不见。
    //
    // 位置说明: 这个按钮挂在 titleBarArea 里, 宿主是标题栏布局中的 fillWidth 项, 它的
    // 右缘和窗口按钮行之间还隔着 RinUI 标题栏 RowLayout 的 spacing = 48
    // (见 RinUI windows/TitleBar.qml: spacing: isMacOS ? ... : 48)。所以要贴到窗口
    // 按钮左边, 得用负的 rightMargin 把这段间距抵消掉 —— 于是按钮越过了宿主右缘,
    // 必须同时关掉宿主自己的裁剪 (titleBarHost.clip), 否则按钮会被宿主裁掉。
    // 标题栏根节点 TitleBar 自己也有 clip: true, 但按钮仍在标题栏范围内, 不受影响。
    titleBarHost.clip: false
    titleBarArea: ToolButton {
        width: 36
        height: 30
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.rightMargin: -48      // 抵消标题栏布局的 48px 间距 -> 与最小化按钮严丝合缝
        // RinUI 的 ToolButton 图标默认 20px, 而旁边三个窗口按钮的字形只有 14~16px,
        // 并排放在一起会显得置顶图标偏大, 所以对齐成 16 (见 TitleBar.qml 里 CtrlBtn 的 Icon.size)
        size: 16
        flat: true                    // 标题栏按钮常态透明, 悬停才显底色
        icon.name: Panel.pinned ? "ic_fluent_pin_20_filled" : "ic_fluent_pin_off_20_regular"
        ToolTip.text: Panel.pinned ? "取消置顶" : "保持置顶"
        ToolTip.visible: hovered
        onClicked: Panel.togglePin()
    }

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

        // ---------- 状态 ----------
        Text {
            Layout.fillWidth: true
            typography: Typography.Body
            color: Theme.currentTheme.colors.primaryColor
            wrapMode: Text.Wrap
            text: Panel.status
        }

        Text {
            Layout.fillWidth: true
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            wrapMode: Text.Wrap
            visible: text !== ""
            text: Panel.hint
        }

        // ---------- 标定 / 翻转 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                Layout.fillWidth: true
                text: "标定基准帧"
                onClicked: Panel.calibrate()
            }
            Button {
                Layout.fillWidth: true
                text: "翻转方向"
                onClicked: Panel.flip()
            }
        }

        // ---------- 灵敏度 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: "灵敏度 −"
                onClicked: Panel.scale(-0.1)
            }
            Button {
                text: "灵敏度 ＋"
                onClicked: Panel.scale(0.1)
            }
            Text {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                text: "SCALE=" + Number(Panel.scaleValue).toFixed(2)
            }
        }

        // ---------- 自动 / 手动 + 浓度 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                Layout.fillWidth: true
                text: Panel.autoMode ? "切手动" : "切自动"
                onClicked: Panel.toggleAuto()
            }
            Button {
                Layout.fillWidth: true
                text: "浓度清零"
                onClicked: Panel.conc(0.0)
            }
            Button {
                Layout.fillWidth: true
                text: "浓度拉满"
                onClicked: Panel.conc(1.0)
            }
        }

        // ---------- 设置 / 退出 ----------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                Layout.fillWidth: true
                text: "设置…"
                onClicked: Panel.openSettings()
            }
            Button {
                Layout.fillWidth: true
                text: "退出"
                onClicked: Panel.quit()
            }
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/**
 * 关于页。
 *
 * 面向公开发布: 顶部一条「品牌条」(图标 + 应用名 + 版本 + 一句话定位),
 * 下面按「这是什么 / 快速上手 / 控制面板 / 配置与状态 / 关于本项目」分组,
 * 每组用卡片承载, 组间留白 —— 信息密度高但不挤。
 *
 * 版本号、路径、运行环境全部来自 Python 侧注入的 App (见 app_info.py),
 * 不在 QML 里写死, 否则发版时必有一处忘记改。
 */
FluentPage {
    id: page
    title: "关于"

    // 一行信息: 左侧固定宽度的名目 + 右侧内容
    component InfoRow: RowLayout {
        id: infoRow
        property string label: ""
        property string value: ""
        property bool mono: false
        Layout.fillWidth: true
        spacing: 16

        Text {
            Layout.preferredWidth: 84
            Layout.alignment: Qt.AlignTop
            typography: Typography.Caption
            color: Theme.currentTheme.colors.textSecondaryColor
            text: infoRow.label
        }

        Text {
            Layout.fillWidth: true
            typography: Typography.Body
            wrapMode: Text.Wrap
            font.family: infoRow.mono ? "Consolas" : Utils.fontFamily
            text: infoRow.value
        }
    }

    // 圆角底板: 放自定义排版 (步骤 / 对照表), 比 SettingCard 更合适。
    // 用法: Panel { ColumnLayout { anchors.fill: parent; ... } } —— 里面只能有
    // 一个直接子项, Frame 的 implicitHeight 是按「唯一子项的 implicitHeight」算的。
    component Panel: Frame {
        id: panel
        Layout.fillWidth: true
        hoverable: false
        leftPadding: 20
        rightPadding: 20
        topPadding: 16
        bottomPadding: 16
    }

    // ---------------------------------------------------------------- 品牌区
    // 一条紧凑的「品牌条」: 图标 + 应用名 + 版本 + 一句话定位。
    // 高度由内容决定 (图标 56 + 上下 18 内边距 = 92), 刻意压扁 —— 它是页眉, 不是封面。
    Rectangle {
        Layout.fillWidth: true
        Layout.bottomMargin: 4
        implicitHeight: heroRow.implicitHeight + 36
        radius: Theme.currentTheme.appearance.windowRadius
        color: "transparent"
        border.width: 1
        border.color: Theme.currentTheme.colors.cardBorderColor

        // 主色向左淡出: 让品牌条比下面的卡片亮一档, 但仍用 Fluent 的叠加色
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop {
                position: 0.0
                color: Qt.rgba(Theme.currentTheme.colors.primaryColor.r,
                               Theme.currentTheme.colors.primaryColor.g,
                               Theme.currentTheme.colors.primaryColor.b, 0.22)
            }
            GradientStop {
                position: 0.5
                color: Qt.rgba(Theme.currentTheme.colors.primaryColor.r,
                               Theme.currentTheme.colors.primaryColor.g,
                               Theme.currentTheme.colors.primaryColor.b, 0.05)
            }
            GradientStop {
                position: 1.0
                color: Theme.currentTheme.colors.cardColor
            }
        }

        RowLayout {
            id: heroRow
            anchors.fill: parent
            anchors.margins: 18
            spacing: 16

            Image {
                source: App.iconUrl
                visible: String(source) !== ""
                sourceSize.width: 112
                sourceSize.height: 112
                Layout.preferredWidth: 56
                Layout.preferredHeight: 56
                Layout.alignment: Qt.AlignVCenter
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 1

                RowLayout {
                    spacing: 10

                    Text {
                        typography: Typography.Subtitle
                        text: App.name
                    }

                    // 版本号跟在品牌名后面: 字号小一档、对齐基线, 像页眉上的刊期
                    Text {
                        Layout.alignment: Qt.AlignBaseline
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.textSecondaryColor
                        text: App.versionTag
                    }
                }

                Text {
                    Layout.fillWidth: true
                    typography: Typography.Body
                    color: Theme.currentTheme.colors.textSecondaryColor
                    text: App.tagline
                }
            }
        }
    }

    // ---------------------------------------------------------------- 这是什么
    Text {
        typography: Typography.BodyStrong
        Layout.topMargin: 14
        text: "这是什么"
    }

    SettingCard {
        Layout.fillWidth: true
        title: "摄像头测角，不需要任何外接硬件"
        description: "上盖摄像头随开合转动，用 ORB 特征匹配 + 单应分解实时算出俯仰角；关键帧与固定锚点校正漂移，One Euro 滤波抑制抖动。"
        icon.name: "ic_fluent_camera_20_regular"
    }

    SettingCard {
        Layout.fillWidth: true
        title: "逆投影渲染，像一块绕屏幕底边转开的玻璃"
        description: "靠近铰链处始终清晰，越远越模糊、越暗，视线出界处为纯黑。模糊用 Vogel 盘 + mip 分级采样，磨砂玻璃的颗粒感由此而来。"
        icon.name: "ic_fluent_board_20_regular"
    }

    SettingCard {
        Layout.fillWidth: true
        title: "不打扰正常使用"
        description: "叠加层全屏置顶但鼠标可穿透点击，键盘照常输入；不折叠时自动隐藏，桌面保持原生清晰。"
        icon.name: "ic_fluent_cursor_20_regular"
    }

    // ---------------------------------------------------------------- 快速上手
    Text {
        typography: Typography.BodyStrong
        Layout.topMargin: 18
        text: "快速上手"
    }

    Panel {
        ColumnLayout {
            anchors.fill: parent
            spacing: 14

            Repeater {
                model: [
                    { "step": "1", "title": "上盖完全展开，摄像头对着有纹理的静止场景",
                      "desc": "书架、贴画的墙都行；纯白墙或对着自己会匹配不到足够特征点。" },
                    { "step": "2", "title": "点控制面板的「标定基准帧」",
                      "desc": "把当前画面设为 0° 基准，状态变成「追踪中」即成功。" },
                    { "step": "3", "title": "慢慢合上上盖",
                      "desc": "桌面跟着折叠成磨砂玻璃，合得越深玻璃转开越多。" },
                    { "step": "4", "title": "方向或幅度不对，就地调",
                      "desc": "方向反了点「翻转方向」，跟手太钝或太灵点「灵敏度 −/＋」。" }
                ]

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    Rectangle {
                        Layout.alignment: Qt.AlignTop
                        width: 22
                        height: 22
                        radius: 11
                        color: Qt.rgba(Theme.currentTheme.colors.primaryColor.r,
                                       Theme.currentTheme.colors.primaryColor.g,
                                       Theme.currentTheme.colors.primaryColor.b, 0.16)

                        Text {
                            anchors.centerIn: parent
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.primaryColor
                            text: modelData.step
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1

                        Text {
                            Layout.fillWidth: true
                            typography: Typography.Body
                            text: modelData.title
                        }
                        Text {
                            Layout.fillWidth: true
                            typography: Typography.Caption
                            color: Theme.currentTheme.colors.textSecondaryColor
                            text: modelData.desc
                        }
                    }
                }
            }
        }
    }

    // ---------------------------------------------------------------- 控制面板
    Text {
        typography: Typography.BodyStrong
        Layout.topMargin: 18
        text: "控制面板"
    }

    Panel {
        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            Repeater {
                // 面板按钮覆盖全部操作, 不依赖控制台 —— 打包版没有控制台,
                // 所以这里只列按钮, 不列键盘快捷键 (那只在有控制台时才可用)。
                model: [
                    { "name": "① 标定基准帧", "desc": "把当前画面设为 0° 基准（上盖完全展开时点）" },
                    { "name": "翻转方向", "desc": "合盖时效果方向反了按它" },
                    { "name": "灵敏度 −/＋", "desc": "调整角度到折叠的换算比例（SCALE）" },
                    { "name": "切手动 / 切自动", "desc": "跟随角度开合，或手动覆盖折叠浓度" },
                    { "name": "浓度清零 / 拉满", "desc": "手动快速设置，便于预览效果" },
                    { "name": "设置…", "desc": "打开本窗口，改动即时生效并自动保存" },
                    { "name": "退出", "desc": "结束程序；标题栏图钉按钮可让面板保持置顶" }
                ]

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 16

                    Text {
                        Layout.preferredWidth: 130
                        Layout.alignment: Qt.AlignTop
                        typography: Typography.Body
                        text: modelData.name
                    }
                    Text {
                        Layout.fillWidth: true
                        typography: Typography.Caption
                        color: Theme.currentTheme.colors.textSecondaryColor
                        text: modelData.desc
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.topMargin: 2
                typography: Typography.Caption
                color: Theme.currentTheme.colors.textSecondaryColor
                text: "面板是普通窗口，Alt+Tab 能找到它。"
            }
        }
    }

    // ---------------------------------------------------------------- 配置与状态
    Text {
        typography: Typography.BodyStrong
        Layout.topMargin: 18
        text: "配置与状态"
    }

    SettingCard {
        Layout.fillWidth: true
        title: "配置文件"
        description: "参数存在 " + Config.configName() + "（与程序同级）。改动立即生效并自动保存；"
                     + "「恢复默认」回到出厂值。打包版请连同它一起移动，别只拷 EXE。"
        icon.name: "ic_fluent_folder_20_regular"

        Button {
            text: "打开所在位置"
            onClicked: App.openConfigDir()
        }
        Button {
            text: "恢复默认"
            onClicked: Config.resetDefaults()
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "当前状态"
        description: Config.status
        icon.name: "ic_fluent_arrow_sync_20_regular"

        Button {
            text: "打开程序目录"
            onClicked: App.openAppDir()
        }
    }

    // ---------------------------------------------------------------- 关于本项目
    Text {
        typography: Typography.BodyStrong
        Layout.topMargin: 18
        text: "关于本项目"
    }

    Panel {
        ColumnLayout {
            anchors.fill: parent
            spacing: 8

            InfoRow { label: "版本"; value: App.versionTag }
            InfoRow { label: "运行方式"; value: App.mode }
            InfoRow { label: "运行环境"; value: App.runtime }
            InfoRow { label: "系统"; value: App.platformName }
            InfoRow { label: "配置文件"; value: App.configPath; mono: true }
            InfoRow { label: "许可"; value: App.license }
        }
    }

    SettingCard {
        Layout.fillWidth: true
        title: "开源致谢"
        // 卡片说明最多显示 3 行, 超了会被省略号截断 —— 这里刻意留出余量
        description: "渲染与工程化移植自 WindowsDuo（MIT），逆投影模型源自 DuoLikeAnimation / iphone-duo / MacDuo / FrostFold；界面用 RinUI 组件库与 Fluent System Icons。"
        icon.name: "ic_fluent_heart_20_regular"

        Hyperlink {
            text: "项目主页"
            url: App.homepage
        }
    }

    // ---------------------------------------------------------------- 页脚
    Text {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 16
        horizontalAlignment: Text.AlignHCenter
        typography: Typography.Caption
        color: Theme.currentTheme.colors.textSecondaryColor
        text: App.name + " " + App.versionTag + " · " + App.license
    }
}

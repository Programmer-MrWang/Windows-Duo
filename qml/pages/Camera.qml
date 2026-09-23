import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "摄像头与识别"

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: "摄像头"
        }

        SettingCard {
            Layout.fillWidth: true
            title: "摄像头索引"
            description: "多个摄像头时选择随上盖转动的那颗，改动需重启程序。"
            icon.name: "ic_fluent_camera_20_regular"

            ComboBox {
                Layout.preferredWidth: 170
                model: ["摄像头 0", "摄像头 1", "摄像头 2", "摄像头 3"]
                Component.onCompleted: currentIndex = Math.min(3, Math.max(0, Math.round(Config.getNum("camera_index"))))
                onActivated: Config.set("camera_index", index)
            }
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "scale"
            title: "角度灵敏度"
            description: "物理俯仰角 → 折叠浓度的比例。开合幅度大但效果不明显时调大它。"
            icon.name: "ic_fluent_camera_20_regular"
            from: 0.2; to: 3.0; step: 0.05; decimals: 2
        }

        SettingCard {
            Layout.fillWidth: true
            title: "反向"
            description: "合盖时效果方向相反就打开（等价控制面板的「翻转方向」）。"
            icon.name: "ic_fluent_camera_20_regular"

            CheckBox {
                id: signBox
                Component.onCompleted: checked = Config.getNum("sign") < 0
                onToggled: Config.set("sign", checked ? -1 : 1)
                Connections {
                    target: Config
                    function onValuesChanged() {
                        signBox.checked = Config.getNum("sign") < 0
                    }
                }
            }
        }

        Text {
            typography: Typography.BodyStrong
            text: "识别阈值"
            Layout.topMargin: 8
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "min_matches"
            title: "最少匹配点"
            description: "低于这个匹配数就认为跟丢了。场景纹理少时可适当调低（最低 4）。"
            icon.name: "ic_fluent_camera_20_regular"
            from: 6; to: 60; step: 1; decimals: 0; asInt: true
        }

        SettingCard {
            Layout.fillWidth: true
            title: "怎么标定"
            description: "1. 上盖完全展开，摄像头对准有纹理的静止场景（书架、贴画的墙）\n2. 点主面板的「① 标定基准帧」\n3. 面板状态显示「追踪中」即成功"
            icon.name: "ic_fluent_camera_20_regular"
        }
    }
}

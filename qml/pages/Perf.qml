import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "性能与显示"

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: "抓屏与显隐"
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "refresh_hz"
            title: "抓屏频率"
            description: "叠加层每秒重新抓几次桌面（单位 Hz）。3 已足够，调高更跟手但更耗性能。"
            icon.name: "ic_fluent_gauge_20_regular"
            from: 1; to: 30; step: 1; decimals: 0; asInt: true
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "show_threshold"
            title: "显示阈值"
            description: "浓度低于此值时隐藏叠加层，桌面保持原生清晰。"
            icon.name: "ic_fluent_gauge_20_regular"
            from: 0.0; to: 0.05; step: 0.001; decimals: 3
        }

        SettingCard {
            Layout.fillWidth: true
            title: "性能提示"
            description: "若开合时卡顿，可降低「抓屏频率」或「采样次数」；抬高「显示阈值」也能减少叠加层出现的时间。"
            icon.name: "ic_fluent_gauge_20_regular"
        }
    }
}

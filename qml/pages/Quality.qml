import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "模糊质感"

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: "磨砂玻璃"
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "blur_spread"
            title: "模糊强度"
            description: "单位间隙对应多大的模糊半径。越大玻璃越朦胧。"
            icon.name: "ic_fluent_paint_brush_sparkle_20_regular"
            from: 0.05; to: 1.5; step: 0.01; decimals: 2
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "darkening"
            title: "变暗程度"
            description: "磨砂玻璃的吸光量。0 = 完全不变暗；越大越暗。"
            icon.name: "ic_fluent_paint_brush_sparkle_20_regular"
            from: 0.0; to: 0.006; step: 0.0005; decimals: 3
        }

        Text {
            typography: Typography.BodyStrong
            text: "渲染精度"
            Layout.topMargin: 8
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "max_taps"
            title: "采样次数"
            description: "每个像素最多采样几次。越大越细腻也更吃显卡，32 是平衡点。"
            icon.name: "ic_fluent_paint_brush_sparkle_20_regular"
            from: 8; to: 64; step: 1; decimals: 0; asInt: true
        }
    }
}

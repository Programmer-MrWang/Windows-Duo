import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI
import "../components"

FluentPage {
    id: page
    title: "折叠效果"

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 4

        Text {
            typography: Typography.BodyStrong
            text: "几何"
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "max_tilt_deg"
            title: "最大转角"
            description: "玻璃最多转开多少度。接近 90° 时视线大量出界、画面变黑；62° 左右观感最好。"
            icon.name: "ic_fluent_board_20_regular"
            from: 20; to: 88; step: 1; decimals: 1
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "eye_dist_h"
            title: "眼距"
            description: "眼睛到界面平面的距离，以屏高为倍数。越大透视越平缓。"
            icon.name: "ic_fluent_board_20_regular"
            from: 0.8; to: 4.0; step: 0.05; decimals: 2
        }

        Text {
            typography: Typography.BodyStrong
            text: "跟随手感"
            Layout.topMargin: 8
        }

        SliderField {
            Layout.fillWidth: true
            cfgKey: "smoothing"
            title: "浓度平滑"
            description: "折叠跟随的平滑程度。越小越顺滑但跟手越慢；越大越跟手但可能抖动。"
            icon.name: "ic_fluent_board_20_regular"
            from: 0.05; to: 0.9; step: 0.01; decimals: 2
        }
    }
}

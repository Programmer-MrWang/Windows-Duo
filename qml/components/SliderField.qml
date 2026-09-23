import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import RinUI

/**
 * 可复用的一行设置卡片: 标题 + 说明 + 右侧数值 + 下方滑块。
 * 数值与滑块的联动在这里统一处理, 各页面只需给 key/范围/单位。
 */
SettingCard {
    id: card

    property string cfgKey: ""
    property real from: 0
    property real to: 100
    property real step: 0.01
    property int decimals: 2
    property string unit: ""
    property bool asInt: false
    property alias sliderItem: slider

    function _fmt(v) {
        return asInt ? String(Math.round(v)) : Number(v).toFixed(decimals)
    }

    function _push(v) {
        Config.set(cfgKey, asInt ? Math.round(v) : v)
    }

    // 批量值变化 (恢复默认) 时重读
    Connections {
        target: Config
        function onValuesChanged() {
            slider.value = Config.getNum(card.cfgKey)
            valueLabel.text = card._fmt(slider.value)
        }
    }

    // 右上角的实时数值
    RowLayout {
        spacing: 12

        Text {
            id: valueLabel
            Layout.alignment: Qt.AlignVCenter
            typography: Typography.Body
            color: Theme.currentTheme.colors.primaryColor
            font.family: "Consolas"
            text: card._fmt(Config.getNum(card.cfgKey))
        }

        Slider {
            id: slider
            Layout.preferredWidth: 260
            Layout.alignment: Qt.AlignVCenter
            from: card.from
            to: card.to
            stepSize: card.step
            snapMode: Slider.SnapAlways
            Component.onCompleted: value = Config.getNum(card.cfgKey)
            onMoved: {
                valueLabel.text = card._fmt(value)
                card._push(value)
            }
        }
    }
}

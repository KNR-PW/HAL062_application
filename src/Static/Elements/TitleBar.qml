import QtQuick
import QtQuick.Layouts

Rectangle {


    Layout.preferredHeight: 25
    Layout.fillWidth: true
    color: inputManager.state.gamepad_enabled ? '#ab6868' : '#981313'

    // RowLayout {
    //     anchors.fill: parent
    //     spacing: 0

    //     Item {
    //         Layout.fillWidth: true
    //     }


    // }

    
}

import QtQuick
import QtQuick.Layouts
import com.halapp.enums

Rectangle {
    Layout.preferredHeight: 25
    Layout.fillWidth: true
    color: inputState.gamepad_enabled ? '#ab6868' : '#981313'

    Text {
        text: "Control scheme: " + inputState.control_scheme_name
    }

    
}

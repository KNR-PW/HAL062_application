import QtQuick 2.15
import QtQuick.Layouts 1.15

Rectangle {
    id: root
    width: 500
    height: 400
    color: "#2b2b2b"

    property real currentSpeed: 0.0
    property real currentTurn: 0.0

    Connections {
        target: inputManager
        function onGamepadSignal(status, value) {
            if (status === "speed") {
                root.currentSpeed = value
            } else if (status === "turn") {
                root.currentTurn = value
            }
        }
    }

    // Telemetry overlay
    Column {
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.margins: 15
        spacing: 5

        Text { text: "Chassis View"; color: "white"; font.bold: true; font.pixelSize: 16 }
        Text { text: "Speed: " + root.currentSpeed.toFixed(2); color: root.currentSpeed >= 0 ? "#00ff00" : "#ff3333" }
        Text { text: "Turn:  " + root.currentTurn.toFixed(2); color: "cyan" }
    }

    // Gauges Container
    Row {
        anchors.centerIn: parent
        spacing: 60

        // 1. Vertical Speed Gauge
        Column {
            spacing: 10
            anchors.verticalCenter: parent.verticalCenter

            Text { 
                text: "THROTTLE / BRAKE"
                color: "gray"
                font.pixelSize: 12
                anchors.horizontalCenter: parent.horizontalCenter 
            }

            Rectangle {
                id: speedGauge
                width: 40
                height: 200
                color: "#1e1e1e"
                border.color: "#444"
                border.width: 2
                radius: 4
                anchors.horizontalCenter: parent.horizontalCenter

                // Center deadzone line
                Rectangle {
                    width: parent.width
                    height: 2
                    color: "#666"
                    anchors.centerIn: parent
                }

                // Dynamic fill indicator
                Rectangle {
                    width: parent.width - 4
                    anchors.horizontalCenter: parent.horizontalCenter
                    
                    // Height is proportional to the absolute speed value
                    height: Math.abs(root.currentSpeed) * ((speedGauge.height - 4) / 2)
                    
                    // If positive, draw from center UP. If negative, draw from center DOWN.
                    y: root.currentSpeed >= 0 
                        ? (speedGauge.height / 2) - height 
                        : (speedGauge.height / 2)
                        
                    // Green for throttle, Red for reverse/brake
                    color: root.currentSpeed >= 0 ? "#00ff00" : "#ff3333"
                    radius: 2

                }
            }
        }

        // 2. Horizontal Turn Gauge
        Column {
            spacing: 10
            anchors.verticalCenter: parent.verticalCenter

            Text { 
                text: "STEERING"
                color: "gray"
                font.pixelSize: 12
                anchors.horizontalCenter: parent.horizontalCenter 
            }

            Rectangle {
                id: turnGauge
                width: 200
                height: 40
                color: "#1e1e1e"
                border.color: "#444"
                border.width: 2
                radius: 4
                anchors.horizontalCenter: parent.horizontalCenter

                // Center deadzone line
                Rectangle {
                    width: 2
                    height: parent.height
                    color: "#666"
                    anchors.centerIn: parent
                }

                // Dynamic fill indicator
                Rectangle {
                    height: parent.height - 4
                    anchors.verticalCenter: parent.verticalCenter
                    
                    // Width is proportional to the absolute turn value
                    width: Math.abs(root.currentTurn) * ((turnGauge.width - 4) / 2)
                    
                    // If positive, draw from center RIGHT. If negative, draw from center LEFT.
                    x: root.currentTurn >= 0 
                        ? (turnGauge.width / 2) 
                        : (turnGauge.width / 2) - width
                        
                    color: "cyan"
                    radius: 2
                }
            }
        }
    }
}
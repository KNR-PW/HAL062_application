# Copyright (C) 2022 The Qt Company Ltd.
# SPDX-License-Identifier: LicenseRef-Qt-Commercial OR BSD-3-Clause
from __future__ import annotations

import signal
import sys

import connections
import inputs
import rover_logic
from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

# To be used on the @QmlElement decorator
QML_IMPORT_NAME = "io.qt.textproperties"
QML_IMPORT_MAJOR_VERSION = 1

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)

    input_manager = inputs.InputManager()
    kb_filter = inputs.GlobalKeyboardFilter(input_manager)
    app.installEventFilter(kb_filter)

    rover_connection = connections.RoverTcpClient()
    # input_manager.gamepadSignal.connect(rover_connection.handle_gamepad)
    # rover_connection.start()

    gamepad_thread = inputs.GamepadWorker()
    gamepad_thread.button_pressed.connect(input_manager.handle_gamepad_button)
    gamepad_thread.axis_moved.connect(input_manager.handle_gamepad_axis)
    gamepad_thread.gamepad_connected.connect(
        lambda state: setattr(input_manager.state, "gamepad_connected", state)
    )
    gamepad_thread.start()

    roverLogic_thread = rover_logic.RoverLogic(connections.RoverAPI(), input_manager)
    input_manager.actionSignal.connect(roverLogic_thread.handle_action_signal)
    input_manager.gamepadSignal.connect(roverLogic_thread.handle_gamepad_signal)

    input_manager.state.gamepad_connectedChanged.connect(
        roverLogic_thread.handle_state_signal
    )
    input_manager.state.gamepad_enabledChanged.connect(
        roverLogic_thread.handle_state_signal
    )
    input_manager.state.control_schemeChanged.connect(
        roverLogic_thread.handle_state_signal
    )

    roverLogic_thread.start()

    app.aboutToQuit.connect(gamepad_thread.stop)
    # app.aboutToQuit.connect(rover_connection.stop)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("inputManager", input_manager)
    # engine.rootContext().setContextProperty("roverConnection", rover_connection)
    # Add the current directory to the import paths and load the main module.
    engine.addImportPath(sys.path[-1])
    engine.loadFromModule("Static", "Main")

    # Make python read signals every 500ms so ctrl+C will work
    signal.signal(signal.SIGINT, lambda sig, frame: app.quit())
    timer = QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    if not engine.rootObjects():
        sys.exit(-1)

    exit_code = app.exec()
    del engine
    sys.exit(exit_code)

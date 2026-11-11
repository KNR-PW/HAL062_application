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

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)

    rover_connection = connections.TcpClient("127.0.0.1", 8888)

    input_state = inputs.InputState()
    input_manager = inputs.InputManager(input_state)
    kb_filter = inputs.GlobalKeyboardFilter(input_manager)
    app.installEventFilter(kb_filter)

    gamepad_thread = inputs.GamepadWorker()
    gamepad_thread.button_pressed.connect(input_manager.handle_gamepad_button)
    gamepad_thread.axis_moved.connect(input_manager.handle_gamepad_axis)
    gamepad_thread.gamepad_connected.connect(
        lambda state: setattr(input_state, "gamepad_connected", state)
    )
    gamepad_thread.gamepad_inactive.connect(
        lambda state: setattr(input_state, "gamepad_enabled", False)
    )

    gamepad_thread.start()

    rover_api = connections.RoverAPI()
    rover_api.commandSignal.connect(rover_connection.send_command)

    roverLogic_thread = rover_logic.RoverLogic(rover_api, input_manager, input_state)
    input_manager.actionSignal.connect(roverLogic_thread.handle_action_signal)
    input_manager.gamepadSignal.connect(roverLogic_thread.handle_gamepad_signal)

    input_state.gamepad_connectedChanged.connect(roverLogic_thread.handle_state_signal)
    input_state.gamepad_enabledChanged.connect(roverLogic_thread.handle_state_signal)
    input_state.control_schemeChanged.connect(roverLogic_thread.handle_state_signal)

    roverLogic_thread.start()

    app.aboutToQuit.connect(gamepad_thread.stop)
    # app.aboutToQuit.connect(rover_connection.stop)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("inputManager", input_manager)
    engine.rootContext().setContextProperty("inputState", input_state)
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

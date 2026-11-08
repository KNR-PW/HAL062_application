import os
from enum import IntEnum, auto

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

import pygame
from PySide6.QtCore import Property, QEnum, QEvent, QObject, QThread, Signal, Slot
from PySide6.QtQmlFeatures import auto_properties


class GlobalKeyboardFilter(QObject):
    """Intercepts key presses application-wide, regardless of which window has focus."""

    def __init__(self, input_manager):
        super().__init__()
        self.input_manager = input_manager

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and not event.isAutoRepeat():
            key_name = event.text().upper() or f"Key_{event.key()}"
            self.input_manager.handle_key_press(key_name)
            return True

        elif event.type() == QEvent.Type.KeyRelease and not event.isAutoRepeat():
            key_name = event.text().upper() or f"Key_{event.key()}"
            self.input_manager.handle_key_release(key_name)
            return True

        # Allow standard Qt event propagation to continue
        return super().eventFilter(watched, event)


@auto_properties
class InputState(QObject):
    class ControlScheme(IntEnum):
        DISABLED = 0
        CHASIS = auto()
        MANIPULATOR = auto()

    QEnum(ControlScheme)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.gamepad_connected = False
        self.gamepad_enabled = True
        self.control_scheme = self.ControlScheme.CHASIS


class InputManager(QObject):
    class InputAction(IntEnum):
        MAIN_FORWARD = 0
        MAIN_BACKWARD = auto()
        MAIN_LEFT = auto()
        MAIN_RIGHT = auto()

        TOGGLE_PAD = auto()

        JOY_LS_X = auto()
        JOY_LS_Y = auto()
        JOY_RS_X = auto()
        JOY_RS_Y = auto()
        JOY_LT = auto()
        JOY_RT = auto()
        JOY_A = auto()
        JOY_B = auto()
        JOY_X = auto()
        JOY_Y = auto()
        JOY_LB = auto()
        JOY_RB = auto()
        JOY_BB = auto()
        JOY_SB = auto()

    actionSignal = Signal(InputAction, bool)
    gamepadSignal = Signal(InputAction, float)
    QEnum(InputAction)

    def __init__(self):
        super().__init__()
        self._state = InputState()  # pyright: ignore[reportCallIssue]

        self.keyboard_map = {
            "W": self.InputAction.MAIN_FORWARD,
            "S": self.InputAction.MAIN_BACKWARD,
            "A": self.InputAction.MAIN_LEFT,
            "D": self.InputAction.MAIN_RIGHT,
            "~": self.InputAction.TOGGLE_PAD,
        }

        self.analog_map = {
            0: self.InputAction.JOY_LS_X,
            1: self.InputAction.JOY_LS_Y,
            2: self.InputAction.JOY_RS_X,
            3: self.InputAction.JOY_RS_Y,
            4: self.InputAction.JOY_LT,
            5: self.InputAction.JOY_RT,
        }

        self.gamepad_map = {
            0: self.InputAction.JOY_A,
            1: self.InputAction.JOY_B,
            2: self.InputAction.JOY_X,
            3: self.InputAction.JOY_Y,
            4: self.InputAction.JOY_LB,
            5: self.InputAction.JOY_RB,
            6: self.InputAction.JOY_BB,
            7: self.InputAction.JOY_SB,
        }

    @Property(QObject, constant=True)
    def state(self):
        return self._state

    # --- RAW INPUT RECEIVERS ---
    @Slot(str)
    def handle_key_press(self, key_name):
        action = self.keyboard_map.get(key_name)
        if action == self.InputAction.TOGGLE_PAD:
            self._state.gamepad_enabled = not self._state.gamepad_enabled
            return

        if action is not None:
            self.actionSignal.emit(action, True)

    @Slot(str)
    def handle_key_release(self, key_name):
        action = self.keyboard_map.get(key_name)
        if action is not None:
            self.actionSignal.emit(action, False)

    @Slot(int)
    def handle_gamepad_button(self, button_id, state):
        action = self.gamepad_map.get(button_id)
        if action is not None:
            self.actionSignal.emit(button_id, state)

    @Slot(int, float)
    def handle_gamepad_axis(self, axis_id, value):
        action = self.analog_map.get(axis_id)
        if action is not None:
            self.actionSignal.emit(axis_id, value)


class GamepadWorker(QThread):
    button_pressed = Signal(int, bool)
    axis_moved = Signal(int, float)
    gamepad_connected = Signal(bool)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        pygame.init()
        pygame.joystick.init()
        joystick = None
        clock = pygame.time.Clock()

        while self._running:
            if joystick is None:
                if pygame.joystick.get_count() > 0:
                    joystick = pygame.joystick.Joystick(0)
                    self.gamepad_connected.emit(True)
                    print("Gamepad connected")
                else:
                    pygame.time.wait(100)
                    continue

            if not joystick.get_init():
                joystick = None
                print("Gamepad dissconected")
                self.gamepad_connected.emit(False)
                continue

            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED and joystick is None:
                    joystick = pygame.joystick.Joystick(event.device_index)

                elif event.type == pygame.JOYBUTTONDOWN:
                    self.button_pressed.emit(event.button, True)

                elif event.type == pygame.JOYBUTTONUP:
                    self.button_pressed.emit(event.button, False)

                elif event.type == pygame.JOYAXISMOTION:
                    self.axis_moved.emit(event.axis, event.value)

            clock.tick(60)

    def stop(self):
        self._running = False
        self.wait()

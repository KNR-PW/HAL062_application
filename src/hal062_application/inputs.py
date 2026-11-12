import os

from PySide6.QtQmlFeatures import computed

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

from typing import TYPE_CHECKING, TypeVar

import pygame
from enums import ControlScheme, InputAction
from PySide6.QtCore import QEvent, QObject, QThread, Signal, Slot

if TYPE_CHECKING:
    # 1. What Basedpyright sees (perfectly typed dummy decorator)
    T = TypeVar("T")

    def auto_properties[T](cls: type[T]) -> type[T]: ...
else:
    # 2. What Python actually runs at runtime
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
    gamepad_connectedChanged = Signal()
    gamepad_enabledChanged = Signal()
    control_schemeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.gamepad_connected = False
        self.gamepad_enabled = True
        self.control_scheme = ControlScheme.DISABLED

    @computed("control_scheme")
    def control_scheme_name(self) -> str:
        return self.control_scheme.name.capitalize()


class InputManager(QObject):
    actionSignal = Signal(InputAction, bool)
    gamepadSignal = Signal(InputAction, float)

    def __init__(self, input_state: InputState):
        super().__init__()
        self.input_state = input_state

        self.keyboard_map = {
            "W": InputAction.MAIN_FORWARD,
            "S": InputAction.MAIN_BACKWARD,
            "A": InputAction.MAIN_LEFT,
            "D": InputAction.MAIN_RIGHT,
            "~": InputAction.TOGGLE_PAD,
            "1": InputAction.CS_NONE,
            "2": InputAction.CS_CHASIS,
            "3": InputAction.CS_MAINPULATOR,
            " ": InputAction.E_BRAKE,
        }

        self.analog_map = {
            0: InputAction.JOY_LS_X,
            1: InputAction.JOY_LS_Y,
            3: InputAction.JOY_RS_X,
            4: InputAction.JOY_RS_Y,
            2: InputAction.JOY_LT,
            5: InputAction.JOY_RT,
        }

        self.gamepad_map = {
            0: InputAction.JOY_A,
            1: InputAction.JOY_B,
            2: InputAction.JOY_X,
            3: InputAction.JOY_Y,
            4: InputAction.JOY_LB,
            5: InputAction.JOY_RB,
            6: InputAction.JOY_BB,
            7: InputAction.JOY_SB,
        }

    # --- RAW INPUT RECEIVERS ---
    @Slot(str)
    def handle_key_press(self, key_name):
        action = self.keyboard_map.get(key_name)
        if action is None:
            return

        if action == InputAction.TOGGLE_PAD:
            self.input_state.gamepad_enabled = not self.input_state.gamepad_enabled

        elif action == InputAction.CS_NONE:
            self.input_state.control_scheme = ControlScheme.DISABLED

        elif action == InputAction.CS_CHASIS:
            self.input_state.control_scheme = ControlScheme.CHASIS

        elif action == InputAction.CS_MAINPULATOR:
            self.input_state.control_scheme = ControlScheme.MANIPULATOR

        self.actionSignal.emit(action, True)

    @Slot(str)
    def handle_key_release(self, key_name):
        action = self.keyboard_map.get(key_name)
        if action is not None:
            self.actionSignal.emit(action, False)

    @Slot(int)
    def handle_gamepad_button(self, button_id, state):
        action = self.gamepad_map.get(button_id)
        if action is not None and self.input_state.gamepad_enabled:
            self.actionSignal.emit(action, state)

    @Slot(int, float)
    def handle_gamepad_axis(self, axis_id, value):
        action = self.analog_map.get(axis_id)
        if action is not None and self.input_state.gamepad_enabled:
            self.gamepadSignal.emit(action, value)


class GamepadWorker(QThread):
    button_pressed = Signal(int, bool)
    axis_moved = Signal(int, float)
    gamepad_connected = Signal(bool)
    gamepad_inactive = Signal()

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        pygame.init()
        pygame.joystick.init()
        joystick = None
        clock = pygame.time.Clock()
        disable_timer = 0

        while self._running:
            if joystick is None:
                print("trying to connect gamepad")
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
                disable_timer = 0
                if event.type == pygame.JOYDEVICEADDED and joystick is None:
                    joystick = pygame.joystick.Joystick(event.device_index)

                elif event.type == pygame.JOYBUTTONDOWN:
                    self.button_pressed.emit(event.button, True)

                elif event.type == pygame.JOYBUTTONUP:
                    self.button_pressed.emit(event.button, False)

                elif event.type == pygame.JOYAXISMOTION:
                    self.axis_moved.emit(event.axis, event.value)

            disable_timer += 1
            if disable_timer > 30 * 60:
                self.gamepad_inactive.emit()
                disable_timer = 0
            clock.tick(60)

    def stop(self):
        self._running = False
        self.wait()

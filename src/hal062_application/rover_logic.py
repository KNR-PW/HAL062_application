import time
from typing import Any

from connections import RoverAPI
from enums import ControlScheme, InputAction
from inputs import InputState
from PySide6.QtCore import QThread, Signal, Slot

ROVER_WIDTH = 0.91


class RoverLogic(QThread):
    # Binds the calculated speed to a signal
    speedSignal = Signal(float, float)

    def __init__(
        self,
        api: RoverAPI,
        input_state: InputState,
        parent=None,
    ):
        super().__init__(parent)
        self.api = api
        self.state = input_state
        self._is_running = True
        self.enable: Any = self.state.control_scheme == ControlScheme.CHASIS
        self.gamepad_mode = self.state.gamepad_connected and self.state.gamepad_enabled

        self.speed_l = 0
        self.speed_r = 0

        # Input states
        self.keys = {
            InputAction.MAIN_FORWARD: False,
            InputAction.MAIN_BACKWARD: False,
            InputAction.MAIN_LEFT: False,
            InputAction.MAIN_RIGHT: False,
            InputAction.E_BRAKE: False,
        }

        self.sticky_keys = self.keys.copy()
        self.key_speed = 0
        self.key_turn = 0

        self.gamepad = {
            InputAction.JOY_LT: 0.0,
            InputAction.JOY_RT: 0.0,
            InputAction.JOY_LS_X: 0.0,
        }

    @Slot(InputAction, bool)
    def handle_action_signal(self, action, state):
        if action not in self.keys:
            return
        self.keys[action] = state
        if not state:
            self.sticky_keys[action] = False

    @Slot(InputAction, float)
    def handle_gamepad_signal(self, axis, value):
        if axis in (InputAction.JOY_RT, InputAction.JOY_LT):
            self.gamepad[axis] = (1 + value) / 2

        elif axis == InputAction.JOY_LS_X:
            self.gamepad[axis] = value if abs(value) > 0.10 else 0.0

    @Slot()
    def handle_state_signal(self):
        self.enable = self.state.control_scheme == ControlScheme.CHASIS

        if self.state.gamepad_connected and self.state.gamepad_enabled:
            self.gamepad_mode = True
        else:
            self.gamepad[InputAction.JOY_LT] = 0.0
            self.gamepad[InputAction.JOY_RT] = 0.0
            self.gamepad[InputAction.JOY_LS_X] = 0.0
            self.gamepad_mode = False

    def _calculate_gamepad_speed(self):
        lt_value = self.gamepad[InputAction.JOY_LT]
        rt_value = self.gamepad[InputAction.JOY_RT]
        joy_ls_x_value: float = self.gamepad[InputAction.JOY_LS_X]

        if lt_value > 0 and rt_value > 0:  # e-brake on screenshot
            print("e-brake triggered")
            return [0.0, 0.0]

        spd_lin = rt_value - lt_value
        spd_ang = joy_ls_x_value / 3

        return [spd_lin, spd_ang]

    def _calculate_wasd_speed(self):
        ACCELERATION_STEP = 0.1  # Replaces / 10
        TURN_SCALAR = 1 / 6  # Replaces / 6
        MAX_SPEED = 1.0

        forward = self.keys[InputAction.MAIN_FORWARD] * ACCELERATION_STEP
        backward = -self.keys[InputAction.MAIN_BACKWARD] * ACCELERATION_STEP
        left = self.keys[InputAction.MAIN_LEFT]
        right = -self.keys[InputAction.MAIN_RIGHT]

        self.key_turn = (left + right) * TURN_SCALAR

        if forward and backward:
            acceleration = backward if self.key_speed >= 0 else forward
        else:
            acceleration = backward + forward

        target_speed = self.key_speed + acceleration
        target_speed = max(-MAX_SPEED, min(MAX_SPEED, target_speed))

        crossed_zero_backward = target_speed < 0 <= self.key_speed
        crossed_zero_forward = target_speed > 0 >= self.key_speed

        was_holding_backward = self.sticky_keys[InputAction.MAIN_BACKWARD]
        was_holding_forward = self.sticky_keys[InputAction.MAIN_FORWARD]

        if (crossed_zero_backward and was_holding_backward) or (
            crossed_zero_forward and was_holding_forward
        ):
            self.key_speed = 0.0
        else:
            self.key_speed = target_speed

        self.sticky_keys = self.keys.copy()

    def run(self):
        while self._is_running:
            if not self.enable:
                if self.speed_l != 0 or self.speed_r != 0:
                    self.key_speed = 0
                    self.key_turn = 0
                    self.speed_l = 0
                    self.speed_r = 0
                    self.api.set_speed(0, 0)

                time.sleep(0.1)
                continue

            if self.gamepad_mode:
                spd_lin, spd_ang = self._calculate_gamepad_speed()
                self.key_speed = 0
                self.key_turn = 0

            else:
                self._calculate_wasd_speed()
                spd_lin, spd_ang = self.key_speed, self.key_turn

            self.speed_l = spd_lin - spd_ang * (ROVER_WIDTH / 2)
            self.speed_r = spd_lin + spd_ang * (ROVER_WIDTH / 2)

            max_magnitude = max(abs(self.speed_l), abs(self.speed_r))
            if max_magnitude > 1.0:
                self.speed_l = self.speed_l / max_magnitude
                self.speed_r = self.speed_r / max_magnitude

            if self.keys[InputAction.E_BRAKE]:
                self.key_speed = 0
                self.key_turn = 0
                self.speed_l = 0
                self.speed_r = 0

            self.speedSignal.emit(self.speed_l, self.speed_r)
            self.api.set_speed(self.speed_l, self.speed_r)

            print(self.speed_l, self.speed_r)

            self.msleep(50)

    def stop(self):
        self._is_running = False
        self.wait()

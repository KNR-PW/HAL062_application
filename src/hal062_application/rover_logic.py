import time

from connections import RoverAPI
from inputs import InputManager
from PySide6.QtCore import QThread, Signal, Slot

ROVER_WIDTH = 0.91


class RoverLogic(QThread):
    # Binds the calculated speed to a signal
    speedSignal = Signal(float, float)

    def __init__(self, api: RoverAPI, input_manager: InputManager, parent=None):
        super().__init__(parent)
        self.api = api
        self.input_manager = input_manager
        self.action_map = input_manager.InputAction
        self._is_running = True
        self.enable = (
            self.input_manager.state.control_scheme
            == self.input_manager.state.ControlScheme.CHASIS
        )
        self.gamepad_mode = (
            self.input_manager.state.gamepad_connected
            and self.input_manager.state.gamepad_enabled
        )

        self.speed_l = 0
        self.speed_r = 0

        # Input states
        self.keys = {
            self.action_map.MAIN_FORWARD: False,
            self.action_map.MAIN_BACKWARD: False,
            self.action_map.MAIN_LEFT: False,
            self.action_map.MAIN_RIGHT: False,
            self.action_map.E_BRAKE: False,
        }

        self.sticky_keys = self.keys.copy()
        self.key_speed = 0
        self.key_turn = 0

        self.gamepad = {
            self.action_map.JOY_LT: 0.0,
            self.action_map.JOY_RT: 1.0,
            self.action_map.JOY_LS_X: 1.0,
        }

    @Slot(str, bool)
    def handle_action_signal(self, action, state):
        if action not in self.keys:
            return
        self.keys[action] = state
        if not state:
            self.sticky_keys[action] = False

    @Slot(str, float)
    def handle_gamepad_signal(self, axis, value):
        self.gamepad_dissconect_timer = 0
        if axis in (self.action_map.JOY_RT, self.action_map.JOY_LT):
            self.gamepad[axis] = (1 + value) / 2

        elif axis == self.action_map.JOY_LS_X:
            self.gamepad[axis] = value if value > 0.10 else 0.0

    @Slot()
    def handle_state_signal(self):
        self.enable = (
            self.input_manager.state.control_scheme
            == self.input_manager.state.ControlScheme.CHASIS
        )

        if (
            self.input_manager.state.gamepad_connected
            and self.input_manager.state.gamepad_enabled
        ):
            self.gamepad_mode = True
        else:
            self.gamepad[self.action_map.JOY_LT] = 0.0
            self.gamepad[self.action_map.JOY_RT] = 0.0
            self.gamepad[self.action_map.JOY_LS_X] = 0.0
            self.gamepad_mode = False

    def _calculate_gamepad_speed(self):
        lt_value = self.gamepad[self.action_map.JOY_LT]
        rt_value = self.gamepad[self.action_map.JOY_RT]
        joy_ls_x_value: float = self.gamepad[self.action_map.JOY_LS_X]

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

        forward = self.keys[self.action_map.MAIN_FORWARD] * ACCELERATION_STEP
        backward = -self.keys[self.action_map.MAIN_BACKWARD] * ACCELERATION_STEP
        left = self.keys[self.action_map.MAIN_LEFT]
        right = -self.keys[self.action_map.MAIN_RIGHT]

        self.key_turn = (left + right) * TURN_SCALAR

        if forward and backward:
            acceleration = backward if self.key_speed >= 0 else forward
        else:
            acceleration = backward + forward

        target_speed = self.key_speed + acceleration
        target_speed = max(-MAX_SPEED, min(MAX_SPEED, target_speed))

        crossed_zero_backward = target_speed < 0 <= self.key_speed
        crossed_zero_forward = target_speed > 0 >= self.key_speed

        was_holding_backward = self.sticky_keys[self.action_map.MAIN_BACKWARD]
        was_holding_forward = self.sticky_keys[self.action_map.MAIN_FORWARD]

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
                    self.speed_l = 0
                    self.spped_r = 0
                    self.api.set_speed(0, spd_r=0)

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

            if self.keys[self.action_map.E_BRAKE]:
                self.key_speed = 0
                self.key_turn = 0
                self.speed_l = 0
                self.speed_r = 0

            self.speedSignal.emit(self.speed_l, self.speed_r)
            self.api.set_speed(self.speed_l, self.speed_r)

            self.msleep(50)

    def stop(self):
        self._is_running = False
        self.wait()

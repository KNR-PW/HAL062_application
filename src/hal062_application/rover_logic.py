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
        self.gamepad_dissconect_timer = 0

        self.speed_l = 0
        self.speed_r = 0

        # Input states
        self.keys = {
            self.action_map.MAIN_FORWARD: False,
            self.action_map.MAIN_BACKWARD: False,
            self.action_map.MAIN_LEFT: False,
            self.action_map.MAIN_RIGHT: False,
        }

        self.gamepad = {
            self.action_map.JOY_LT: 0.0,
            self.action_map.JOY_RT: 1.0,
            self.action_map.JOY_LS_X: 1.0,
        }

    @Slot(str, bool)
    def handle_action_signal(self, action, state):
        if action in self.keys:
            self.keys[action] = state

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
            not self.input_manager.state.gamepad_connected
            or not self.input_manager.state.gamepad_enabled
        ):
            self.gamepad[self.action_map.JOY_LT] = 0.0
            self.gamepad[self.action_map.JOY_RT] = 0.0
            self.gamepad[self.action_map.JOY_LS_X] = 0.0

    def _calculate_gamepad_speed(self):
        lt_value = self.gamepad[self.action_map.JOY_LT]
        rt_value = self.gamepad[self.action_map.JOY_RT]
        joy_ls_x_value: float = self.gamepad[self.action_map.JOY_LS_X]

        if lt_value > 0 and rt_value > 0:  # e-brake on screenshot
            print("e-brake triggered")
            return [0.0, 0.0]

        spd_lin = rt_value - lt_value
        spd_ang = joy_ls_x_value

        slp_l = spd_lin - spd_ang * (ROVER_WIDTH / 2)
        slp_r = spd_lin + spd_ang * (ROVER_WIDTH / 2)

        return [slp_l, slp_r]

    def _calculate_wasd_speed(self):
        return [0.0, 0.0]

    def run(self):
        while self._is_running:
            if not self.enable:
                if self.speed_l != 0 or self.speed_r != 0:
                    self.speed_l = 0
                    self.spped_r = 0
                    self.api.set_speed(0, spd_r=0)

                time.sleep(0.1)
                continue

            if self.gamepad.values != {0}:
                spd_l, spd_r = self._calculate_gamepad_speed()

            else:
                spd_l, spd_r = self._calculate_wasd_speed()

            max_magnitude = max(abs(spd_l), abs(spd_r))
            if max_magnitude > 1.0:
                self.speed_l = spd_l / max_magnitude
                self.speed_r = spd_r / max_magnitude

            self.speedSignal.emit(self.speed_l, self.speed_r)
            self.api.set_speed(self.speed_l, self.speed_r)

            self.gamepad_dissconect_timer += 1
            if self.gamepad_dissconect_timer > 600:
                self.input_manager.state.gamepad_enabled = False

            print(self.speed_l, self.speed_r)
            self.msleep(50)

    def stop(self):
        self._is_running = False
        self.wait()

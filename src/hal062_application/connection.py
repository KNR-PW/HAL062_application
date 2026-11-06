from __future__ import annotations

import logging
import math
import os
import queue
import select
import socket
import threading
import time
from collections.abc import Sequence

from PySide6.QtCore import QThread, Signal, Slot

logger = logging.getLogger(__name__)

# Stałe protokołu i geometrii łazika (zgodne z hal_communication)
COMMUNICATION_FRAME_SIZE = 19
WHEEL_RAD = 0.1575
ROVER_WIDTH = 0.91

FRAME_ID_WHEEL_SPEED = 20
FRAME_ID_ENGINE_INIT = 22
FRAME_ID_LIGHT = 50

DEFAULT_ROVER_IP = os.environ.get("ROVER_IP", "192.168.2.69")
DEFAULT_ROVER_PORT = int(os.environ.get("ROVER_PORT", "8889"))

SEND_INTERVAL_SEC = 0.05  # 20 Hz (jak w ChassisControlNode)
RECONNECT_INTERVAL_SEC = 2.0


def build_standard_frame(frame_id: int, data: Sequence[int]) -> str:
    """Buduje 19-znakową ramkę ASCII hex '#<ID><DATA>' zgodną z comm_server.cpp."""
    if not (0 <= frame_id <= 0xFF):
        raise ValueError(f"Frame ID poza zakresem uint8: {frame_id}")
    if len(data) > 8:
        raise ValueError(f"Dane ramki nie mogą przekraczać 8 bajtów (otrzymano {len(data)})")

    hex_payload = "".join(f"{byte & 0xFF:02X}" for byte in (frame_id, *data))
    frame = f"#{hex_payload}"
    return frame.ljust(COMMUNICATION_FRAME_SIZE, "x")


def twist_to_wheel_units(linear_x: float, angular_z: float) -> tuple[int, int]:
    """Przelicza prędkość postępową (m/s) i kątową (rad/s) na jednostki kół L/P (jak w wheel_interface.py)."""
    spd_l = (linear_x - angular_z * ROVER_WIDTH) / WHEEL_RAD
    spd_r = (linear_x + angular_z * ROVER_WIDTH) / WHEEL_RAD

    spd_mb_unit_l = round(spd_l / (2.0 * math.pi) * 100.0)
    spd_mb_unit_r = round(spd_r / (2.0 * math.pi) * 100.0)

    if abs(spd_mb_unit_l) <= 1 and abs(spd_mb_unit_r) > 1:
        spd_mb_unit_l = -2
    if abs(spd_mb_unit_r) <= 1 and abs(spd_mb_unit_l) > 1:
        spd_mb_unit_r = -2

    spd_mb_unit_l = max(-128, min(127, spd_mb_unit_l))
    spd_mb_unit_r = max(-128, min(127, spd_mb_unit_r))
    return spd_mb_unit_l, spd_mb_unit_r


def build_wheel_frame(linear_x: float, angular_z: float) -> str:
    """Tworzy gotową ramkę sterowania kołami (ID 20 / 0x14)."""
    spd_l, spd_r = twist_to_wheel_units(linear_x, angular_z)
    return build_standard_frame(
        FRAME_ID_WHEEL_SPEED,
        [spd_l & 0xFF, spd_r & 0xFF, 0, 0, 0, 0, 0, 0],
    )


class TCPClient:
    """Klient TCP odpowiedzialny za utrzymanie połączenia z łazikiem i wymianę 19-znakowych ramek."""

    def __init__(self, ip: str = DEFAULT_ROVER_IP, port: int = DEFAULT_ROVER_PORT) -> None:
        self.ip = ip
        self.port = port
        self._sock: socket.socket | None = None
        self._recv_buffer = ""

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    def set_params(self, ip: str, port: int) -> None:
        self.ip = ip
        self.port = port

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._recv_buffer = ""

    def connect(self) -> str | None:
        """Nawiązuje połączenie TCP. Zwraca None w przypadku sukcesu lub treść błędu."""
        self.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(1.0)
        try:
            sock.connect((self.ip, self.port))
            sock.settimeout(0.2)
            self._sock = sock
            return None
        except OSError as exc:
            sock.close()
            return str(exc)

    def send_message(self, data: str) -> str | None:
        """Wysyła ramkę TCP. Zwraca None przy sukcesie lub opis błędu przy zerwaniu połączenia."""
        if self._sock is None:
            err = self.connect()
            if err is not None:
                return err

        assert self._sock is not None
        try:
            self._sock.sendall(data.encode("ascii"))
            return None
        except OSError as exc:
            self.close()
            return str(exc)

    def receive_frames(self) -> tuple[list[tuple[int, str]], bool]:
        """Odczytuje nieblokująco dostępne 19-bajtowe ramki zwrotne '#<ID><16_HEX>'.

        Zwraca krotkę (lista_ramek, czy_rozlaczono).
        """
        if self._sock is None:
            return [], False

        frames: list[tuple[int, str]] = []
        try:
            readable, _, _ = select.select([self._sock], [], [], 0.0)
            if not readable:
                return frames, False
            chunk = self._sock.recv(256)
            if not chunk:
                self.close()
                return frames, True
            self._recv_buffer += chunk.decode("ascii", errors="ignore")
        except (BlockingIOError, InterruptedError):
            return frames, False
        except OSError:
            self.close()
            return frames, True

        while True:
            start_pos = self._recv_buffer.find("#")
            if start_pos == -1:
                self._recv_buffer = ""
                break
            if len(self._recv_buffer) < start_pos + COMMUNICATION_FRAME_SIZE:
                if start_pos > 0:
                    self._recv_buffer = self._recv_buffer[start_pos:]
                break

            raw_frame = self._recv_buffer[start_pos : start_pos + COMMUNICATION_FRAME_SIZE]
            self._recv_buffer = self._recv_buffer[start_pos + COMMUNICATION_FRAME_SIZE :]
            try:
                frame_id = int(raw_frame[1:3], 16)
                payload = raw_frame[3:19]
                frames.append((frame_id, payload))
            except ValueError:
                continue

        return frames, False


class RoverConnectionService(QThread):
    """Serwis tłumaczący sygnał gamepadSignal na ramki sterujące wysyłane po TCP na łazika."""

    connectionStatusChanged = Signal(bool)
    telemetryUpdated = Signal(float, float)
    frameSent = Signal(str)
    transmissionReceived = Signal(int, str)

    def __init__(
        self,
        ip: str = DEFAULT_ROVER_IP,
        port: int = DEFAULT_ROVER_PORT,
        auto_init_chassis: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._client = TCPClient(ip, port)
        self._auto_init_chassis = auto_init_chassis

        self._lock = threading.Lock()
        self._forward_speed = 0.0
        self._reverse_speed = 0.0
        self._linear_x = 0.0
        self._angular_z = 0.0
        self._active = True
        self._pending_reconnect = False
        self._new_endpoint: tuple[str, int] | None = None

        self._cmd_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()

    @Slot(str, float)
    def handle_gamepad(self, action: str, value: float) -> None:
        """Odbiera akcje z InputManager.gamepadSignal i przelicza je na prędkości jak w ChassisControlNode."""
        with self._lock:
            if action == "speed":
                # Oś spustu (RT, oś 5): spoczynkowo -1.0, pełne wciśnięcie +1.0
                self._forward_speed = (value + 0.9) / 2.5 if value > -0.9 else 0.0
                self._linear_x = self._forward_speed - self._reverse_speed
            elif action == "reverse":
                # Oś lewego spustu (LT, oś 2): jazda wstecz
                self._reverse_speed = (value + 0.9) / 2.5 if value > -0.9 else 0.0
                self._linear_x = self._forward_speed - self._reverse_speed
            elif action == "turn":
                # Oś skrętu (lewy analog X, oś 0)
                self._angular_z = -value / 2.5 if abs(value) > 0.0 else 0.0

    @Slot(float, float)
    def set_velocity(self, linear_x: float, angular_z: float) -> None:
        with self._lock:
            self._forward_speed = max(0.0, linear_x)
            self._reverse_speed = max(0.0, -linear_x)
            self._linear_x = linear_x
            self._angular_z = angular_z

    @Slot()
    def stop_wheels(self) -> None:
        with self._lock:
            self._forward_speed = 0.0
            self._reverse_speed = 0.0
            self._linear_x = 0.0
            self._angular_z = 0.0
        self._cmd_queue.put(build_wheel_frame(0.0, 0.0))

    @Slot(bool)
    def set_active(self, active: bool) -> None:
        with self._lock:
            self._active = active
        if not active:
            self.stop_wheels()

    @Slot()
    def init_light(self) -> None:
        self._cmd_queue.put(build_standard_frame(FRAME_ID_LIGHT, [0, 0, 1, 1, 0, 0, 0, 0]))

    @Slot()
    def init_engine(self) -> None:
        self._cmd_queue.put(build_standard_frame(FRAME_ID_ENGINE_INIT, [1, 1, 1, 0, 0, 0, 0, 0]))

    @Slot()
    def init_chassis(self) -> None:
        self.init_light()
        self.init_engine()

    @Slot(str)
    def set_light(self, color: str) -> None:
        color_frames = {
            "red": [1, 1, 0, 0, 0, 0, 0, 0],
            "green": [1, 0, 0, 1, 0, 0, 0, 0],
            "blue": [0, 0, 1, 1, 0, 0, 0, 0],
        }
        payload = color_frames.get(color.lower())
        if payload is not None:
            self._cmd_queue.put(build_standard_frame(FRAME_ID_LIGHT, payload))

    @Slot(int, list)
    def send_custom_frame(self, frame_id: int, data: list[int]) -> None:
        self._cmd_queue.put(build_standard_frame(frame_id, data))

    @Slot(str, int)
    def update_connection_params(self, ip: str, port: int) -> None:
        with self._lock:
            self._new_endpoint = (ip, port)
            self._pending_reconnect = True

    def run(self) -> None:
        next_connect_attempt = 0.0
        logged_disconnect = False

        while not self._stop_event.is_set():
            tick_start = time.monotonic()

            with self._lock:
                if self._pending_reconnect and self._new_endpoint is not None:
                    ip, port = self._new_endpoint
                    self._pending_reconnect = False
                    self._new_endpoint = None
                    self._client.close()
                    self._client.set_params(ip, port)
                    self.connectionStatusChanged.emit(False)
                    next_connect_attempt = 0.0
                    logged_disconnect = False

                active = self._active
                linear_x = self._linear_x
                angular_z = self._angular_z

            if not self._client.is_connected:
                if tick_start >= next_connect_attempt:
                    err = self._client.connect()
                    if err is None:
                        logger.info("Połączono z łazikiem (%s:%d)", self._client.ip, self._client.port)
                        logged_disconnect = False
                        self.connectionStatusChanged.emit(True)
                        if self._auto_init_chassis:
                            self.init_chassis()
                    else:
                        if not logged_disconnect:
                            logger.warning(
                                "Brak połączenia z łazikiem (%s:%d): %s — ponawianie w tle...",
                                self._client.ip,
                                self._client.port,
                                err,
                            )
                            logged_disconnect = True
                        next_connect_attempt = time.monotonic() + RECONNECT_INTERVAL_SEC

            if self._client.is_connected:
                while True:
                    try:
                        queued_frame = self._cmd_queue.get_nowait()
                    except queue.Empty:
                        break
                    err = self._client.send_message(queued_frame)
                    if err is not None:
                        logger.warning("Utracono połączenie z łazikiem podczas wysyłki: %s", err)
                        self.connectionStatusChanged.emit(False)
                        next_connect_attempt = time.monotonic() + RECONNECT_INTERVAL_SEC
                        break
                    self.frameSent.emit(queued_frame)

            if self._client.is_connected and active:
                wheel_frame = build_wheel_frame(linear_x, angular_z)
                err = self._client.send_message(wheel_frame)
                if err is not None:
                    logger.warning("Utracono połączenie z łazikiem: %s", err)
                    self.connectionStatusChanged.emit(False)
                    next_connect_attempt = time.monotonic() + RECONNECT_INTERVAL_SEC
                else:
                    self.frameSent.emit(wheel_frame)
                    self.telemetryUpdated.emit(linear_x, angular_z)

            if self._client.is_connected:
                received, disconnected = self._client.receive_frames()
                for frame_id, payload in received:
                    self.transmissionReceived.emit(frame_id, payload)
                if disconnected:
                    logger.warning("Połączenie z łazikiem zostało zamknięte przez zdalny host")
                    self.connectionStatusChanged.emit(False)
                    next_connect_attempt = time.monotonic() + RECONNECT_INTERVAL_SEC

            elapsed = time.monotonic() - tick_start
            remaining = max(0.0, SEND_INTERVAL_SEC - elapsed)
            self._stop_event.wait(remaining)

        if self._client.is_connected:
            self._client.send_message(build_wheel_frame(0.0, 0.0))
            self._client.close()
            self.connectionStatusChanged.emit(False)

    def stop(self) -> None:
        self._stop_event.set()
        self.wait()

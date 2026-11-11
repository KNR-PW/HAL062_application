from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket


class TcpClient(QObject):
    def __init__(self, ip, port, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.socket.connectToHost(ip, port)
        self.socket.setSocketOption(QAbstractSocket.SocketOption.LowDelayOption, 1)

        # Connect QTcpSocket signals to handler methods
        self.socket.connected.connect(self.on_connected)
        # self.socket.readyRead.connect(self.on_ready_read)
        self.socket.errorOccurred.connect(self.on_error)

    @Slot()
    def on_connected(self):
        print("Connected to server successfully!")
        # Example: send initial payload
        # self.send_command("CONNECTED")

    # @Slot()
    # def on_ready_read(self):
    #     # Triggered automatically whenever data arrives from the socket
    #     while self.socket.bytesAvailable() > 0:
    #         data = self.socket.readAll().data().decode("utf-8")
    #         print(f"Received from TCP: {data}")

    @Slot(int, list)
    def send_command(self, can_id: int, command: list[int]):
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            message = f"#{can_id:02X}{''.join(f'{b:02X}' for b in command)}"
            self.socket.write(message.encode("utf-8"))
            self.socket.flush()

    @Slot(QAbstractSocket.SocketError)
    def on_error(self, socket_error):
        print(f"TCP Error: {self.socket.errorString()}")


class RoverAPI(QObject):
    commandSignal = Signal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)

    def set_speed(self, spd_l, spd_r):
        command = [0] * 8
        command[0] = round(spd_l * 100) & 0xFF
        command[1] = round(spd_r * 100) & 0xFF
        self.commandSignal.emit(0x14, command)

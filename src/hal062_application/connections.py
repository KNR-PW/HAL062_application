from PySide6.QtCore import QObject, Slot
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket


class RoverTcpClient(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = QTcpSocket(self)
        self.socket.connectToHost("127.0.0.1", 8888)

        # Connect QTcpSocket signals to handler methods
        self.socket.connected.connect(self.on_connected)
        # self.socket.readyRead.connect(self.on_ready_read)
        self.socket.errorOccurred.connect(self.on_error)

    @Slot()
    def on_connected(self):
        print("Connected to server successfully!")
        # Example: send initial payload
        self.send_command("CONNECTED")

    # @Slot()
    # def on_ready_read(self):
    #     # Triggered automatically whenever data arrives from the socket
    #     while self.socket.bytesAvailable() > 0:
    #         data = self.socket.readAll().data().decode("utf-8")
    #         print(f"Received from TCP: {data}")

    def send_command(self, message: str):
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            self.socket.write(message.encode("utf-8"))

    @Slot(QAbstractSocket.SocketError)
    def on_error(self, socket_error):
        print(f"TCP Error: {self.socket.errorString()}")


class RoverAPI:
    def set_speed(self, spd_l, spd_r): ...

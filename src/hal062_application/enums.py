from enum import IntEnum, auto

from PySide6.QtCore import QEnum, QObject
from PySide6.QtQml import QmlElement

QML_IMPORT_NAME = "com.halapp.enums"
QML_IMPORT_MAJOR_VERSION = 1


class InputAction(IntEnum):
    MAIN_FORWARD = 0
    MAIN_BACKWARD = auto()
    MAIN_LEFT = auto()
    MAIN_RIGHT = auto()
    E_BRAKE = auto()

    TOGGLE_PAD = auto()

    CS_NONE = auto()
    CS_CHASIS = auto()
    CS_MAINPULATOR = auto()

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


class ControlScheme(IntEnum):
    DISABLED = 0
    CHASIS = auto()
    MANIPULATOR = auto()


@QmlElement
class QMLEnums(QObject):
    QEnum(InputAction)
    QEnum(ControlScheme)

"""The Mac's audio inputs, and the saved pick: kept by device id (the list reorders and inputs
come and go), falling back to the system default when the saved one is gone."""
from PySide6.QtMultimedia import QAudioDevice, QMediaDevices


def device_id(dev: QAudioDevice) -> str:
    return bytes(dev.id()).hex()


def inputs() -> list[tuple[str, str]]:
    """(id, name) for every input, in the system's order."""
    return [(device_id(d), d.description()) for d in QMediaDevices.audioInputs()]


def resolve(saved_id: str | None) -> QAudioDevice | None:
    """The saved input if it's still there, else the default; None when the Mac has no input."""
    devices = QMediaDevices.audioInputs()
    for d in devices:
        if saved_id and device_id(d) == saved_id:
            return d
    default = QMediaDevices.defaultAudioInput()
    if not default.isNull():
        return default
    return devices[0] if devices else None

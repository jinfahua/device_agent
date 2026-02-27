"""
Tools layer - Device management and control tools.
"""

from .mqtt_tools import MQTTConnectTool, MQTTPublishTool, MQTTSubscribeTool
from .device_tools import DeviceStateGetTool, DeviceStateSetTool, DeviceListTool
from .control_tools import DeviceControlTool

__all__ = [
    "MQTTConnectTool",
    "MQTTPublishTool",
    "MQTTSubscribeTool",
    "DeviceStateGetTool",
    "DeviceStateSetTool",
    "DeviceListTool",
    "DeviceControlTool",
]


def get_default_tools(runtime) -> list:
    """Get the default set of tools for the runtime."""
    return [
        MQTTConnectTool(runtime),
        MQTTPublishTool(runtime),
        MQTTSubscribeTool(runtime),
        DeviceStateGetTool(runtime),
        DeviceStateSetTool(runtime),
        DeviceListTool(runtime),
        DeviceControlTool(runtime),
    ]

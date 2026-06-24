from __future__ import annotations

import logging
from typing import Any, Optional, Protocol

from .config import AppConfig

logger = logging.getLogger(__name__)


class ReadingSink(Protocol):
    def connect(self) -> None:
        ...

    def close(self) -> None:
        ...

    def publish_reading(self, address: str, name: Optional[str], rssi: Optional[int], payload: dict[str, Any]) -> None:
        ...


class MultiBridge:
    def __init__(self, config: AppConfig) -> None:
        self.sinks: list[ReadingSink] = []
        if config.mqtt.enabled:
            from .mqtt import MqttBridge

            self.sinks.append(MqttBridge(config))
        if config.influxdb.enabled:
            from .influxdb import InfluxBridge

            self.sinks.append(InfluxBridge(config))
        if config.venus_dbus.enabled:
            from .venus_dbus import VenusDbusBridge

            self.sinks.append(VenusDbusBridge(config))

    def connect(self) -> None:
        for sink in self.sinks:
            sink.connect()

    def close(self) -> None:
        for sink in reversed(self.sinks):
            try:
                sink.close()
            except Exception:
                logger.exception("Failed to close %s", sink.__class__.__name__)

    def publish_reading(self, address: str, name: Optional[str], rssi: Optional[int], payload: dict[str, Any]) -> None:
        for sink in self.sinks:
            try:
                sink.publish_reading(address, name, rssi, payload)
            except Exception:
                logger.exception("Failed to publish reading via %s", sink.__class__.__name__)

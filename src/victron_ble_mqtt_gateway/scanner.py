from __future__ import annotations

import json
import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from victron_ble.devices import Device, detect_device_type
from victron_ble.exceptions import AdvertisementKeyMissingError, UnknownDeviceError
from victron_ble.scanner import BaseScanner, DeviceDataEncoder

from .config import DeviceConfig
from .bridge import MultiBridge

logger = logging.getLogger(__name__)


class VictronMqttScanner(BaseScanner):
    def __init__(self, devices: list[DeviceConfig], bridge: MultiBridge) -> None:
        super().__init__()
        self._bridge = bridge
        self._device_configs = {device.normalized_address: device for device in devices}
        self._known_devices: dict[str, Device] = {}

    async def start(self) -> None:
        logger.info("Scanning for Victron Instant Readout advertisements from %s device(s)", len(self._device_configs))
        await super().start()

    def get_device(self, ble_device: BLEDevice, raw_data: bytes) -> Device:
        address = ble_device.address.lower()
        if address not in self._known_devices:
            device_config = self._device_configs.get(address)
            if not device_config:
                raise AdvertisementKeyMissingError(f"No key configured for {address}")

            device_klass = detect_device_type(raw_data)
            if not device_klass:
                raise UnknownDeviceError(f"Could not identify device type for {ble_device.address}")

            self._known_devices[address] = device_klass(device_config.advertisement_key)

        return self._known_devices[address]

    def callback(self, ble_device: BLEDevice, raw_data: bytes, advertisement: AdvertisementData) -> None:
        address = ble_device.address.lower()
        if address not in self._device_configs:
            return

        logger.debug("Received advertisement from %s: %s", address, raw_data.hex())
        try:
            device = self.get_device(ble_device, raw_data)
            parsed = device.parse(raw_data)
        except AdvertisementKeyMissingError:
            return
        except UnknownDeviceError as exc:
            logger.warning("%s", exc)
            return
        except Exception:
            logger.exception("Failed to parse Victron advertisement from %s", address)
            return

        payload = _to_plain_dict(parsed)
        self._bridge.publish_reading(
            address=address,
            name=ble_device.name,
            rssi=advertisement.rssi,
            payload=payload,
        )


def _to_plain_dict(value: Any) -> dict[str, Any]:
    return json.loads(json.dumps(value, cls=DeviceDataEncoder))

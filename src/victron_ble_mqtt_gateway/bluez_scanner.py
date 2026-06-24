from __future__ import annotations

import json
import logging
from typing import Any

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
from victron_ble.devices import Device, detect_device_type
from victron_ble.scanner import DeviceDataEncoder

from .config import DeviceConfig, normalize_ble_address
from .bridge import MultiBridge

logger = logging.getLogger(__name__)

BLUEZ = "org.bluez"
DEVICE_IFACE = "org.bluez.Device1"
ADAPTER_IFACE = "org.bluez.Adapter1"
PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
OBJECT_MANAGER_IFACE = "org.freedesktop.DBus.ObjectManager"
VICTRON_COMPANY_ID = 0x02E1


class BluezVictronScanner:
    def __init__(self, devices: list[DeviceConfig], bridge: MultiBridge, adapter_path: str = "/org/bluez/hci0") -> None:
        self.devices = {device.normalized_address: device for device in devices}
        self.bridge = bridge
        self.adapter_path = adapter_path
        self.bus: Any = None
        self.adapter: Any = None
        self.mainloop: Any = None
        self._known_devices: dict[str, Device] = {}
        self._seen_data: set[bytes] = set()

    async def start(self) -> None:
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.adapter = dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), ADAPTER_IFACE)

        self.bus.add_signal_receiver(
            self._interfaces_added,
            dbus_interface=OBJECT_MANAGER_IFACE,
            signal_name="InterfacesAdded",
        )
        self.bus.add_signal_receiver(
            self._properties_changed,
            dbus_interface=PROPERTIES_IFACE,
            signal_name="PropertiesChanged",
            path_keyword="path",
        )

        logger.info("Starting BlueZ LE discovery on %s", self.adapter_path)
        self.adapter.SetDiscoveryFilter({
            "Transport": dbus.String("le"),
            "DuplicateData": dbus.Boolean(True),
        })
        self.adapter.StartDiscovery()
        self.mainloop = GLib.MainLoop()
        GLib.idle_add(self._log_ready)
        self.mainloop.run()

    async def stop(self) -> None:
        if self.adapter is not None:
            try:
                self.adapter.StopDiscovery()
            except Exception:
                logger.exception("Failed to stop BlueZ discovery")
        if self.mainloop is not None:
            self.mainloop.quit()

    def _log_ready(self) -> bool:
        logger.info("Listening for Victron BLE advertisements from %s device(s)", len(self.devices))
        return False

    def _interfaces_added(self, path: str, interfaces: dict[str, Any]) -> None:
        props = interfaces.get(DEVICE_IFACE)
        if props:
            self._handle_device(path, props)

    def _properties_changed(self, interface: str, changed: dict[str, Any], invalidated: list[str], path: str | None = None) -> None:
        if interface == DEVICE_IFACE:
            self._handle_device(path or "", changed)

    def _handle_device(self, path: str, props: dict[str, Any]) -> None:
        manufacturer = props.get("ManufacturerData")
        if not manufacturer or VICTRON_COMPANY_ID not in manufacturer:
            return

        raw_data = bytes(manufacturer[VICTRON_COMPANY_ID])
        if not raw_data.startswith(b"\x10"):
            return
        if raw_data in self._seen_data:
            return
        if len(self._seen_data) > 1000:
            self._seen_data.clear()
        self._seen_data.add(raw_data)

        address = _address_from_props_or_path(props, path)
        normalized_address = normalize_ble_address(address or "")
        if not address or normalized_address not in self.devices:
            logger.debug(
                "Ignoring unconfigured Victron device %s normalized=%s configured=%s: %s",
                address,
                normalized_address,
                sorted(self.devices.keys()),
                raw_data.hex(),
            )
            return

        rssi = props.get("RSSI")
        name = props.get("Name") or props.get("Alias")
        try:
            device = self._get_device(normalized_address, raw_data)
            parsed = device.parse(raw_data)
            payload = json.loads(json.dumps(parsed, cls=DeviceDataEncoder))
        except Exception:
            logger.exception("Failed to parse Victron advertisement from %s: %s", address, raw_data.hex())
            return

        logger.info("Parsed Victron advertisement from %s: %s", address, payload)
        self.bridge.publish_reading(address=normalized_address, name=name, rssi=int(rssi) if rssi is not None else None, payload=payload)

    def _get_device(self, address: str, raw_data: bytes) -> Device:
        normalized = normalize_ble_address(address)
        if normalized not in self._known_devices:
            device_config = self.devices[normalized]
            device_klass = detect_device_type(raw_data)
            if not device_klass:
                raise ValueError(f"Could not identify Victron device type for {address}: {raw_data.hex()}")
            self._known_devices[normalized] = device_klass(device_config.advertisement_key)
        return self._known_devices[normalized]


def _address_from_props_or_path(props: dict[str, Any], path: str) -> str | None:
    address = props.get("Address")
    if address:
        return str(address)
    marker = "/dev_"
    if marker in path:
        return path.rsplit(marker, 1)[1].replace("_", ":")
    return None

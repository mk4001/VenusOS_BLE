from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Any, Optional

from .config import AppConfig, DeviceConfig
from .topics import clean_topic_part, flatten_payload

logger = logging.getLogger(__name__)


class VenusDbusBridge:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.devices_by_address = {device.normalized_address: device for device in config.devices}
        self.services_by_address: dict[str, Any] = {}
        self.last_seen_by_address: dict[str, float] = {}
        self.mainloop: Any = None
        self.thread: Optional[threading.Thread] = None
        self.GLib: Any = None
        self.dbus: Any = None

    def connect(self) -> None:
        self._load_venus_modules()
        for index, device in enumerate(self.config.devices):
            self.services_by_address[device.normalized_address] = self._create_service(device, index)

        self.GLib.timeout_add_seconds(10, self._check_connected_timeouts)
        self.mainloop = self.GLib.MainLoop()
        self.thread = threading.Thread(target=self.mainloop.run, name="venus-dbus-mainloop", daemon=True)
        self.thread.start()
        logger.info("Publishing %s Venus D-Bus service(s)", len(self.services_by_address))

    def close(self) -> None:
        if self.mainloop is not None:
            self.mainloop.quit()
        if self.thread is not None:
            self.thread.join(timeout=2)

    def publish_reading(self, address: str, name: Optional[str], rssi: Optional[int], payload: dict[str, Any]) -> None:
        normalized = address.lower()
        service = self.services_by_address[normalized]
        flat = flatten_payload(payload)
        logger.info("Updating Venus D-Bus service for %s with %s", normalized, flat)
        self._update_battery_service(normalized, service, flat, rssi)

    def _load_venus_modules(self) -> None:
        vedbus_path = self.config.venus_dbus.vedbus_path
        if vedbus_path and vedbus_path not in sys.path:
            sys.path.insert(0, vedbus_path)

        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        from gi.repository import GLib
        from vedbus import VeDbusService

        DBusGMainLoop(set_as_default=True)
        self.GLib = GLib
        self.dbus = dbus
        self.VeDbusService = VeDbusService

    def _create_service(self, device: DeviceConfig, index: int) -> Any:
        if device.device_type in ("orion_xs", "dcdc", "dc_dc"):
            return self._create_orion_xs_service(device, index)
        if device.device_type in ("smartsolar", "solar_charger", "solarcharger", "mppt"):
            return self._create_solar_charger_service(device, index)
        if device.device_type in ("smartcharger", "ac_charger", "charger"):
            return self._create_ac_charger_service(device, index)
        return self._create_battery_service(device, index)

    def _new_service(self, service_name: str) -> Any:
        # dbus.SystemBus() returns a shared connection. Multiple VeDbusService
        # instances on that connection collide on object path '/'. Use a private
        # connection per service so battery/dcdc/etc can coexist in one process.
        try:
            return self.VeDbusService(service_name, bus=self.dbus.SystemBus(private=True))
        except TypeError:
            logger.warning("VeDbusService does not accept a bus parameter; falling back to shared bus")
            return self.VeDbusService(service_name)

    def _add_common_paths(self, service: Any, device: DeviceConfig, device_instance: int) -> None:
        service.add_path("/Mgmt/ProcessName", "victron-ble-mqtt-gateway")
        service.add_path("/Mgmt/ProcessVersion", "0.1.0")
        service.add_path("/Mgmt/Connection", "Bluetooth LE")
        service.add_path("/DeviceInstance", device_instance)
        service.add_path("/ProductName", device.name)
        service.add_path("/ProductId", int(self.config.venus_dbus.product_id))
        service.add_path("/Connected", 0)
        service.add_path("/CustomName", device.name)

    def _create_battery_service(self, device: DeviceConfig, index: int) -> Any:
        service_name = f"{self.config.venus_dbus.service_prefix}.battery.{clean_topic_part(device.id)}"
        device_instance = self.config.venus_dbus.device_instance_start + index
        service = self._new_service(service_name)
        self._add_common_paths(service, device, device_instance)
        service.add_path("/Dc/0/Voltage", None)
        service.add_path("/Dc/0/Current", None)
        service.add_path("/Dc/0/Power", None)
        service.add_path("/Dc/0/Temperature", None)
        service.add_path("/Soc", None)
        service.add_path("/DeviceType", "battery")
        return service

    def _create_orion_xs_service(self, device: DeviceConfig, index: int) -> Any:
        service_name = f"{self.config.venus_dbus.service_prefix}.dcdc.{clean_topic_part(device.id)}"
        device_instance = self.config.venus_dbus.device_instance_start + index
        service = self._new_service(service_name)
        self._add_common_paths(service, device, device_instance)
        service.add_path("/DeviceType", "orion_xs")
        service.add_path("/Capabilities/Capabilities1", 0)
        service.add_path("/Mode", 1)
        service.add_path("/State", None)
        service.add_path("/ErrorCode", None)
        service.add_path("/DeviceOffReason", None)
        service.add_path("/Settings/DeviceFunction", 1)
        service.add_path("/Settings/OutputBattery", 0)
        service.add_path("/Dc/0/Voltage", None)
        service.add_path("/Dc/0/Current", None)
        service.add_path("/Dc/0/Power", None)
        service.add_path("/Dc/In/V", None)
        service.add_path("/Dc/In/I", None)
        service.add_path("/Dc/In/P", None)
        return service

    def _create_solar_charger_service(self, device: DeviceConfig, index: int) -> Any:
        service_name = f"{self.config.venus_dbus.service_prefix}.solarcharger.{clean_topic_part(device.id)}"
        device_instance = self.config.venus_dbus.device_instance_start + index
        service = self._new_service(service_name)
        self._add_common_paths(service, device, device_instance)
        service.add_path("/DeviceType", "solarcharger")
        service.add_path("/Mode", 1)
        service.add_path("/State", None)
        service.add_path("/ErrorCode", None)
        service.add_path("/Dc/0/Voltage", None)
        service.add_path("/Dc/0/Current", None)
        service.add_path("/Dc/0/Power", None)
        service.add_path("/Yield/Power", None)
        service.add_path("/Yield/User", None)
        service.add_path("/History/Daily/0/Yield", None)
        service.add_path("/Load/I", None)
        return service

    def _create_ac_charger_service(self, device: DeviceConfig, index: int) -> Any:
        service_name = f"{self.config.venus_dbus.service_prefix}.charger.{clean_topic_part(device.id)}"
        device_instance = self.config.venus_dbus.device_instance_start + index
        service = self._new_service(service_name)
        self._add_common_paths(service, device, device_instance)
        service.add_path("/DeviceType", "charger")
        service.add_path("/Mode", 1)
        service.add_path("/State", None)
        service.add_path("/ErrorCode", None)
        service.add_path("/NrOfOutputs", 3)
        service.add_path("/Temperature", None)
        service.add_path("/Ac/In/1/Current", None)
        service.add_path("/Dc/0/Voltage", None)
        service.add_path("/Dc/0/Current", None)
        service.add_path("/Dc/0/Power", None)
        service.add_path("/Dc/1/Voltage", None)
        service.add_path("/Dc/1/Current", None)
        service.add_path("/Dc/1/Power", None)
        service.add_path("/Dc/2/Voltage", None)
        service.add_path("/Dc/2/Current", None)
        service.add_path("/Dc/2/Power", None)
        return service

    def _check_connected_timeouts(self) -> bool:
        now = time.monotonic()
        timeout = max(1, int(self.config.venus_dbus.connected_timeout_seconds))
        for address, service in self.services_by_address.items():
            last_seen = self.last_seen_by_address.get(address)
            if last_seen is None or now - last_seen > timeout:
                if service["/Connected"] != 0:
                    logger.warning("No BLE advertisement from %s for %ss; marking disconnected", address, timeout)
                service["/Connected"] = 0
        return True

    def _update_battery_service(self, address: str, service: Any, flat: dict[str, Any], rssi: Optional[int]) -> bool:
        self.last_seen_by_address[address] = time.monotonic()

        device_type = service["/DeviceType"]
        logger.debug("D-Bus update target device_type=%s address=%s", device_type, address)
        if device_type == "orion_xs":
            self._update_orion_xs_service(service, flat)
        elif device_type == "solarcharger":
            self._update_solar_charger_service(service, flat)
        elif device_type == "charger":
            self._update_ac_charger_service(service, flat)
        else:
            self._update_battery_monitor_service(service, flat)

        service["/Connected"] = 1
        return False

    def _update_battery_monitor_service(self, service: Any, flat: dict[str, Any]) -> None:
        voltage = _first_number(flat, "voltage", "battery_voltage", "dc_0_voltage")
        current = _first_number(flat, "current", "battery_current", "dc_0_current")
        power = _first_number(flat, "power", "battery_power", "dc_0_power")
        soc = _first_number(flat, "soc", "state_of_charge")
        temperature = _first_number(flat, "temperature", "battery_temperature")

        if power is None and voltage is not None and current is not None:
            power = voltage * current

        logger.info("Battery values voltage=%s current=%s power=%s soc=%s temperature=%s", voltage, current, power, soc, temperature)
        if voltage is not None:
            service["/Dc/0/Voltage"] = round(voltage, 3)
        if current is not None:
            service["/Dc/0/Current"] = round(current, 3)
        if power is not None:
            service["/Dc/0/Power"] = round(power, 3)
        if soc is not None:
            service["/Soc"] = round(soc, 2)
        if temperature is not None:
            service["/Dc/0/Temperature"] = round(temperature, 2)

    def _update_solar_charger_service(self, service: Any, flat: dict[str, Any]) -> None:
        battery_voltage = _first_number(flat, "battery_voltage", "voltage", "dc_0_voltage")
        battery_current = _first_number(flat, "battery_charging_current", "current", "dc_0_current")
        solar_power = _first_number(flat, "solar_power", "yield_power")
        yield_today_wh = _first_number(flat, "yield_today")
        load_current = _first_number(flat, "external_device_load", "load_current")
        state = flat.get("charge_state") or flat.get("device_state")
        error = flat.get("charger_error")

        logger.info(
            "SmartSolar values battery_v=%s battery_a=%s solar_w=%s yield_today_wh=%s load_a=%s state=%s error=%s",
            battery_voltage,
            battery_current,
            solar_power,
            yield_today_wh,
            load_current,
            state,
            error,
        )
        if battery_voltage is not None:
            service["/Dc/0/Voltage"] = round(battery_voltage, 3)
        if battery_current is not None:
            service["/Dc/0/Current"] = round(battery_current, 3)
        if battery_voltage is not None and battery_current is not None:
            service["/Dc/0/Power"] = round(battery_voltage * battery_current, 3)
        if solar_power is not None:
            service["/Yield/Power"] = round(solar_power, 3)
        if yield_today_wh is not None:
            yield_today_kwh = yield_today_wh / 1000.0
            service["/Yield/User"] = round(yield_today_kwh, 3)
            service["/History/Daily/0/Yield"] = round(yield_today_kwh, 3)
        if load_current is not None:
            service["/Load/I"] = round(load_current, 3)
        if state is not None:
            service["/State"] = _state_to_dbus_value(state)
        if error is not None:
            service["/ErrorCode"] = _enum_or_value(error)


    def _update_ac_charger_service(self, service: Any, flat: dict[str, Any]) -> None:
        state = flat.get("charge_state") or flat.get("device_state")
        error = flat.get("charger_error")
        temperature = _first_number(flat, "temperature")
        ac_current = _first_number(flat, "ac_current")

        logger.info(
            "SmartCharger values state=%s error=%s temperature=%s ac_current=%s",
            state,
            error,
            temperature,
            ac_current,
        )

        if state is not None:
            service["/State"] = _state_to_dbus_value(state)
        if error is not None:
            service["/ErrorCode"] = _enum_or_value(error)
        if temperature is not None:
            service["/Temperature"] = round(temperature, 2)
        if ac_current is not None:
            service["/Ac/In/1/Current"] = round(ac_current, 3)

        for index in range(3):
            output_number = index + 1
            voltage = _first_number(flat, f"output_voltage{output_number}")
            current = _first_number(flat, f"output_current{output_number}")
            base_path = f"/Dc/{index}"
            if voltage is not None:
                service[f"{base_path}/Voltage"] = round(voltage, 3)
            if current is not None:
                service[f"{base_path}/Current"] = round(current, 3)
            if voltage is not None and current is not None:
                service[f"{base_path}/Power"] = round(voltage * current, 3)


    def _update_orion_xs_service(self, service: Any, flat: dict[str, Any]) -> None:
        input_voltage = _first_number(flat, "input_voltage")
        input_current = _first_number(flat, "input_current")
        output_voltage = _first_number(flat, "output_voltage")
        output_current = _first_number(flat, "output_current")
        state = flat.get("charge_state") or flat.get("device_state")
        error = flat.get("charger_error")
        off_reason = flat.get("off_reason")

        logger.info(
            "Orion XS values in_v=%s in_a=%s out_v=%s out_a=%s state=%s error=%s off_reason=%s",
            input_voltage,
            input_current,
            output_voltage,
            output_current,
            state,
            error,
            off_reason,
        )
        if input_voltage is not None:
            service["/Dc/In/V"] = round(input_voltage, 3)
        if input_current is not None:
            service["/Dc/In/I"] = round(input_current, 3)
        if input_voltage is not None and input_current is not None:
            service["/Dc/In/P"] = round(input_voltage * input_current, 3)
        if output_voltage is not None:
            service["/Dc/0/Voltage"] = round(output_voltage, 3)
        if output_current is not None:
            service["/Dc/0/Current"] = round(output_current, 3)
        if output_voltage is not None and output_current is not None:
            service["/Dc/0/Power"] = round(output_voltage * output_current, 3)
        if state is not None:
            service["/State"] = _state_to_dbus_value(state)
        if error is not None:
            service["/ErrorCode"] = _enum_or_value(error)
        if off_reason is not None:
            service["/DeviceOffReason"] = _enum_or_value(off_reason)


def _first_number(values: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = values.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _enum_or_value(value: Any) -> Any:
    if isinstance(value, str):
        return value
    enum_name = getattr(value, "name", None)
    if enum_name is not None:
        return enum_name.lower()
    return value


def _state_to_dbus_value(value: Any) -> Any:
    if isinstance(value, str):
        mapping = {
            "off": 0,
            "fault": 2,
            "bulk": 3,
            "absorption": 4,
            "float": 5,
            "storage": 6,
            "power_supply": 11,
        }
        return mapping.get(value.lower(), value)
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return value

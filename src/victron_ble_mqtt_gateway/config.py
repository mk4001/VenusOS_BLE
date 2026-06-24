from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Venus OS can ship Python without tomllib
    tomllib = None


@dataclass(frozen=True)
class MqttConfig:
    enabled: bool = False
    host: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    client_id: str = "victron-ble-mqtt-gateway"
    base_topic: str = "victron"
    retain: bool = True
    qos: int = 0
    tls: bool = False


@dataclass(frozen=True)
class InfluxConfig:
    enabled: bool = False
    url: str = "http://127.0.0.1:8086"
    token: str = ""
    org: str = ""
    bucket: str = "victron"
    measurement: str = "victron_ble"
    timeout_ms: int = 5000


@dataclass(frozen=True)
class VenusDbusConfig:
    enabled: bool = True
    vedbus_path: str = "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python"
    service_prefix: str = "com.victronenergy"
    device_instance_start: int = 42
    product_id: int = 0xFFFF
    connected_timeout_seconds: int = 180


@dataclass(frozen=True)
class BridgeConfig:
    publish_metric_topics: bool = True
    publish_json_state: bool = True
    publish_home_assistant_discovery: bool = False
    home_assistant_prefix: str = "homeassistant"
    offline_after_seconds: int = 180


@dataclass(frozen=True)
class DeviceConfig:
    id: str
    name: str
    address: str
    advertisement_key: str
    device_type: str = "battery"

    @property
    def normalized_address(self) -> str:
        return normalize_ble_address(self.address)


@dataclass(frozen=True)
class AppConfig:
    mqtt: MqttConfig
    influxdb: InfluxConfig
    venus_dbus: VenusDbusConfig
    bridge: BridgeConfig
    devices: list[DeviceConfig]


def normalize_ble_address(address: str) -> str:
    hex_chars = "".join(ch for ch in address.strip().lower() if ch in "0123456789abcdef")
    if len(hex_chars) == 12:
        return ":".join(hex_chars[index:index + 2] for index in range(0, 12, 2))
    return address.strip().lower().replace("-", ":")


def load_config(path: Union[str, Path]) -> AppConfig:
    config_path = Path(path)
    if tomllib is not None:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    else:
        raw = _parse_simple_toml(config_path.read_text())

    mqtt = MqttConfig(**raw.get("mqtt", {}))
    influxdb = InfluxConfig(**raw.get("influxdb", {}))
    venus_dbus = VenusDbusConfig(**raw.get("venus_dbus", {}))
    bridge = BridgeConfig(**raw.get("bridge", {}))
    devices = [_parse_device(item) for item in raw.get("devices", [])]

    if not mqtt.enabled and not influxdb.enabled and not venus_dbus.enabled:
        raise ValueError("At least one output must be enabled: [mqtt], [influxdb], or [venus_dbus]")
    if mqtt.enabled and not mqtt.host:
        raise ValueError("[mqtt].host is required when MQTT is enabled")
    if influxdb.enabled:
        missing = [key for key in ("url", "token", "org", "bucket") if not getattr(influxdb, key)]
        if missing:
            raise ValueError(f"[influxdb] is missing required field(s): {', '.join(missing)}")

    if not devices:
        raise ValueError("Config must contain at least one [[devices]] entry")

    seen_ids: set[str] = set()
    seen_addresses: set[str] = set()
    for device in devices:
        if device.id in seen_ids:
            raise ValueError(f"Duplicate device id: {device.id}")
        if device.normalized_address in seen_addresses:
            raise ValueError(f"Duplicate device address: {device.address}")
        seen_ids.add(device.id)
        seen_addresses.add(device.normalized_address)

    return AppConfig(mqtt=mqtt, influxdb=influxdb, venus_dbus=venus_dbus, bridge=bridge, devices=devices)


def _parse_device(raw: dict[str, Any]) -> DeviceConfig:
    missing = [key for key in ("id", "name", "address", "advertisement_key") if not raw.get(key)]
    if missing:
        raise ValueError(f"Device entry is missing required field(s): {', '.join(missing)}")

    key = str(raw["advertisement_key"]).strip().lower()
    if len(key) != 32:
        raise ValueError(f"Advertisement key for {raw['id']} must be 32 hex characters")
    try:
        bytes.fromhex(key)
    except ValueError as exc:
        raise ValueError(f"Advertisement key for {raw['id']} is not valid hex") from exc

    return DeviceConfig(
        id=str(raw["id"]).strip(),
        name=str(raw["name"]).strip(),
        address=str(raw["address"]).strip(),
        advertisement_key=key,
        device_type=str(raw.get("device_type", "battery")).strip().lower(),
    )


def _parse_simple_toml(text: str) -> dict[str, Any]:
    """Parse the small TOML subset used by this project.

    This keeps Venus OS installs dependency-free when tomllib/tomli are absent.
    Supported: [section], [[devices]], strings, booleans, and integers.
    """
    root: dict[str, Any] = {}
    current: dict[str, Any] | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if line.startswith("[[") and line.endswith("]]" ) :
            section = line[2:-2].strip()
            item: dict[str, Any] = {}
            root.setdefault(section, []).append(item)
            current = item
            continue

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = root.setdefault(section, {})
            continue

        if current is None or "=" not in line:
            continue

        key, value = line.split("=", 1)
        current[key.strip()] = _parse_simple_toml_value(value.strip())

    return root


def _parse_simple_toml_value(value: str) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value, 0)
    except ValueError:
        return value

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
from pathlib import Path

from .config import load_config
from .bridge import MultiBridge


def main() -> None:
    parser = argparse.ArgumentParser(description="Victron BLE Instant Readout to MQTT gateway")
    parser.add_argument("-c", "--config", required=True, help="Path to config TOML")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run(Path(args.config)))


async def run(config_path: Path) -> None:
    config = load_config(config_path)
    bridge = MultiBridge(config)
    if config.venus_dbus.enabled:
        from .bluez_scanner import BluezVictronScanner

        scanner = BluezVictronScanner(config.devices, bridge)
    else:
        from bleak.exc import BleakBluetoothNotAvailableError
        from .scanner import VictronMqttScanner

        try:
            scanner = VictronMqttScanner(config.devices, bridge)
        except BleakBluetoothNotAvailableError as exc:
            logging.error(
                "No powered Bluetooth adapter found. On Raspberry Pi, check: "
                "sudo systemctl enable --now bluetooth; rfkill list bluetooth; "
                "sudo rfkill unblock bluetooth; bluetoothctl show."
            )
            raise SystemExit(2) from exc
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    bridge.connect()
    await scanner.start()
    try:
        await stop_event.wait()
    finally:
        await scanner.stop()
        bridge.close()


if __name__ == "__main__":
    main()

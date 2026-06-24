from __future__ import annotations

import logging
from typing import Any, Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from .config import AppConfig, DeviceConfig
from .topics import clean_topic_part, flatten_payload

logger = logging.getLogger(__name__)


class InfluxBridge:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.devices_by_address = {device.normalized_address: device for device in config.devices}
        self.client = InfluxDBClient(
            url=config.influxdb.url,
            token=config.influxdb.token,
            org=config.influxdb.org,
            timeout=config.influxdb.timeout_ms,
        )
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

    def connect(self) -> None:
        logger.info(
            "Connecting to InfluxDB %s bucket=%s org=%s",
            self.config.influxdb.url,
            self.config.influxdb.bucket,
            self.config.influxdb.org,
        )

    def close(self) -> None:
        self.client.close()

    def publish_reading(self, address: str, name: Optional[str], rssi: Optional[int], payload: dict[str, Any]) -> None:
        device = self.devices_by_address[address.lower()]
        point = Point(self.config.influxdb.measurement)
        point.tag("device_id", clean_topic_part(device.id))
        point.tag("device_name", name or device.name)
        point.tag("address", device.address)

        wrote_field = False
        for key, value in flatten_payload(payload).items():
            if isinstance(value, bool):
                point.field(key, value)
                wrote_field = True
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                point.field(key, float(value))
                wrote_field = True
            elif isinstance(value, str) and value:
                point.field(key, value)
                wrote_field = True

        if rssi is not None:
            point.field("rssi", int(rssi))
            wrote_field = True

        if not wrote_field:
            logger.debug("Skipping InfluxDB write for %s: no scalar fields", device.id)
            return

        self.write_api.write(
            bucket=self.config.influxdb.bucket,
            org=self.config.influxdb.org,
            record=point,
            write_precision=WritePrecision.S,
        )

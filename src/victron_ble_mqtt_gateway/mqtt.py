from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import paho.mqtt.client as mqtt

from .config import AppConfig, DeviceConfig
from .topics import clean_topic_part, flatten_payload

logger = logging.getLogger(__name__)


class MqttBridge:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.base_topic = config.mqtt.base_topic.strip().strip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=config.mqtt.client_id)
        self.devices_by_address = {device.normalized_address: device for device in config.devices}

        availability_topic = f"{self.base_topic}/gateway/status"
        self.client.will_set(availability_topic, "offline", qos=config.mqtt.qos, retain=True)

        if config.mqtt.username:
            self.client.username_pw_set(config.mqtt.username, config.mqtt.password or None)
        if config.mqtt.tls:
            self.client.tls_set()

    def connect(self) -> None:
        logger.info("Connecting to MQTT broker %s:%s", self.config.mqtt.host, self.config.mqtt.port)
        self.client.connect(self.config.mqtt.host, self.config.mqtt.port, keepalive=60)
        self.client.loop_start()
        self.publish_gateway_status("online")

    def close(self) -> None:
        self.publish_gateway_status("offline")
        self.client.loop_stop()
        self.client.disconnect()

    def publish_gateway_status(self, status: str) -> None:
        self._publish(f"{self.base_topic}/gateway/status", status, retain=True)

    def publish_reading(self, address: str, name: Optional[str], rssi: Optional[int], payload: dict[str, Any]) -> None:
        device = self.devices_by_address[address.lower()]
        now = int(time.time())
        topic_root = f"{self.base_topic}/{clean_topic_part(device.id)}"
        state = {
            "id": device.id,
            "name": name or device.name,
            "address": device.address,
            "rssi": rssi,
            "updated_at": now,
            "payload": payload,
        }

        if self.config.bridge.publish_json_state:
            self._publish_json(f"{topic_root}/state", state)

        if self.config.bridge.publish_metric_topics:
            for key, value in flatten_payload(payload).items():
                self._publish_json(f"{topic_root}/{key}", value)
            if rssi is not None:
                self._publish_json(f"{topic_root}/rssi", rssi)
            self._publish_json(f"{topic_root}/updated_at", now)

        self._publish(f"{topic_root}/status", "online", retain=True)

        if self.config.bridge.publish_home_assistant_discovery:
            self.publish_home_assistant_discovery(device, payload, topic_root)

    def publish_home_assistant_discovery(
        self,
        device: DeviceConfig,
        payload: dict[str, Any],
        topic_root: str,
    ) -> None:
        ha_prefix = self.config.bridge.home_assistant_prefix.strip().strip("/")
        device_info = {
            "identifiers": [f"victron_ble_{device.id}"],
            "name": device.name,
            "manufacturer": "Victron Energy",
        }

        for metric in flatten_payload(payload):
            unique_id = f"victron_ble_{device.id}_{metric}"
            discovery_topic = f"{ha_prefix}/sensor/victron_ble_{device.id}/{metric}/config"
            config = {
                "name": f"{device.name} {metric.replace('_', ' ')}",
                "unique_id": unique_id,
                "state_topic": f"{topic_root}/{metric}",
                "availability_topic": f"{topic_root}/status",
                "device": device_info,
            }
            self._publish_json(discovery_topic, config, retain=True)

    def _publish_json(self, topic: str, value: Any, retain: Optional[bool] = None) -> None:
        self._publish(topic, json.dumps(value, separators=(",", ":")), retain=retain)

    def _publish(self, topic: str, payload: str, retain: Optional[bool] = None) -> None:
        effective_retain = self.config.mqtt.retain if retain is None else retain
        result = self.client.publish(topic, payload, qos=self.config.mqtt.qos, retain=effective_retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.warning("MQTT publish failed for %s with rc=%s", topic, result.rc)

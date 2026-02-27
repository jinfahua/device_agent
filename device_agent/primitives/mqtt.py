"""
MQTT Client primitive.

Wraps paho-mqtt for asynchronous operation.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional, Set
from dataclasses import dataclass

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from ..types import MQTTConfig, MQTTMessageEvent

logger = logging.getLogger(__name__)


@dataclass
class Subscription:
    """MQTT subscription."""
    topic: str
    qos: int
    handler: Callable[[str, Any], None]


class MQTTClient:
    """Asynchronous MQTT client."""

    def __init__(self, config: MQTTConfig):
        if mqtt is None:
            raise ImportError("paho-mqtt is required. Install with: pip install paho-mqtt")

        self.config = config
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._subscriptions: Dict[str, Subscription] = {}
        self._message_handlers: Set[Callable[[MQTTMessageEvent], None]] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connect_event = asyncio.Event()

    @property
    def connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    @property
    def client_id(self) -> str:
        """Get client ID."""
        return self.config.client_id or f"device_agent_{uuid.uuid4().hex[:8]}"

    def _on_connect(self, client, userdata, flags, rc):
        """Connection callback."""
        if rc == 0:
            self._connected = True
            logger.info(f"Connected to MQTT broker: {self.config.broker}:{self.config.port}")
            # Resubscribe to all topics
            for sub in self._subscriptions.values():
                client.subscribe(sub.topic, sub.qos)
                logger.debug(f"Resubscribed to: {sub.topic}")
            self._connect_event.set()
        else:
            logger.error(f"Connection failed with code: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Disconnection callback."""
        self._connected = False
        self._connect_event.clear()
        if rc != 0:
            logger.warning(f"Unexpected disconnection (rc={rc}), will auto-reconnect")
        else:
            logger.info("Disconnected from MQTT broker")

    def _on_message(self, client, userdata, msg):
        """Message received callback."""
        try:
            payload = msg.payload.decode("utf-8")
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = payload

            logger.debug(f"Received message on {msg.topic}: {data}")

            # Create event
            event = MQTTMessageEvent(topic=msg.topic, payload=data)

            # Notify global handlers
            for handler in self._message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(event))
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")

            # Notify topic-specific handlers
            for sub in self._subscriptions.values():
                if mqtt.topic_matches_sub(sub.topic, msg.topic):
                    try:
                        if asyncio.iscoroutinefunction(sub.handler):
                            asyncio.create_task(sub.handler(msg.topic, data))
                        else:
                            sub.handler(msg.topic, data)
                    except Exception as e:
                        logger.error(f"Error in subscription handler: {e}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def connect(self) -> bool:
        """Connect to MQTT broker."""
        if self._connected:
            return True

        self._loop = asyncio.get_event_loop()
        self._connect_event.clear()

        self._client = mqtt.Client(client_id=self.client_id)

        if self.config.username and self.config.password:
            self._client.username_pw_set(self.config.username, self.config.password)

        if self.config.use_ssl:
            self._client.tls_set()

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        try:
            self._client.connect(self.config.broker, self.config.port)
            self._client.loop_start()

            # Wait for connection with timeout
            await asyncio.wait_for(self._connect_event.wait(), timeout=10.0)
            return self._connected
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    async def disconnect(self):
        """Disconnect from MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info("Disconnected from MQTT broker")

    async def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> bool:
        """Publish a message."""
        if not self._connected or not self._client:
            logger.error("Cannot publish: not connected")
            return False

        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            elif not isinstance(payload, str):
                payload = str(payload)

            result = self._client.publish(topic, payload, qos, retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Publish failed with code: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing: {e}")
            return False

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[str, Any], None],
        qos: int = 0
    ) -> bool:
        """Subscribe to a topic."""
        if not self._connected or not self._client:
            logger.error("Cannot subscribe: not connected")
            return False

        try:
            result, mid = self._client.subscribe(topic, qos)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self._subscriptions[topic] = Subscription(topic, qos, handler)
                logger.info(f"Subscribed to: {topic}")
                return True
            else:
                logger.error(f"Subscribe failed with code: {result}")
                return False
        except Exception as e:
            logger.error(f"Error subscribing: {e}")
            return False

    async def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from a topic."""
        if not self._connected or not self._client:
            return False

        try:
            result, mid = self._client.unsubscribe(topic)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self._subscriptions.pop(topic, None)
                logger.info(f"Unsubscribed from: {topic}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error unsubscribing: {e}")
            return False

    def add_message_handler(self, handler: Callable[[MQTTMessageEvent], None]):
        """Add a global message handler."""
        self._message_handlers.add(handler)

    def remove_message_handler(self, handler: Callable[[MQTTMessageEvent], None]):
        """Remove a global message handler."""
        self._message_handlers.discard(handler)

    def get_status_topic(self, device_id: str) -> str:
        """Get device status topic."""
        return f"{self.config.topic_prefix}/{device_id}/status"

    def get_command_topic(self, device_id: str) -> str:
        """Get device command topic."""
        return f"{self.config.topic_prefix}/{device_id}/command"

"""
Event stream for asynchronous communication.

Inspired by pi-agent-core's event system.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from collections import deque

from ..types import Event, EventHandler

logger = logging.getLogger(__name__)


class EventStream:
    """
    Asynchronous event stream.

    Allows components to emit and subscribe to events.
    """

    def __init__(self, max_history: int = 100):
        self._handlers: Dict[str, Set[EventHandler]] = {}
        self._global_handlers: Set[EventHandler] = set()
        self._history: deque = deque(maxlen=max_history)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def on(self, event_type: str, handler: EventHandler):
        """Subscribe to a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
        self._handlers[event_type].add(handler)
        logger.debug(f"Handler registered for event: {event_type}")

    def off(self, event_type: str, handler: EventHandler):
        """Unsubscribe from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].discard(handler)

    def on_any(self, handler: EventHandler):
        """Subscribe to all events."""
        self._global_handlers.add(handler)

    def off_any(self, handler: EventHandler):
        """Unsubscribe from all events."""
        self._global_handlers.discard(handler)

    async def emit(self, event: Event):
        """Emit an event."""
        self._history.append(event)
        await self._queue.put(event)

    async def emit_typed(self, event_type: str, data: Dict[str, Any]):
        """Emit a typed event."""
        event = Event(type=event_type, data=data)
        await self.emit(event)

    async def start(self):
        """Start processing events."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("Event stream started")

    async def stop(self):
        """Stop processing events."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Event stream stopped")

    async def _process_loop(self):
        """Main event processing loop."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.1)
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    async def _dispatch(self, event: Event):
        """Dispatch event to handlers."""
        # Global handlers
        for handler in self._global_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")

        # Type-specific handlers
        handlers = self._handlers.get(event.type, set())
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    def get_history(self, event_type: Optional[str] = None) -> List[Event]:
        """Get event history, optionally filtered by type."""
        events = list(self._history)
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events

    def clear_history(self):
        """Clear event history."""
        self._history.clear()


class EventBus:
    """
    Simple event bus for request-response patterns.
    """

    def __init__(self):
        self._responders: Dict[str, Callable] = {}

    def register(self, action: str, handler: Callable):
        """Register a handler for an action."""
        self._responders[action] = handler

    async def request(self, action: str, data: Dict[str, Any]) -> Any:
        """Send a request and wait for response."""
        handler = self._responders.get(action)
        if not handler:
            raise ValueError(f"No handler registered for action: {action}")

        if asyncio.iscoroutinefunction(handler):
            return await handler(data)
        else:
            return handler(data)

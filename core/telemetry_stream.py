"""
telemetry_stream.py - Real-Time Telemetry Ring Buffer & SSE Event Stream for AutoDev (v2.2)

Provides thread-safe bounded ring buffering of execution events, Server-Sent Events (SSE)
formatting, client subscriber queues, event catchup by Last-Event-ID, and secret redaction.
"""

from __future__ import annotations

import collections
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Set

from core.telemetry_models import (
    TelemetryEvent,
    TelemetrySeverity,
    TelemetrySnapshot,
    redact_telemetry_payload,
)

logger = logging.getLogger("AutoDev.TelemetryStream")


class TelemetryStream:
    """
    Thread-safe publisher and ring-buffer for live execution telemetry.
    Supports SSE streaming, subscriber fan-out, and event replay via Last-Event-ID.
    """

    def __init__(self, max_buffer_size: int = 1000, max_events: Optional[int] = None) -> None:
        self.max_buffer_size = max_events if max_events is not None else max_buffer_size
        self._buffer: Deque[TelemetryEvent] = collections.deque(maxlen=self.max_buffer_size)
        self._subscribers: Set[queue.Queue[Optional[TelemetryEvent]]] = set()
        self._lock = threading.RLock()
        self._event_counter = 0

    @property
    def event_count(self) -> int:
        """Returns total number of events currently retained in the ring buffer."""
        with self._lock:
            return len(self._buffer)

    def publish_event(
        self,
        event_type: str,
        message: str = "",
        severity: TelemetrySeverity = TelemetrySeverity.INFO,
        transaction_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        stage_id: Optional[int] = None,
        operation_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        container_id: Optional[str] = None,
        status: Optional[str] = None,
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TelemetryEvent:
        """
        Creates, redacts, buffers, and broadcasts a telemetry event to all active subscribers.
        """
        with self._lock:
            self._event_counter += 1
            event_id = f"evt-{self._event_counter:06d}"

            clean_meta = redact_telemetry_payload(metadata or {})
            clean_msg = redact_telemetry_payload(message)

            event = TelemetryEvent(
                event_id=event_id,
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).isoformat(),
                transaction_id=transaction_id,
                plan_id=plan_id,
                stage_id=stage_id,
                operation_id=operation_id,
                worker_id=worker_id,
                container_id=container_id,
                severity=severity,
                status=status,
                duration_ms=duration_ms,
                message=clean_msg,
                metadata=clean_meta,
            )

            self._buffer.append(event)

            # Fan-out to subscribers (drop or non-blocking put to avoid stalling execution)
            dead_subscribers = []
            for sub_q in self._subscribers:
                try:
                    sub_q.put_nowait(event)
                except queue.Full:
                    # Slow client buffer full: remove oldest to prevent backpressure blocking
                    try:
                        sub_q.get_nowait()
                        sub_q.put_nowait(event)
                    except Exception:
                        dead_subscribers.append(sub_q)
                except Exception:
                    dead_subscribers.append(sub_q)

            for dead in dead_subscribers:
                self._subscribers.discard(dead)

            return event

    def publish(self, event: TelemetryEvent) -> TelemetryEvent:
        """Publishes an already constructed TelemetryEvent instance."""
        with self._lock:
            self._event_counter += 1
            if not event.event_id:
                event.event_id = f"evt-{self._event_counter:06d}"
            self._buffer.append(event)
            dead_subscribers = []
            for sub_q in self._subscribers:
                try:
                    sub_q.put_nowait(event)
                except queue.Full:
                    try:
                        sub_q.get_nowait()
                        sub_q.put_nowait(event)
                    except Exception:
                        dead_subscribers.append(sub_q)
                except Exception:
                    dead_subscribers.append(sub_q)
            for dead in dead_subscribers:
                self._subscribers.discard(dead)
            return event

    def emit(self, event: TelemetryEvent) -> TelemetryEvent:
        return self.publish(event)

    def subscribe(
        self,
        last_event_id: Optional[str] = None,
        queue_maxsize: int = 200,
    ) -> Tuple[queue.Queue[Optional[TelemetryEvent]], List[TelemetryEvent]]:
        """
        Registers a new subscriber queue and returns missed catch-up events if last_event_id is provided.
        """
        with self._lock:
            client_queue: queue.Queue[Optional[TelemetryEvent]] = queue.Queue(maxsize=queue_maxsize)
            catchup_events: List[TelemetryEvent] = []

            if last_event_id:
                found = False
                for evt in self._buffer:
                    if found:
                        catchup_events.append(evt)
                    elif evt.event_id == last_event_id:
                        found = True
                if not found:
                    # If last_event_id was purged or unknown, replay recent events up to maxsize
                    catchup_events = list(self._buffer)

            self._subscribers.add(client_queue)
            logger.info("New telemetry subscriber attached (total subscribers: %d)", len(self._subscribers))
            return client_queue, catchup_events

    def unsubscribe(self, client_queue: queue.Queue[Optional[TelemetryEvent]]) -> None:
        """
        Unregisters a subscriber queue and signals termination.
        """
        with self._lock:
            self._subscribers.discard(client_queue)
            try:
                client_queue.put_nowait(None)
            except Exception:
                pass
            logger.info("Telemetry subscriber detached (remaining: %d)", len(self._subscribers))

    def get_recent_events(self, limit: int = 50, transaction_id: Optional[str] = None) -> List[TelemetryEvent]:
        """
        Returns recent buffered telemetry events up to limit, optionally filtered by transaction_id.
        """
        with self._lock:
            events_list = list(self._buffer)
            if transaction_id:
                events_list = [e for e in events_list if e.transaction_id == transaction_id]
            return events_list[-limit:] if len(events_list) > limit else events_list

    @staticmethod
    def format_sse(event: TelemetryEvent) -> str:
        """
        Formats a TelemetryEvent into standard Server-Sent Events (SSE) wire protocol string.
        """
        data_json = json.dumps(event.to_dict())
        return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data_json}\n\n"

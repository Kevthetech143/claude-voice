"""
Event system for observable pipeline
Enables AI testing by providing full visibility into system behavior
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from enum import Enum


class EventType(str, Enum):
    """Standard pipeline event types"""

    # Audio input events
    AUDIO_CAPTURE_START = "audio_capture_start"
    AUDIO_CAPTURE_COMPLETE = "audio_capture_complete"

    # STT events
    STT_START = "stt_start"
    STT_COMPLETE = "stt_complete"
    STT_ERROR = "stt_error"

    # LLM events
    LLM_QUERY_START = "llm_query_start"
    LLM_TOKEN_RECEIVED = "llm_token_received"
    LLM_COMPLETE = "llm_complete"
    LLM_ERROR = "llm_error"

    # Sentence chunker events
    SENTENCE_READY = "sentence_ready"

    # TTS events
    TTS_START = "tts_start"
    TTS_COMPLETE = "tts_complete"
    TTS_ERROR = "tts_error"

    # Pipeline events
    PIPELINE_START = "pipeline_start"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"


@dataclass
class PipelineEvent:
    """
    Immutable event record for pipeline observability

    All timestamps are Unix epoch (seconds since 1970)
    """
    timestamp: float
    event_type: EventType
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure event_type is EventType enum"""
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)

    @property
    def latency_ms(self) -> float | None:
        """Extract latency if present in data"""
        return self.data.get("latency_ms")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "data": self.data
        }


class EventObserver(Protocol):
    """Protocol for objects that observe pipeline events"""

    def emit(self, event_type: EventType | str, data: dict[str, Any] | None = None) -> None:
        """Emit an event"""
        ...

    def get_events(self) -> list[PipelineEvent]:
        """Retrieve all recorded events"""
        ...

    def clear(self) -> None:
        """Clear event history"""
        ...


class InMemoryEventObserver:
    """
    In-memory event observer for testing and development
    Thread-safe for async usage
    """

    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []
        self._callbacks: list[Callable[[PipelineEvent], None]] = []

    def emit(self, event_type: EventType | str, data: dict[str, Any] | None = None) -> None:
        """Record an event with current timestamp"""
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        event = PipelineEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data or {}
        )

        self.events.append(event)

        # Notify callbacks
        for callback in self._callbacks:
            callback(event)

    def get_events(self) -> list[PipelineEvent]:
        """Return copy of all events"""
        return self.events.copy()

    def clear(self) -> None:
        """Clear event history"""
        self.events.clear()

    def on_event(self, callback: Callable[[PipelineEvent], None]) -> None:
        """Register callback to be called on each event"""
        self._callbacks.append(callback)

    def get_events_by_type(self, event_type: EventType) -> list[PipelineEvent]:
        """Filter events by type"""
        return [e for e in self.events if e.event_type == event_type]

    def get_latency_breakdown(self) -> dict[str, float]:
        """
        Calculate latency for each stage
        Returns dict of stage_name -> latency_ms
        """
        breakdown: dict[str, float] = {}

        # Find paired start/complete events
        pairs = [
            ("stt", EventType.STT_START, EventType.STT_COMPLETE),
            ("llm_first_token", EventType.LLM_QUERY_START, EventType.LLM_TOKEN_RECEIVED),
            ("llm_total", EventType.LLM_QUERY_START, EventType.LLM_COMPLETE),
            ("tts", EventType.TTS_START, EventType.TTS_COMPLETE),
            ("pipeline_total", EventType.PIPELINE_START, EventType.PIPELINE_COMPLETE),
        ]

        for name, start_type, end_type in pairs:
            start_events = self.get_events_by_type(start_type)
            end_events = self.get_events_by_type(end_type)

            if start_events and end_events:
                # Use most recent pair
                latency_ms = (end_events[-1].timestamp - start_events[-1].timestamp) * 1000
                breakdown[name] = latency_ms

        return breakdown

    def print_summary(self) -> None:
        """Print human-readable event summary"""
        print("\n=== Pipeline Event Summary ===")
        print(f"Total events: {len(self.events)}\n")

        # Group by type
        by_type: dict[EventType, int] = {}
        for event in self.events:
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1

        print("Events by type:")
        for event_type, count in sorted(by_type.items(), key=lambda x: x[0].value):
            print(f"  {event_type.value}: {count}")

        # Latency breakdown
        latencies = self.get_latency_breakdown()
        if latencies:
            print("\nLatency breakdown (ms):")
            for stage, latency in latencies.items():
                print(f"  {stage}: {latency:.1f}ms")

        print()


class NullObserver:
    """No-op observer for production when you don't need event tracking"""

    def emit(self, event_type: EventType | str, data: dict[str, Any] | None = None) -> None:
        pass

    def get_events(self) -> list[PipelineEvent]:
        return []

    def clear(self) -> None:
        pass

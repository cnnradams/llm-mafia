"""Event log system for tracking game events."""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class EventType(Enum):
    """Types of game events."""
    KILL = "KILL"
    VOTE = "VOTE"
    NOMINATE = "NOMINATE"
    ELIMINATE = "ELIMINATE"
    SPEAK = "SPEAK"
    NIGHT_ACTION = "NIGHT_ACTION"
    PHASE_CHANGE = "PHASE_CHANGE"


@dataclass
class GameEvent:
    """Represents a single game event."""
    type: EventType
    phase: str
    day: int
    player_id: Optional[str] = None
    target_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        result = asdict(self)
        result['type'] = self.type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result


class EventLog:
    """Manages the game event log."""
    
    def __init__(self):
        self.events: list[GameEvent] = []
    
    def add_event(
        self,
        event_type: EventType,
        phase: str,
        day: int,
        player_id: Optional[str] = None,
        target_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> GameEvent:
        """Add an event to the log."""
        event = GameEvent(
            type=event_type,
            phase=phase,
            day=day,
            player_id=player_id,
            target_id=target_id,
            data=data or {},
        )
        self.events.append(event)
        return event
    
    def get_events_by_type(self, event_type: EventType) -> list[GameEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.type == event_type]
    
    def get_events_by_day(self, day: int) -> list[GameEvent]:
        """Get all events from a specific day."""
        return [e for e in self.events if e.day == day]
    
    def get_speeches(self) -> list[GameEvent]:
        """Get all speech events."""
        return self.get_events_by_type(EventType.SPEAK)
    
    def to_list(self) -> list[Dict[str, Any]]:
        """Convert event log to list of dictionaries."""
        return [e.to_dict() for e in self.events]


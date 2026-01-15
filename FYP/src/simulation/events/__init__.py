"""Event system for discrete occurrences in the simulation."""

from .event_queue import EventQueue
from .event_types import (
    Event,
    TruckDepartureEvent,
    TruckArrivalEvent,
    OrderPlacedEvent,
    AccidentStartEvent,
    AccidentEndEvent,
    WarehouseRestockEvent,
    CustomerArrivalEvent,
    RouteChangedEvent,
    LowFuelWarningEvent,
    CargoSpoiledEvent
)

__all__ = [
    'EventQueue',
    'Event',
    'TruckDepartureEvent',
    'TruckArrivalEvent',
    'OrderPlacedEvent',
    'AccidentStartEvent',
    'AccidentEndEvent',
    'WarehouseRestockEvent',
    'CustomerArrivalEvent',
    'RouteChangedEvent',
    'LowFuelWarningEvent',
    'CargoSpoiledEvent'
]

#!/usr/bin/env python3
"""base_adapter.py - Defines the abstract interface for all network adapters."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Callable

class NetBaseAdapter(ABC):
    """
    Abstract Base Class for network adapters.

    This class defines a universal, implementation-agnostic interface for network
    communication, allowing consuming scripts (like NetNode) to remain unaware
    of the underlying transport mechanism (e.g., P2P, loopback).
    """

    @abstractmethod
    async def start(self):
        """Starts the network adapter and any underlying services."""
        pass

    @abstractmethod
    async def stop(self):
        """Stops the network adapter and cleans up resources."""
        pass

    @abstractmethod
    async def broadcast(self, sender_id: str, message: Dict[str, Any]):
        """Broadcasts a message to all other peers in the network."""
        pass

    @abstractmethod
    async def send(self, sender_id: str, receiver_id: str, message: Dict[str, Any]):
        """Sends a direct message to a specific peer."""
        pass

    @abstractmethod
    def register_message_handler(self, handler_func: Callable[[str, Dict[str, Any]], None]):
        """
        Registers a callback function to handle incoming messages.
        The handler should expect two arguments: sender_id (str) and message (dict).
        """
        pass

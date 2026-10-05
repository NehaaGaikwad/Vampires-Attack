"""
core/packet.py
==============
Represents a packet travelling through the Wireless Sensor Network (WSN).

Responsibilities
----------------
- Storing source and destination node IDs.
- Tracking the ordered route taken by the packet (list of node IDs).
- Maintaining hop count.
- Maintaining Time-To-Live (TTL) — the maximum number of hops allowed.
- Maintaining a visited-node set to support loop detection.
- Providing clear delivered / expired / dropped state.
- Advancing packet state as the packet moves hop-by-hop.

TTL Semantics
-------------
TTL represents the **maximum number of remaining hops** that the packet
may travel.  Every time the packet moves from one node to the next the TTL
is decremented by 1 *before* being accepted at the new node.

- A TTL of 0 means the packet cannot move at all.
- A TTL of 1 means the packet may take exactly one more hop.
- When TTL reaches 0 during forwarding the packet is marked as expired
  and forwarding stops.

TTL never becomes negative.

Loop Prevention
---------------
The ``visited`` set records every node the packet has *arrived at*.  The
source node is added on creation.  Before a packet is advanced to the
next hop the Router checks whether the target node is already in
``visited``; if it is, the packet is marked as dropped (loop detected)
and forwarding stops.

Responsibility Boundaries
--------------------------
This module does NOT perform routing, energy calculations, Dijkstra, or
network topology operations.  It only represents the state of a single
in-flight packet.
"""

from __future__ import annotations

from enum import Enum, auto


# ---------------------------------------------------------------------------
# Packet status enumeration
# ---------------------------------------------------------------------------


class PacketStatus(Enum):
    """Lifecycle state of a :class:`Packet`."""

    IN_TRANSIT = auto()   #: Packet is still travelling.
    DELIVERED = auto()    #: Packet has reached its destination.
    EXPIRED = auto()      #: TTL was exhausted before delivery.
    DROPPED = auto()      #: Dropped due to loop detection or unreachable destination.


# ---------------------------------------------------------------------------
# Packet
# ---------------------------------------------------------------------------


class Packet:
    """A packet travelling through the WSN.

    Parameters
    ----------
    source : str
        Node ID of the originating node.
    destination : str
        Node ID of the target node.
    ttl : int
        Maximum number of hops the packet may travel.  Must be >= 1.
        Defaults to 50, which is ample for typical WSN topologies.
    packet_size : int
        Payload size in bits.  Used by the routing layer when calling
        ``EnergyModel.transmit()``.  Defaults to 4000 bits.

    Raises
    ------
    ValueError
        If *source* or *destination* is empty, or if *ttl* < 1, or if
        *packet_size* < 0.
    """

    DEFAULT_TTL: int = 50
    DEFAULT_PACKET_SIZE: int = 4000  # bits

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        source: str,
        destination: str,
        ttl: int = DEFAULT_TTL,
        packet_size: int = DEFAULT_PACKET_SIZE,
    ) -> None:
        if not source:
            raise ValueError("source must be a non-empty node ID string.")
        if not destination:
            raise ValueError("destination must be a non-empty node ID string.")
        if ttl < 1:
            raise ValueError(f"ttl must be >= 1, got {ttl!r}.")
        if packet_size < 0:
            raise ValueError(f"packet_size must be >= 0, got {packet_size!r}.")

        self._source: str = source
        self._destination: str = destination
        self._ttl: int = ttl
        self._packet_size: int = packet_size

        # Route: ordered list of node IDs the packet has visited.
        # Initialised with the source node.
        self._route: list[str] = [source]

        # Hop count: number of hops taken so far.
        self._hops: int = 0

        # Visited set for O(1) loop detection.
        self._visited: set[str] = {source}

        # Lifecycle state
        self._status: PacketStatus = PacketStatus.IN_TRANSIT

    # ------------------------------------------------------------------
    # Core identity
    # ------------------------------------------------------------------

    @property
    def source(self) -> str:
        """Node ID of the originating node."""
        return self._source

    @property
    def destination(self) -> str:
        """Node ID of the target / destination node."""
        return self._destination

    @property
    def packet_size(self) -> int:
        """Packet payload size in bits."""
        return self._packet_size

    # ------------------------------------------------------------------
    # Route / position
    # ------------------------------------------------------------------

    @property
    def route(self) -> list[str]:
        """Ordered list of node IDs the packet has visited.

        The first element is always the source.  The last element is the
        node where the packet currently resides.  Returns a copy to
        prevent external mutation.
        """
        return list(self._route)

    @property
    def current_node(self) -> str:
        """The node ID where the packet currently resides."""
        return self._route[-1]

    @property
    def hops(self) -> int:
        """Number of hops the packet has taken so far."""
        return self._hops

    # ------------------------------------------------------------------
    # TTL
    # ------------------------------------------------------------------

    @property
    def ttl(self) -> int:
        """Remaining Time-To-Live (number of additional hops allowed).

        TTL is decremented each time the packet advances one hop.  When
        it reaches 0 the packet can no longer be forwarded.  TTL never
        becomes negative.
        """
        return self._ttl

    # ------------------------------------------------------------------
    # Visited nodes
    # ------------------------------------------------------------------

    @property
    def visited(self) -> set[str]:
        """Set of all node IDs the packet has visited (including source).

        Returns a copy to prevent external mutation.
        """
        return set(self._visited)

    # ------------------------------------------------------------------
    # Status / lifecycle flags
    # ------------------------------------------------------------------

    @property
    def status(self) -> PacketStatus:
        """Current lifecycle status of the packet."""
        return self._status

    @property
    def delivered(self) -> bool:
        """``True`` if the packet has been successfully delivered."""
        return self._status == PacketStatus.DELIVERED

    @property
    def expired(self) -> bool:
        """``True`` if the packet was dropped because TTL was exhausted."""
        return self._status == PacketStatus.EXPIRED

    @property
    def dropped(self) -> bool:
        """``True`` if the packet was dropped for any non-delivery reason
        (e.g. loop detected, unreachable destination)."""
        return self._status == PacketStatus.DROPPED

    @property
    def in_transit(self) -> bool:
        """``True`` if the packet is still travelling (not yet delivered
        or dropped)."""
        return self._status == PacketStatus.IN_TRANSIT

    # ------------------------------------------------------------------
    # State advancement — called by the Router
    # ------------------------------------------------------------------

    def advance(self, next_node_id: str) -> None:
        """Advance the packet one hop to *next_node_id*.

        This method is intended to be called by the routing layer *after*
        the physical transmission has been performed via
        ``EnergyModel.transmit()``.

        Rules (applied in this order)
        ------------------------------
        1. The packet must be ``IN_TRANSIT``; otherwise ``RuntimeError``
           is raised.
        2. *next_node_id* must be non-empty; otherwise ``ValueError`` is
           raised.
        3. If *next_node_id* is already in ``visited``, the packet is
           marked as ``DROPPED`` (loop detected) — no further state
           change occurs.
        4. If the remaining TTL is 0, the packet is marked as
           ``EXPIRED`` — no hop is taken.
        5. TTL is decremented by 1.
        6. The hop count is incremented by 1.
        7. *next_node_id* is appended to ``route`` and added to
           ``visited``.
        8. If *next_node_id* == ``destination``, status becomes
           ``DELIVERED``.

        Parameters
        ----------
        next_node_id : str
            The node ID of the next hop.

        Raises
        ------
        RuntimeError
            If the packet is not ``IN_TRANSIT``.
        ValueError
            If *next_node_id* is empty.
        """
        if self._status != PacketStatus.IN_TRANSIT:
            raise RuntimeError(
                f"Cannot advance a packet that is not IN_TRANSIT "
                f"(current status: {self._status.name})."
            )
        if not next_node_id:
            raise ValueError("next_node_id must be a non-empty string.")

        # Rule 3: Loop detection — reject revisiting an already-visited node.
        if next_node_id in self._visited:
            self._status = PacketStatus.DROPPED
            return

        # Rule 4: TTL check — packet cannot move if TTL is exhausted.
        if self._ttl <= 0:
            self._status = PacketStatus.EXPIRED
            return

        # Rules 5-7: Update counters, route, visited.
        self._ttl -= 1
        self._hops += 1
        self._route.append(next_node_id)
        self._visited.add(next_node_id)

        # Rule 8: Check delivery.
        if next_node_id == self._destination:
            self._status = PacketStatus.DELIVERED

    def mark_dropped(self) -> None:
        """Explicitly mark the packet as dropped (e.g. unreachable destination).

        Has no effect if the packet is already in a terminal state.
        """
        if self._status == PacketStatus.IN_TRANSIT:
            self._status = PacketStatus.DROPPED

    def mark_expired(self) -> None:
        """Explicitly mark the packet as expired (TTL exhausted).

        Has no effect if the packet is already in a terminal state.
        """
        if self._status == PacketStatus.IN_TRANSIT:
            self._status = PacketStatus.EXPIRED

    def mark_delivered(self) -> None:
        """Explicitly mark the packet as delivered.

        Has no effect if the packet is already in a terminal state.
        This is used by the Router for the source == destination edge case
        where no physical hop takes place.
        """
        if self._status == PacketStatus.IN_TRANSIT:
            self._status = PacketStatus.DELIVERED


    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Packet(src={self._source!r}, dst={self._destination!r}, "
            f"hops={self._hops}, ttl={self._ttl}, "
            f"status={self._status.name}, "
            f"route={self._route!r})"
        )

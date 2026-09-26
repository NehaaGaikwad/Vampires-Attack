"""
core/node.py
============
Represents a single sensor node in the Wireless Sensor Network (WSN).

Responsibilities
----------------
- Identity   : unique node ID
- Position   : 2-D coordinates (x, y)
- Energy     : battery tracking with safe consumption
- Neighbors  : set of directly reachable node IDs (managed by Network)
- Counters   : packet-level counters for use by routing / metrics layers
- Liveness   : derived automatically from remaining energy

This module does NOT contain routing, attack, detection, or GUI logic.
"""

from __future__ import annotations


class Node:
    """A battery-powered sensor node in the WSN.

    Parameters
    ----------
    node_id : str
        Unique identifier for this node (e.g. ``"N1"``, ``"SINK"``).
    x : float
        X-coordinate of the node's position (metres or arbitrary units).
    y : float
        Y-coordinate of the node's position (metres or arbitrary units).
    initial_energy : float
        Starting battery energy in Joules (must be > 0).

    Raises
    ------
    ValueError
        If *initial_energy* is not positive.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        node_id: str,
        x: float,
        y: float,
        initial_energy: float,
    ) -> None:
        if initial_energy <= 0:
            raise ValueError(
                f"initial_energy must be positive, got {initial_energy!r}"
            )

        self._id: str = node_id
        self._x: float = float(x)
        self._y: float = float(y)
        self._initial_energy: float = float(initial_energy)
        self._energy: float = float(initial_energy)

        # Neighbor set — stores node IDs, managed externally by Network
        self._neighbors: set[str] = set()

        # Packet counters — incremented externally by EnergyModel / routing
        self._sent: int = 0
        self._received: int = 0
        self._forwarded: int = 0

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:  # noqa: A003
        """Unique node identifier."""
        return self._id

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    @property
    def x(self) -> float:
        """X-coordinate."""
        return self._x

    @property
    def y(self) -> float:
        """Y-coordinate."""
        return self._y

    @property
    def position(self) -> tuple[float, float]:
        """(x, y) tuple representing the 2-D position."""
        return (self._x, self._y)

    # ------------------------------------------------------------------
    # Energy
    # ------------------------------------------------------------------

    @property
    def initial_energy(self) -> float:
        """Battery energy at node creation — never changes."""
        return self._initial_energy

    @property
    def energy(self) -> float:
        """Currently remaining battery energy (Joules). Always >= 0."""
        return self._energy

    @property
    def alive(self) -> bool:
        """``True`` while the node has remaining energy; ``False`` when dead.

        This property is **derived** from :attr:`energy` — there is no
        separate flag that can drift out of sync.
        """
        return self._energy > 0.0

    def consume_energy(self, amount: float) -> None:
        """Deduct *amount* Joules from the node's battery.

        Rules
        -----
        1. Energy can never become negative; it clamps to 0.
        2. Consuming exactly the remaining energy leaves energy == 0.
        3. Consuming more than the remaining energy leaves energy == 0.
        4. Negative *amount* is silently ignored to prevent corruption.

        Parameters
        ----------
        amount : float
            Energy to deduct (Joules).  Values <= 0 are ignored.
        """
        if amount <= 0:
            return
        self._energy = max(0.0, self._energy - amount)

    # ------------------------------------------------------------------
    # Neighbors
    # ------------------------------------------------------------------

    @property
    def neighbors(self) -> set[str]:
        """Set of neighboring node IDs (managed by :class:`~core.network.Network`)."""
        return self._neighbors

    def add_neighbor(self, node_id: str) -> None:
        """Record *node_id* as a direct neighbor.

        Duplicate additions are silently ignored (set semantics).

        Parameters
        ----------
        node_id : str
            ID of the neighboring node.
        """
        self._neighbors.add(node_id)

    def remove_neighbor(self, node_id: str) -> None:
        """Remove *node_id* from the neighbor set.

        If *node_id* is not present, the call is silently ignored.

        Parameters
        ----------
        node_id : str
            ID of the node to remove.
        """
        self._neighbors.discard(node_id)

    # ------------------------------------------------------------------
    # Packet counters (read-only via properties; incremented by external layers)
    # ------------------------------------------------------------------

    @property
    def sent(self) -> int:
        """Total packets sent by this node."""
        return self._sent

    @sent.setter
    def sent(self, value: int) -> None:
        self._sent = value

    @property
    def received(self) -> int:
        """Total packets received by this node."""
        return self._received

    @received.setter
    def received(self, value: int) -> None:
        self._received = value

    @property
    def forwarded(self) -> int:
        """Total packets forwarded by this node (set by routing layer)."""
        return self._forwarded

    @forwarded.setter
    def forwarded(self, value: int) -> None:
        self._forwarded = value

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Restore node to its initial state.

        Restores
        --------
        - ``energy``    → ``initial_energy``
        - ``sent``      → 0
        - ``received``  → 0
        - ``forwarded`` → 0
        - ``neighbors`` → empty set (Network must re-run
          :meth:`~core.network.Network.update_neighbors` after reset)
        """
        self._energy = self._initial_energy
        self._sent = 0
        self._received = 0
        self._forwarded = 0
        self._neighbors = set()

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        status = "alive" if self.alive else "dead"
        return (
            f"Node(id={self._id!r}, pos=({self._x}, {self._y}), "
            f"energy={self._energy:.4f}/{self._initial_energy:.4f}, {status})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

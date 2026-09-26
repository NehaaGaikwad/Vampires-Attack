"""
core/network.py
===============
Manages the topology of the Wireless Sensor Network (WSN).

Responsibilities
----------------
- Storing and retrieving sensor nodes by ID
- Calculating Euclidean distances between nodes
- Discovering and maintaining bidirectional neighbor relationships
  based on a configurable communication range
- Tracking the Sink / Base Station node

This module does NOT contain routing, energy calculation, attack, or GUI logic.
"""

from __future__ import annotations

import math
from typing import Optional

from core.node import Node


class Network:
    """The Wireless Sensor Network topology manager.

    Parameters
    ----------
    communication_range : float
        Maximum transmission distance (same units as node coordinates).
        Two nodes are direct neighbors when their Euclidean distance is
        **<= communication_range**.

    Raises
    ------
    ValueError
        If *communication_range* is not positive.

    Notes
    -----
    Dead nodes (``node.alive == False``) are **retained** in
    :attr:`nodes` for statistics and visualisation purposes but are
    **excluded** from the list returned by :meth:`get_neighbors`.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, communication_range: float) -> None:
        if communication_range <= 0:
            raise ValueError(
                f"communication_range must be positive, got {communication_range!r}"
            )
        self._communication_range: float = float(communication_range)
        self._nodes: dict[str, Node] = {}
        self._sink: Optional[Node] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def communication_range(self) -> float:
        """Maximum direct-communication distance between two nodes."""
        return self._communication_range

    @property
    def nodes(self) -> dict[str, Node]:
        """Mapping of node ID → :class:`~core.node.Node` for **all** nodes
        (alive and dead).  Do not mutate this dict directly; use
        :meth:`add_node` instead."""
        return self._nodes

    @property
    def sink(self) -> Optional[Node]:
        """The Sink / Base Station node, or ``None`` if not yet assigned."""
        return self._sink

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add *node* to the network.

        If a node with the same ID already exists it is silently replaced.

        Parameters
        ----------
        node : Node
            The sensor node to add.
        """
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        """Return the node with identifier *node_id*, or ``None`` if not found.

        Parameters
        ----------
        node_id : str
            The node's unique identifier.

        Returns
        -------
        Node or None
            The corresponding :class:`~core.node.Node`, or ``None`` when
            *node_id* does not exist in the network.
        """
        return self._nodes.get(node_id)

    # ------------------------------------------------------------------
    # Sink / Base Station
    # ------------------------------------------------------------------

    def set_sink(self, node_id: str) -> None:
        """Designate an existing node as the Sink / Base Station.

        Parameters
        ----------
        node_id : str
            ID of a node **already added** to the network.

        Raises
        ------
        KeyError
            If *node_id* does not exist in the network.
        """
        if node_id not in self._nodes:
            raise KeyError(
                f"Node {node_id!r} not found in the network. "
                "Add the node before setting it as the sink."
            )
        self._sink = self._nodes[node_id]

    # ------------------------------------------------------------------
    # Distance
    # ------------------------------------------------------------------

    def distance(
        self,
        node_a: "Node | str",
        node_b: "Node | str",
    ) -> float:
        """Return the Euclidean distance between two nodes.

        Parameters
        ----------
        node_a, node_b : Node or str
            Either :class:`~core.node.Node` objects or node ID strings.

        Returns
        -------
        float
            Euclidean distance: ``sqrt((x1-x2)² + (y1-y2)²)``.

        Raises
        ------
        KeyError
            If a string ID is passed and the node is not in the network.
        TypeError
            If *node_a* or *node_b* is neither a ``Node`` nor a ``str``.
        """
        a = self._resolve_node(node_a)
        b = self._resolve_node(node_b)
        return math.hypot(a.x - b.x, a.y - b.y)

    def _resolve_node(self, ref: "Node | str") -> Node:
        """Return a Node object from either a Node or a string ID."""
        if isinstance(ref, Node):
            return ref
        if isinstance(ref, str):
            node = self._nodes.get(ref)
            if node is None:
                raise KeyError(f"Node {ref!r} not found in the network.")
            return node
        raise TypeError(
            f"Expected Node or str, got {type(ref).__name__!r}"
        )

    # ------------------------------------------------------------------
    # Neighbor discovery
    # ------------------------------------------------------------------

    def update_neighbors(self) -> None:
        """Recompute bidirectional neighbor relationships for all nodes.

        Algorithm
        ---------
        1. Clear every node's current neighbor set (removes stale data).
        2. For every unique pair (A, B), compute Euclidean distance.
        3. If distance <= :attr:`communication_range`, add each node to
           the other's neighbor set.

        Call this method whenever nodes are added, removed, or their
        positions change.
        """
        node_list = list(self._nodes.values())

        # Step 1: clear existing neighbor sets
        for node in node_list:
            node._neighbors = set()  # direct access for efficiency

        # Step 2 & 3: rebuild
        for i, node_a in enumerate(node_list):
            for node_b in node_list[i + 1 :]:
                if math.hypot(node_a.x - node_b.x, node_a.y - node_b.y) <= self._communication_range:
                    node_a.add_neighbor(node_b.id)
                    node_b.add_neighbor(node_a.id)

    # ------------------------------------------------------------------
    # Neighbor retrieval
    # ------------------------------------------------------------------

    def get_neighbors(self, node_id: str) -> list[Node]:
        """Return the **alive** direct neighbors of the specified node.

        Dead nodes are present in :attr:`nodes` but are excluded from
        this list so the routing layer never attempts to use them.

        Parameters
        ----------
        node_id : str
            ID of the node whose neighbors are requested.

        Returns
        -------
        list[Node]
            Alive neighbor nodes.  Order is not guaranteed.

        Raises
        ------
        KeyError
            If *node_id* does not exist in the network.
        """
        if node_id not in self._nodes:
            raise KeyError(f"Node {node_id!r} not found in the network.")

        node = self._nodes[node_id]
        alive_neighbors: list[Node] = []
        for neighbor_id in node.neighbors:
            neighbor = self._nodes.get(neighbor_id)
            if neighbor is not None and neighbor.alive:
                alive_neighbors.append(neighbor)
        return alive_neighbors

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        sink_id = self._sink.id if self._sink else "None"
        return (
            f"Network(nodes={len(self._nodes)}, "
            f"range={self._communication_range}, "
            f"sink={sink_id!r})"
        )

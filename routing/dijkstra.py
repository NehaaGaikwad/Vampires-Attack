"""
routing/dijkstra.py
===================
Dijkstra shortest-path algorithm for the Wireless Sensor Network (WSN).

Responsibilities
----------------
- Compute the shortest path (minimum total Euclidean distance) between
  two nodes in the network.
- Use the existing ``Network.get_neighbors()`` API to discover alive
  neighbours only — dead nodes are never included.
- Use ``Network.distance()`` for edge weights — no duplicate distance
  calculation.

Non-Responsibilities
--------------------
- This module does NOT track packet state.
- This module does NOT consume energy.
- This module does NOT update routing tables.

Algorithm
---------
Standard Dijkstra with a binary heap priority queue
(``heapq`` from the Python standard library).

Edge weights are the Euclidean distances between neighbouring nodes as
returned by ``network.distance()``.

When multiple equal-cost paths exist the algorithm is deterministic
because the priority queue breaks ties by node ID string comparison
(second element of the heap tuple).

Return Value
------------
- A list of node IDs in path order: ``[source, ..., destination]``.
- Returns ``None`` if no path exists (unreachable destination).
- Returns ``[source]`` when source == destination.
"""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.network import Network


def shortest_path(
    network: "Network",
    source: str,
    destination: str,
) -> Optional[list[str]]:
    """Compute the shortest path from *source* to *destination*.

    Uses Dijkstra's algorithm with Euclidean edge weights from
    ``network.distance()``.  Only alive nodes are considered; dead nodes
    are excluded via ``network.get_neighbors()``.

    Parameters
    ----------
    network : Network
        The WSN network topology.
    source : str
        Node ID of the starting node.
    destination : str
        Node ID of the target node.

    Returns
    -------
    list[str] or None
        An ordered list of node IDs representing the shortest path,
        including both *source* and *destination*.
        Returns ``[source]`` when source == destination.
        Returns ``None`` when no path exists (unreachable) or when
        *source* / *destination* do not exist in the network or are dead.

    Notes
    -----
    The algorithm is deterministic for equal-cost paths: ties in
    accumulated distance are broken by node ID lexicographic order.
    """
    # --- Validation: source node ---
    source_node = network.get_node(source)
    if source_node is None:
        return None  # source does not exist
    if not source_node.alive:
        return None  # source is dead

    # --- Validation: destination node ---
    dest_node = network.get_node(destination)
    if dest_node is None:
        return None  # destination does not exist
    if not dest_node.alive:
        return None  # destination is dead

    # --- Trivial case ---
    if source == destination:
        return [source]

    # --- Dijkstra ---
    # Priority queue entries: (accumulated_distance, node_id, path_so_far)
    # node_id is included as the second element so that equal-distance
    # entries are broken deterministically by lexicographic order.
    initial_entry = (0.0, source, [source])
    heap: list[tuple[float, str, list[str]]] = [initial_entry]

    # Set of node IDs that have been finalised (shortest path confirmed).
    visited: set[str] = set()

    while heap:
        dist, node_id, path = heapq.heappop(heap)

        # Skip if already settled.
        if node_id in visited:
            continue
        visited.add(node_id)

        # Reached the destination — return the path.
        if node_id == destination:
            return path

        # Expand neighbours (alive only, via network.get_neighbors).
        try:
            neighbours = network.get_neighbors(node_id)
        except KeyError:
            # node_id not in network (should not happen, but be safe)
            continue

        for neighbour in neighbours:
            n_id = neighbour.id
            if n_id in visited:
                continue
            edge_weight = network.distance(node_id, n_id)
            new_dist = dist + edge_weight
            heapq.heappush(heap, (new_dist, n_id, path + [n_id]))

    # No path found.
    return None

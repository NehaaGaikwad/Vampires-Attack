"""
routing/routing_table.py
========================
Routing table for storing next-hop decisions.

Responsibilities
----------------
- Map a destination node ID to the next-hop node ID on the shortest
  path from the current node's perspective.
- Provide clean set / get / remove / clear operations.
- Provide existence checking.

Non-Responsibilities
--------------------
- Does NOT compute routes (that is Dijkstra's job).
- Does NOT interact with the Network or EnergyModel.
- Does NOT track packet state.

Usage Pattern
-------------
The Router populates the routing table after running Dijkstra, then
uses it to look up the immediate next hop for a given destination.

Example
-------
::

    table = RoutingTable()
    table.set_next_hop("SINK", "N3")

    hop = table.get_next_hop("SINK")  # returns "N3"
    table.has_route("SINK")           # True
    table.remove_route("SINK")
    table.has_route("SINK")           # False
    table.clear()
"""

from __future__ import annotations

from typing import Optional


class RoutingTable:
    """A simple destination → next-hop routing table.

    The table maps each destination node ID to the immediate next-hop
    node ID that a packet should be forwarded to on the path toward
    that destination.

    The table is not scoped to a particular source node; the Router is
    responsible for managing per-source or shared table instances as
    appropriate.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        # Internal store: destination_id -> next_hop_id
        self._table: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def set_next_hop(self, destination: str, next_hop: str) -> None:
        """Set (or update) the next hop for *destination*.

        Parameters
        ----------
        destination : str
            The destination node ID.
        next_hop : str
            The immediate next-hop node ID toward *destination*.

        Raises
        ------
        ValueError
            If *destination* or *next_hop* is an empty string.
        """
        if not destination:
            raise ValueError("destination must be a non-empty node ID string.")
        if not next_hop:
            raise ValueError("next_hop must be a non-empty node ID string.")
        self._table[destination] = next_hop

    def remove_route(self, destination: str) -> None:
        """Remove the routing entry for *destination*.

        Silently does nothing if the entry does not exist.

        Parameters
        ----------
        destination : str
            The destination node ID whose entry should be removed.
        """
        self._table.pop(destination, None)

    def clear(self) -> None:
        """Remove all routing entries from the table."""
        self._table.clear()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_next_hop(self, destination: str) -> Optional[str]:
        """Return the next-hop node ID for *destination*.

        Parameters
        ----------
        destination : str
            The destination node ID to look up.

        Returns
        -------
        str or None
            The next-hop node ID, or ``None`` if no route exists for
            *destination*.
        """
        return self._table.get(destination)

    def has_route(self, destination: str) -> bool:
        """Return ``True`` if a route to *destination* is stored.

        Parameters
        ----------
        destination : str
            The destination node ID to check.

        Returns
        -------
        bool
        """
        return destination in self._table

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the number of routes stored in the table."""
        return len(self._table)

    def __repr__(self) -> str:
        return f"RoutingTable({self._table!r})"

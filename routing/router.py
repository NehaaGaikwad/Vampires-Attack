"""
routing/router.py
=================
The Router is the main routing interface for the WSN simulator.

Responsibilities
----------------
- Coordinate Packet, Dijkstra, RoutingTable, Network, and EnergyModel.
- Provide ``find_route(source, destination)`` to compute the shortest path.
- Provide ``get_next_hop(current_node, destination)`` for next-hop lookup.
- Provide ``route_packet(packet)`` to forward a Packet hop-by-hop until
  it is delivered, expired, or dropped.
- Manage a ``RoutingTable`` as a cache of recent routing decisions.
- Enforce dead-node safety at every forwarding step.
- Increment ``node.forwarded`` at the correct points (intermediate nodes
  that receive and re-forward a packet).
- Integrate with ``EnergyModel.transmit()`` for every physical hop.

Non-Responsibilities
--------------------
- Does NOT implement Vampire Attack logic.
- Does NOT implement detection or mitigation.
- Does NOT implement simulation or GUI logic.

Forwarded Counter Semantics
---------------------------
For a packet travelling N1 → N2 → N3 → SINK:

- N1 (source):    ``sent`` incremented by EnergyModel, ``forwarded`` = 0.
- N2 (relay):     ``received`` incremented by EnergyModel, ``forwarded`` += 1.
- N3 (relay):     ``received`` incremented by EnergyModel, ``forwarded`` += 1.
- SINK (dest):    ``received`` incremented by EnergyModel, ``forwarded`` = 0.

Only nodes that receive *and then forward* a packet have their
``forwarded`` counter incremented.

Error Handling
--------------
``find_route`` and ``get_next_hop`` return ``None`` to signal failure
conditions (no path, dead node, nonexistent node) rather than raising
exceptions.  ``route_packet`` marks the packet as DROPPED or EXPIRED as
appropriate and returns it — it never raises for normal routing failures.

EnergyModel integration raises ``NodeDeadError`` when a node dies between
the route calculation and the actual transmission.  The Router handles this
by stopping forwarding and marking the packet as DROPPED.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from routing.dijkstra import shortest_path
from routing.routing_table import RoutingTable

if TYPE_CHECKING:
    from core.network import Network
    from core.packet import Packet
    from energy.energy_model import EnergyModel



class Router:
    """Main routing interface for the WSN simulator.

    Parameters
    ----------
    network : Network
        The WSN topology containing all nodes.
    energy_model : EnergyModel
        The energy model used for physical transmissions.

    Attributes
    ----------
    routing_table : RoutingTable
        Cache of routing decisions (destination → next hop).
        Populated lazily by ``find_route`` and ``get_next_hop``.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        network: "Network",
        energy_model: "EnergyModel",
    ) -> None:
        self._network = network
        self._energy_model = energy_model
        self.routing_table: RoutingTable = RoutingTable()

    # ------------------------------------------------------------------
    # Properties (read-only access to injected dependencies)
    # ------------------------------------------------------------------

    @property
    def network(self) -> "Network":
        """The underlying WSN network topology."""
        return self._network

    @property
    def energy_model(self) -> "EnergyModel":
        """The energy model used for transmission calculations."""
        return self._energy_model

    # ------------------------------------------------------------------
    # find_route
    # ------------------------------------------------------------------

    def find_route(
        self,
        source: str,
        destination: str,
        *,
        excluded_nodes: set[str] | None = None,
    ) -> Optional[list[str]]:
        """Find the shortest path from *source* to *destination*.

        Uses Dijkstra's algorithm with Euclidean edge weights.  Only
        alive nodes are considered; dead nodes are automatically excluded
        by ``network.get_neighbors()``.

        The result is **not** stored in the routing table automatically
        because the full path is returned.  Use ``get_next_hop`` if you
        want the routing-table cache to be populated.

        Parameters
        ----------
        source : str
            Node ID of the starting node.
        destination : str
            Node ID of the target node.

        Returns
        -------
        list[str] or None
            Ordered list of node IDs from *source* to *destination*
            (inclusive), or ``None`` if:

            - *source* or *destination* does not exist in the network.
            - *source* or *destination* is dead (``node.alive == False``).
            - No path exists between *source* and *destination*.

        Examples
        --------
        ::

            route = router.find_route("N1", "SINK")
            # => ["N1", "N3", "N5", "SINK"]  or None
        """
        return shortest_path(
            self._network,
            source,
            destination,
            excluded_nodes=excluded_nodes,
        )

    # ------------------------------------------------------------------
    # get_next_hop
    # ------------------------------------------------------------------

    def get_next_hop(
        self,
        current_node: str,
        destination: str,
    ) -> Optional[str]:
        """Return the immediate next hop toward *destination*.

        Looks up the routing table first.  On a cache miss, calls
        Dijkstra and populates the routing table with the full path's
        next hops before returning.

        Parameters
        ----------
        current_node : str
            Node ID of the node requesting the next hop.
        destination : str
            Node ID of the target node.

        Returns
        -------
        str or None
            Node ID of the immediate next-hop node, or ``None`` if:

            - *current_node* == *destination* (no hop required).
            - No path exists.
            - *current_node* or *destination* is dead or nonexistent.

        Examples
        --------
        ::

            # Route: N1 -> N3 -> N5 -> SINK
            router.get_next_hop("N1", "SINK")  # => "N3"
            router.get_next_hop("N3", "SINK")  # => "N5"
            router.get_next_hop("N5", "SINK")  # => "SINK"
        """
        if current_node == destination:
            return None

        current = self._network.get_node(current_node)
        target = self._network.get_node(destination)
        if (
            current is None
            or not current.alive
            or target is None
            or not target.alive
        ):
            self.routing_table.remove_route(destination)
            return None

        # Check routing table cache first.
        cached = self.routing_table.get_next_hop(destination)
        if cached is not None:
            # Validate that the cached next hop is still alive and reachable.
            cached_node = self._network.get_node(cached)
            alive_neighbors = {
                neighbor.id for neighbor in self._network.get_neighbors(current_node)
            }
            if (
                cached_node is not None
                and cached_node.alive
                and cached in alive_neighbors
            ):
                return cached
            # Cache is stale — remove it and recalculate.
            self.routing_table.remove_route(destination)

        # Compute full route via Dijkstra.
        path = shortest_path(self._network, current_node, destination)
        if path is None or len(path) < 2:
            return None

        # Populate routing table with all next-hop entries along the path.
        # For each node at index i, the next hop toward destination is
        # the node at index i+1.
        self._populate_routing_table(path)

        # The immediate next hop from current_node is path[1].
        return path[1]

    # ------------------------------------------------------------------
    # route_packet
    # ------------------------------------------------------------------

    def route_packet(
        self,
        packet: "Packet",
        packet_size: Optional[int] = None,
        on_progress: Callable[[dict[str, object]], None] | None = None,
    ) -> "Packet":
        """Forward *packet* hop-by-hop from its current node to its destination.

        The packet's route is computed via Dijkstra starting from
        ``packet.current_node``.  The packet is then advanced one hop at
        a time, consuming energy via ``EnergyModel.transmit()`` at each
        step.

        The method stops when:

        - The packet is delivered (``packet.delivered == True``).
        - The packet's TTL is exhausted (``packet.expired == True``).
        - A loop is detected (``packet.dropped == True``).
        - A node dies during forwarding.
        - No route is found.

        The ``forwarded`` counter on intermediate nodes is incremented
        by this method (not by EnergyModel).

        Parameters
        ----------
        packet : Packet
            The packet to route.  It must be ``IN_TRANSIT``.
        packet_size : int, optional
            Override the packet's own ``packet_size`` for the energy
            calculation.  Defaults to ``packet.packet_size``.

        Returns
        -------
        Packet
            The same *packet* object (modified in-place) after routing.

        Notes
        -----
        If *packet* is not ``IN_TRANSIT`` when this method is called, it
        is returned immediately without modification.
        """
        from energy.energy_model import NodeDeadError

        if not packet.in_transit:
            return packet

        size = packet_size if packet_size is not None else packet.packet_size
        stale_hop_retries = 0

        while packet.in_transit:
            sender_id = packet.current_node
            sender_node = self._network.get_node(sender_id)
            if sender_node is None or not sender_node.alive:
                packet.mark_failed()
                return packet
            if packet.ttl <= 0:
                packet.mark_expired()
                return packet

            route = shortest_path(
                self._network,
                sender_id,
                packet.destination,
                excluded_nodes=packet.visited - {sender_id},
            )
            if route is None:
                packet.mark_failed()
                return packet
            if len(route) == 1:
                packet.mark_delivered()
                return packet

            receiver_id = route[1]
            if receiver_id in packet.visited:
                packet.mark_dropped()
                return packet

            receiver_node = self._network.get_node(receiver_id)

            if receiver_node is None or not receiver_node.alive:
                stale_hop_retries += 1
                if stale_hop_retries > len(self._network.nodes):
                    packet.mark_failed()
                    return packet
                continue

            alive_neighbour_ids = {n.id for n in self._network.get_neighbors(sender_id)}
            if receiver_id not in alive_neighbour_ids:
                stale_hop_retries += 1
                if stale_hop_retries > len(self._network.nodes):
                    packet.mark_failed()
                    return packet
                continue

            distance = self._network.distance(sender_id, receiver_id)

            try:
                self._energy_model.transmit(
                    sender=sender_node,
                    receiver=receiver_node,
                    packet_size=size,
                    distance=distance,
                )
            except NodeDeadError:
                stale_hop_retries += 1
                if stale_hop_retries > len(self._network.nodes):
                    packet.mark_failed()
                    return packet
                continue

            packet.advance(receiver_id)
            stale_hop_retries = 0

            if sender_id != packet.source:
                sender_node.forwarded += 1

            if on_progress is not None:
                on_progress(
                    {
                        "route": packet.route,
                        "planned_route": list(route),
                        "sender": sender_id,
                        "receiver": receiver_id,
                        "status": packet.status.name,
                        "hops": packet.hops,
                    }
                )

        return packet

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate_routing_table(self, path: list[str]) -> None:
        """Store next-hop entries for every node along *path*.

        For a path [A, B, C, D]:
        - ``routing_table.set_next_hop("D", "B")``  (from A's perspective)
        - This method stores the full-path next hops for nodes along the
          route so that intermediate nodes can also benefit from the cache.

        In practice the table is keyed by destination and stores the
        next hop from the node that requested the route.  We store just
        the single entry for the immediate next hop to the destination.

        Parameters
        ----------
        path : list[str]
            Ordered path as returned by :func:`routing.dijkstra.shortest_path`.
        """
        if len(path) < 2:
            return
        destination = path[-1]
        next_hop = path[1]  # immediate next hop from path[0]
        self.routing_table.set_next_hop(destination, next_hop)

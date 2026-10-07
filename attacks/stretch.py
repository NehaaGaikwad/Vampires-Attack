"""
attacks/stretch.py
==================
Implements the Stretch Vampire Attack for Wireless Sensor Networks (WSN).

Responsibilities
----------------
- Extends :class:`~attacks.base.BaseAttack` with :attr:`~attacks.base.AttackType.STRETCH`.
- Artificially inflates / elongates routes involving the malicious node.
- Preserves packet integrity: source remains first, destination remains final.
- Uses actual network topology (:class:`~core.network.Network`) to ensure all
  detour hops correspond to real, alive wireless links.
- Scales path elongation according to :class:`~attacks.base.AttackIntensity` (LOW, MEDIUM, HIGH).
- Respects Time-To-Live (TTL) boundaries.
- Reverts safely to the unmanipulated route when inactive, when no longer valid path exists,
  or when network information is insufficient.

Vampire Attack Model: Stretch
-----------------------------
In a Stretch Attack (Vasserman & Hopper, 2013), a malicious node artificially
diverts packets along an unnecessarily long path rather than forwarding them
directly along the optimal shortest path. By routing packets through additional
innocent relay nodes, the attacker drains their batteries via redundant
transmissions and receptions, degrading network lifetime and causing premature node deaths.

Intensity Semantics
-------------------
- LOW:
    Minimal route inflation. Selects the shortest valid detour path strictly
    longer than the optimal route.
- MEDIUM:
    Moderate route inflation. Selects a median-length valid detour path.
- HIGH:
    Maximum reasonable route inflation. Selects the longest available simple
    path within the remaining TTL budget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from attacks.base import AttackIntensity, AttackType, BaseAttack

if TYPE_CHECKING:
    from core.network import Network
    from core.packet import Packet


class StretchAttack(BaseAttack):
    """Stretch Vampire Attack implementation.

    Artificially elongates packet routes traversing the attacker node to
    cause maximum distributed energy exhaustion across innocent intermediate nodes.

    Parameters
    ----------
    attacker_node_id : str
        Unique identifier of the malicious sensor node.
    intensity : AttackIntensity | str, default AttackIntensity.MEDIUM
        Aggressiveness level determining how much the route is inflated.
    start_time : float, default 0.0
        Simulation time at which the attack becomes active.
    duration : float, default 100.0
        Simulation time window during which the attack remains active.
    """

    def __init__(
        self,
        attacker_node_id: str,
        intensity: Union[AttackIntensity, str] = AttackIntensity.MEDIUM,
        start_time: float = 0.0,
        duration: float = 100.0,
        **kwargs,
    ) -> None:
        # Allow callers passing attack_type explicitly or by position
        if "attack_type" in kwargs:
            kwargs.pop("attack_type")
        # Handle case where user passes AttackType or string as second positional argument
        if isinstance(intensity, AttackType) or (
            isinstance(intensity, str) and intensity.upper() in [t.name for t in AttackType]
        ):
            # Positional argument shift: (id, AttackType.STRETCH, intensity, start_time, duration)
            actual_intensity = kwargs.pop("actual_intensity", AttackIntensity.MEDIUM)
            super().__init__(
                attacker_node_id=attacker_node_id,
                attack_type=AttackType.STRETCH,
                intensity=actual_intensity,
                start_time=start_time,
                duration=duration,
            )
            return

        super().__init__(
            attacker_node_id=attacker_node_id,
            attack_type=AttackType.STRETCH,
            intensity=intensity,
            start_time=start_time,
            duration=duration,
        )

    # ------------------------------------------------------------------
    # Attack Execution API
    # ------------------------------------------------------------------

    def apply(
        self,
        target: Union[list[str], "Packet"],
        network: Optional["Network"] = None,
        current_time: float = 0.0,
        ttl: Optional[int] = None,
    ) -> list[str]:
        """Apply the Stretch Attack to a route or packet.

        Parameters
        ----------
        target : list[str] or Packet
            The current route (list of node ID strings) or an in-flight :class:`~core.packet.Packet`.
        network : Network, optional
            The network topology containing alive nodes and neighbor relationships.
        current_time : float, default 0.0
            Current simulation timestamp.
        ttl : int, optional
            Remaining Time-To-Live. If target is a Packet and ttl is None,
            the packet's ttl property is used. Default fallback is 64.

        Returns
        -------
        list[str]
            The manipulated route if active and applicable, otherwise a copy of the original route.
        """
        route, effective_ttl = self._extract_route_and_ttl(target, network, ttl)
        return self.manipulate_route(
            route=route,
            network=network,
            current_time=current_time,
            ttl=effective_ttl,
        )

    def manipulate_route(
        self,
        route: list[str],
        network: Optional["Network"] = None,
        current_time: float = 0.0,
        ttl: Optional[int] = None,
    ) -> list[str]:
        """Manipulate an existing route by stretching its path through extra nodes.

        Rules
        -----
        1. If attack is inactive at *current_time*: return original route.
        2. If *route* is empty or has fewer than 2 nodes: return original route.
        3. If *attacker_node_id* is not in *route*: return original route.
        4. If *attacker_node_id* is the final destination: return original route.
        5. If *network* is None: return original route (cannot invent fake nodes).
        6. Find all valid simple paths from attacker to destination avoiding previously
           visited nodes.
        7. Filter paths strictly longer than the original suffix and within TTL.
        8. Select detour path according to *intensity* (LOW, MEDIUM, HIGH).
        9. Reconstruct route preserving source as first node, destination as final node,
           and attacker at its transit point.

        Parameters
        ----------
        route : list[str]
            The initial ordered list of node IDs.
        network : Network, optional
            Network topology used to verify node existence and link connectivity.
        current_time : float, default 0.0
            Current simulation time.
        ttl : int, optional
            Maximum allowed hop count for the complete route.

        Returns
        -------
        list[str]
            The stretched route, or original route if stretching cannot be applied.
        """
        # Safety & lifecycle checks
        if not self.is_active(current_time):
            return list(route) if route is not None else []

        if not route or not isinstance(route, list) or len(route) < 2:
            return list(route) if isinstance(route, list) else []

        if self.attacker_node_id not in route:
            return list(route)

        attacker_idx = route.index(self.attacker_node_id)
        if attacker_idx == len(route) - 1:
            # Attacker is already the destination; cannot manipulate onward route
            return list(route)

        if network is None:
            # Insufficient topology info to guarantee real valid nodes
            return list(route)

        # Check attacker is alive in network
        attacker_node = network.get_node(self.attacker_node_id)
        if attacker_node is None or not attacker_node.alive:
            return list(route)

        destination = route[-1]
        dest_node = network.get_node(destination)
        if dest_node is None or not dest_node.alive:
            return list(route)

        # Nodes already traversed up to attacker (cannot be revisited in a simple stretch)
        prefix = route[: attacker_idx + 1]
        forbidden = set(prefix[:-1])  # Exclude attacker itself from forbidden

        # Suffix from attacker to destination in original route
        original_suffix = route[attacker_idx:]
        original_suffix_hops = len(original_suffix) - 1

        # Max hops allowed for the suffix
        effective_ttl = ttl if (ttl is not None and ttl > 0) else 64
        hops_before_attacker = attacker_idx
        max_suffix_hops = effective_ttl - hops_before_attacker

        if max_suffix_hops <= original_suffix_hops:
            # No TTL budget left to extend the path
            return list(route)

        # Discover valid simple paths from attacker to destination
        candidate_paths = self._find_simple_paths(
            network=network,
            start=self.attacker_node_id,
            target=destination,
            forbidden=forbidden,
            max_depth=min(max_suffix_hops, 25),
        )

        # Filter strictly longer paths that fit in TTL
        longer_paths = [
            p for p in candidate_paths
            if len(p) - 1 > original_suffix_hops and len(p) - 1 <= max_suffix_hops
        ]

        if not longer_paths:
            return list(route)

        # Sort candidate paths by hop count ascending, then by tie-breaker
        longer_paths.sort(key=lambda p: (len(p), p))

        # Select path based on intensity
        selected_path = self._select_by_intensity(longer_paths)

        # Reconstruct route: prefix[:-1] + selected_path (prefix ends with attacker, selected starts with attacker)
        stretched_route = prefix[:-1] + selected_path
        return stretched_route

    # ------------------------------------------------------------------
    # Path Search & Helper Logic
    # ------------------------------------------------------------------

    def _select_by_intensity(self, sorted_paths: list[list[str]]) -> list[str]:
        """Select a path from ascending-sorted candidates according to attack intensity."""
        if not sorted_paths:
            return []

        if self.intensity == AttackIntensity.LOW:
            # Minimal inflation: the shortest available detour
            return sorted_paths[0]
        elif self.intensity == AttackIntensity.MEDIUM:
            # Moderate inflation: median length detour
            idx = len(sorted_paths) // 2
            return sorted_paths[idx]
        else:  # HIGH
            # Maximum inflation: longest available detour within budget
            return sorted_paths[-1]

    @staticmethod
    def _find_simple_paths(
        network: "Network",
        start: str,
        target: str,
        forbidden: set[str],
        max_depth: int,
        max_paths: int = 150,
    ) -> list[list[str]]:
        """Find simple paths of alive nodes from start to target using bounded DFS."""
        results: list[list[str]] = []
        # Stack: (current_node_id, path_so_far, visited_set_in_path)
        stack: list[tuple[str, list[str], set[str]]] = [(start, [start], {start})]

        while stack and len(results) < max_paths:
            current, path, visited = stack.pop()

            if current == target:
                results.append(path)
                continue

            if len(path) - 1 >= max_depth:
                continue

            try:
                neighbors = network.get_neighbors(current)
            except KeyError:
                continue

            for neighbor in neighbors:
                n_id = neighbor.id
                if not neighbor.alive or n_id in forbidden or n_id in visited:
                    continue
                stack.append((n_id, path + [n_id], visited | {n_id}))

        return results

    @staticmethod
    def _extract_route_and_ttl(
        target: Union[list[str], "Packet"],
        network: Optional["Network"],
        ttl: Optional[int],
    ) -> tuple[list[str], int]:
        """Extract a route list and effective TTL from either a list or Packet."""
        if hasattr(target, "route") and hasattr(target, "destination"):
            history = list(getattr(target, "route", []))
            dest = getattr(target, "destination", None)
            effective_ttl = ttl if ttl is not None else getattr(target, "ttl", 64)

            if history and dest and history[-1] != dest:
                if network is not None:
                    try:
                        from routing.dijkstra import shortest_path
                        remaining = shortest_path(network, history[-1], dest)
                        if remaining and len(remaining) > 1:
                            return history[:-1] + remaining, effective_ttl
                    except (ImportError, Exception):
                        pass
                return history + [dest], effective_ttl

            return history, effective_ttl

        if isinstance(target, list):
            effective_ttl = ttl if ttl is not None else 64
            return list(target), effective_ttl

        return [], ttl if ttl is not None else 64

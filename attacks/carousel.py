"""
attacks/carousel.py
===================
Implements the Carousel Vampire Attack for Wireless Sensor Networks (WSN).

Responsibilities
----------------
- Extends :class:`~attacks.base.BaseAttack` with :attr:`~attacks.base.AttackType.CAROUSEL`.
- Introduces controlled routing loops / cycles involving the attacker node.
- Preserves packet integrity: source remains first, destination remains final.
- Strictly bounds loop repetitions by Time-To-Live (TTL) to prevent infinite loops.
- Scales loop repetitions according to :class:`~attacks.base.AttackIntensity` (LOW, MEDIUM, HIGH).
- Validates neighbor adjacency using :class:`~core.network.Network` when provided.
- Reverts safely to the unmanipulated route when inactive or when TTL is insufficient.

Vampire Attack Model: Carousel
------------------------------
In a Carousel Attack (Vasserman & Hopper, 2013), an attacker deliberately introduces
routing cycles into a packet's traversal path. The packet circles repeatedly between
the malicious node and neighbouring victim nodes, consuming transmission and reception
energy on every loop until its Time-To-Live (TTL) is exhausted. This drains victim
batteries in localized clusters while masquerading as valid forwarding.

Intensity Semantics
-------------------
- LOW:
    Minimal cycle inflation. Introduces 1 extra loop iteration (2 additional hops).
- MEDIUM:
    Moderate cycle inflation. Consumes approximately half of the remaining TTL budget.
- HIGH:
    Maximum cycle inflation. Consumes the maximum allowable loop repetitions within TTL.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from attacks.base import AttackIntensity, AttackType, BaseAttack

if TYPE_CHECKING:
    from core.network import Network
    from core.packet import Packet


class CarouselAttack(BaseAttack):
    """Carousel Vampire Attack implementation.

    Artificially introduces routing cycles into a packet's path to repeatedly
    drain the batteries of nodes in the cycle.

    Parameters
    ----------
    attacker_node_id : str
        Unique identifier of the malicious sensor node.
    intensity : AttackIntensity | str, default AttackIntensity.MEDIUM
        Aggressiveness level determining how many cycle repetitions are injected.
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
        # Handle positional or explicit attack_type keyword argument
        if "attack_type" in kwargs:
            kwargs.pop("attack_type")
        if isinstance(intensity, AttackType) or (
            isinstance(intensity, str) and intensity.upper() in [t.name for t in AttackType]
        ):
            actual_intensity = kwargs.pop("actual_intensity", AttackIntensity.MEDIUM)
            super().__init__(
                attacker_node_id=attacker_node_id,
                attack_type=AttackType.CAROUSEL,
                intensity=actual_intensity,
                start_time=start_time,
                duration=duration,
            )
            return

        super().__init__(
            attacker_node_id=attacker_node_id,
            attack_type=AttackType.CAROUSEL,
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
        """Apply the Carousel Attack to a route or packet.

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
            The manipulated route with cycle repetitions if active and applicable,
            otherwise a copy of the original route.
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
        """Manipulate an existing route by injecting a cycle involving the attacker.

        Rules
        -----
        1. If attack is inactive at *current_time*: return original route.
        2. If *route* is empty or has fewer than 2 nodes: return original route.
        3. If *attacker_node_id* is not in *route*: return original route.
        4. If *attacker_node_id* is the final destination: return original route.
        5. Identify a valid partner node adjacent to the attacker (e.g. next hop
           or an alive neighbor).
        6. Calculate remaining TTL budget: each loop (attacker -> partner -> attacker)
           consumes exactly 2 hops.
        7. If remaining TTL budget < 2: return original route (cannot cycle within TTL).
        8. Determine repetition count based on *intensity* (LOW, MEDIUM, HIGH).
        9. Reconstruct route: source is preserved first, destination is preserved final,
           and the total hop count strictly respects TTL.

        Parameters
        ----------
        route : list[str]
            The initial ordered list of node IDs.
        network : Network, optional
            Network topology used to verify neighbor adjacency and node liveness.
        current_time : float, default 0.0
            Current simulation time.
        ttl : int, optional
            Maximum allowed hop count for the complete route.

        Returns
        -------
        list[str]
            The looped carousel route, or original route if cycling cannot be safely applied.
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
            # Attacker is already the destination; cannot create forward cycle
            return list(route)

        # Identify partner node to cycle with
        partner_node_id = self._select_partner_node(route, attacker_idx, network)
        if partner_node_id is None:
            return list(route)

        # Base hops required for the original route
        base_hops = len(route) - 1
        effective_ttl = ttl if (ttl is not None and ttl > 0) else 64

        if effective_ttl <= base_hops:
            # No TTL budget left to insert extra loop hops
            return list(route)

        hop_budget = effective_ttl - base_hops
        # Each cycle of (partner -> attacker) adds 2 hops
        max_possible_reps = hop_budget // 2
        if max_possible_reps < 1:
            return list(route)

        # Determine repetitions based on intensity
        reps = self._determine_repetitions(max_possible_reps)
        if reps < 1:
            return list(route)

        # Construct the carousel route:
        # prefix: route[:attacker_idx + 1] (ends with attacker)
        # cycle hops: [partner, attacker] * reps
        # suffix: route[attacker_idx + 1:] (begins with next hop)
        prefix = route[: attacker_idx + 1]
        suffix = route[attacker_idx + 1 :]

        cycle_sequence: list[str] = []
        for _ in range(reps):
            cycle_sequence.extend([partner_node_id, self.attacker_node_id])

        looped_route = prefix + cycle_sequence + suffix

        # Final safety check: ensure total hops does not exceed TTL
        if len(looped_route) - 1 > effective_ttl:
            return list(route)

        return looped_route

    # ------------------------------------------------------------------
    # Helper Logic
    # ------------------------------------------------------------------

    def _determine_repetitions(self, max_possible: int) -> int:
        """Calculate loop repetitions based on intensity and maximum allowed by TTL."""
        if max_possible <= 1:
            return max_possible

        if self.intensity == AttackIntensity.LOW:
            # 1 repetition (2 extra hops)
            return 1
        elif self.intensity == AttackIntensity.MEDIUM:
            # Moderate repetitions: approximately half of the budget
            return max(1, min(max_possible, max(2, max_possible // 2)))
        else:  # HIGH
            # Maximum repetitions within TTL budget
            return max_possible

    def _select_partner_node(
        self,
        route: list[str],
        attacker_idx: int,
        network: Optional["Network"],
    ) -> Optional[str]:
        """Select a valid adjacent neighbor to cycle with the attacker."""
        # Candidate 1: The immediate next hop in the route
        candidate_next = route[attacker_idx + 1]

        if network is None:
            return candidate_next

        # If network is provided, verify attacker and candidate exist and are alive
        attacker_node = network.get_node(self.attacker_node_id)
        if attacker_node is None or not attacker_node.alive:
            return None

        # Check alive neighbors of attacker
        try:
            alive_neighbors = network.get_neighbors(self.attacker_node_id)
        except KeyError:
            return None

        alive_neighbor_ids = {n.id for n in alive_neighbors}

        if candidate_next in alive_neighbor_ids:
            return candidate_next

        # Candidate 2: The previous hop in the route
        if attacker_idx > 0:
            candidate_prev = route[attacker_idx - 1]
            if candidate_prev in alive_neighbor_ids:
                return candidate_prev

        # Candidate 3: Any alive neighbor
        if alive_neighbor_ids:
            # Deterministic selection: sorted first
            return sorted(alive_neighbor_ids)[0]

        return None

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

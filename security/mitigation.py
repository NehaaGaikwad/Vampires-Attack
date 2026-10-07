"""
security/mitigation.py
======================
Mitigation and node isolation layer for Vampire Attack containment in Wireless
Sensor Networks (WSN).

Responsibilities
----------------
- Consumes :class:`~security.detector.DetectionResult` from Phase 3 detection layer.
- Maintains an independent blacklist / isolation set of malicious node IDs.
- Ensures isolated nodes remain intact in the network (for logging, visualization,
  and metrics) without modifying node batteries or deleting node instances.
- Re-routes network traffic around isolated nodes using the existing Dijkstra
  shortest path infrastructure via an isolated network view.
- Provides idempotent isolation and explicit recovery / de-isolation controls.
- Preserves detection evidence (reasons, suspicion score) inside :class:`MitigationResult`.
- Validates that recalculated routes never traverse any isolated or dead nodes.

Architecture
------------
Detection (Phase 3)
      │
      ▼
DetectionResult
      │
      ▼
MitigationManager (Phase 4)
      ├── isolate_node / apply_detection
      ├── is_isolated / clear_isolation
      └── recalculate_route
              │
              ▼
      IsolatedNetworkView
              │
              ▼
      routing.dijkstra.shortest_path
              │
              ▼
      New Safe Route (isolated nodes strictly excluded)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

from routing.dijkstra import shortest_path

if TYPE_CHECKING:
    from core.network import Network
    from core.node import Node
    from routing.router import Router
    from security.detector import DetectionResult


@dataclass(frozen=True)
class MitigationResult:
    """Immutable record of an isolation or mitigation action taken on a node.

    Attributes
    ----------
    node_id : str
        Identifier of the sensor node.
    isolated : bool
        Whether the node is currently in the isolated / blacklisted state.
    reasons : list[str]
        Detection reasons that triggered isolation (e.g. 'hop_inflation', 'route_cycle').
    suspicion_score : float, optional
        Composite suspicion score from the detection layer that triggered isolation.
    details : dict[str, Any]
        Additional context and telemetry metadata associated with the mitigation action.
    """

    node_id: str
    isolated: bool
    reasons: list[str] = field(default_factory=list)
    suspicion_score: Optional[float] = None
    details: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "ISOLATED" if self.isolated else "ACTIVE"
        return (
            f"MitigationResult(node={self.node_id!r}, status={status}, "
            f"score={self.suspicion_score}, reasons={self.reasons})"
        )


class IsolatedNetworkView:
    """A lightweight read-only proxy over Network that filters out isolated nodes.

    This enables the existing :func:`routing.dijkstra.shortest_path` algorithm
    to compute optimal routes strictly avoiding isolated nodes without copying,
    forking, or mutating the underlying network topology or node states.

    Parameters
    ----------
    network : Network
        The underlying physical WSN network topology.
    isolated_nodes : set[str]
        Set of node IDs currently blacklisted by the mitigation manager.
    """

    def __init__(self, network: "Network", isolated_nodes: set[str]) -> None:
        self._network = network
        self._isolated = isolated_nodes

    def get_node(self, node_id: str) -> Optional["Node"]:
        """Return node from network, or None if the node is isolated."""
        if node_id in self._isolated:
            return None
        return self._network.get_node(node_id)

    def get_neighbors(self, node_id: str) -> list["Node"]:
        """Return alive neighbors of node_id, excluding any isolated nodes."""
        if node_id in self._isolated:
            return []
        neighbors = self._network.get_neighbors(node_id)
        return [n for n in neighbors if n.id not in self._isolated]

    def distance(self, a: Union["Node", str], b: Union["Node", str]) -> float:
        """Delegate distance calculation to the underlying network."""
        return self._network.distance(a, b)


class MitigationManager:
    """Manages node isolation, blacklisting, and route recalculation.

    Parameters
    ----------
    initial_isolated : set[str] or list[str], optional
        Optional initial collection of blacklisted node IDs.
    """

    def __init__(
        self,
        initial_isolated: Optional[Union[set[str], list[str]]] = None,
    ) -> None:
        self._isolated_nodes: set[str] = set()
        self._isolation_records: dict[str, MitigationResult] = {}

        if initial_isolated:
            for n_id in initial_isolated:
                self.isolate_node(n_id)

    # ------------------------------------------------------------------
    # Isolation / Blacklist Management
    # ------------------------------------------------------------------

    def isolate_node(
        self,
        node_id: str,
        reasons: Optional[list[str]] = None,
        suspicion_score: Optional[float] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> MitigationResult:
        """Isolate a sensor node from network routing.

        Parameters
        ----------
        node_id : str
            Unique identifier of the node to blacklist.
        reasons : list[str], optional
            Detection reasons triggering isolation.
        suspicion_score : float, optional
            Detection suspicion score triggering isolation.
        details : dict[str, Any], optional
            Additional telemetry and diagnostic metadata.

        Returns
        -------
        MitigationResult
            The recorded mitigation state for this node.

        Raises
        ------
        ValueError
            If node_id is empty or whitespace-only.
        TypeError
            If node_id is not a string.
        """
        if not isinstance(node_id, str):
            raise TypeError(f"node_id must be a string, got {type(node_id).__name__}")
        clean_id = node_id.strip()
        if not clean_id:
            raise ValueError("node_id must not be empty or whitespace-only.")

        self._isolated_nodes.add(clean_id)

        result = MitigationResult(
            node_id=clean_id,
            isolated=True,
            reasons=list(reasons) if reasons else [],
            suspicion_score=suspicion_score,
            details=dict(details) if details else {},
        )
        self._isolation_records[clean_id] = result
        return result

    def is_isolated(self, node_id: str) -> bool:
        """Check whether a node is currently isolated / blacklisted.

        Parameters
        ----------
        node_id : str
            Identifier of the node to check.

        Returns
        -------
        bool
            True if the node is isolated, False otherwise.
        """
        return node_id in self._isolated_nodes

    def get_isolated_nodes(self) -> set[str]:
        """Return a copy of all currently isolated node IDs."""
        return set(self._isolated_nodes)

    def get_isolation_record(self, node_id: str) -> Optional[MitigationResult]:
        """Retrieve the mitigation record and evidence for an isolated node."""
        return self._isolation_records.get(node_id)

    def clear_isolation(self, node_id: str) -> bool:
        """Remove a node from isolation and restore its eligibility for routing.

        Parameters
        ----------
        node_id : str
            Identifier of the node to de-isolate.

        Returns
        -------
        bool
            True if the node was previously isolated and removed, False if it was not isolated.
        """
        if node_id in self._isolated_nodes:
            self._isolated_nodes.remove(node_id)
            self._isolation_records.pop(node_id, None)
            return True
        return False

    def clear_all(self) -> None:
        """Remove all nodes from isolation."""
        self._isolated_nodes.clear()
        self._isolation_records.clear()

    # ------------------------------------------------------------------
    # Detection Layer Integration
    # ------------------------------------------------------------------

    def apply_detection(
        self,
        detection_result: "DetectionResult",
    ) -> Optional[MitigationResult]:
        """Process a DetectionResult and isolate the node if it was flagged as suspicious.

        Parameters
        ----------
        detection_result : DetectionResult
            The detection assessment from Phase 3 AttackDetector.

        Returns
        -------
        MitigationResult or None
            A MitigationResult if the node was isolated, or None if the result was not suspicious.
        """
        if not detection_result.suspicious:
            return None

        return self.isolate_node(
            node_id=detection_result.node_id,
            reasons=detection_result.reasons,
            suspicion_score=detection_result.suspicion_score,
            details=detection_result.details,
        )

    def apply_detections(
        self,
        detection_results: list["DetectionResult"],
    ) -> list[MitigationResult]:
        """Process multiple DetectionResults and isolate all suspicious nodes.

        Parameters
        ----------
        detection_results : list[DetectionResult]
            List of detection assessments.

        Returns
        -------
        list[MitigationResult]
            Records for all newly or confirmed isolated nodes.
        """
        mitigations: list[MitigationResult] = []
        for res in detection_results:
            mit = self.apply_detection(res)
            if mit is not None:
                mitigations.append(mit)
        return mitigations

    # ------------------------------------------------------------------
    # Route Recalculation & Exclusion
    # ------------------------------------------------------------------

    def recalculate_route(
        self,
        network_or_router: Union["Network", "Router"],
        source: str,
        destination: str,
    ) -> Optional[list[str]]:
        """Recalculate the shortest path between source and destination excluding isolated nodes.

        Uses the existing Dijkstra algorithm and underlying topology, ensuring that
        no isolated node can appear anywhere along the new route.

        Parameters
        ----------
        network_or_router : Network or Router
            The network topology or Router instance.
        source : str
            Node ID of the starting node.
        destination : str
            Node ID of the target destination node.

        Returns
        -------
        list[str] or None
            An ordered list of node IDs forming a valid path excluding all isolated nodes,
            or None if no valid route exists or if source/destination is isolated.
        """
        # Resolve network from Router if provided
        if hasattr(network_or_router, "network"):
            network: "Network" = getattr(network_or_router, "network")
            router: Optional["Router"] = network_or_router
        else:
            network = network_or_router
            router = None

        if not network:
            return None

        # If source or destination is isolated, no valid route can be formed
        if source in self._isolated_nodes or destination in self._isolated_nodes:
            return None

        # Verify source and destination exist in network and are alive
        src_node = network.get_node(source)
        if src_node is None or not src_node.alive:
            return None

        dst_node = network.get_node(destination)
        if dst_node is None or not dst_node.alive:
            return None

        # Trivial single-node path
        if source == destination:
            return [source]

        # Use IsolatedNetworkView with the existing Dijkstra implementation
        view = IsolatedNetworkView(network, self._isolated_nodes)
        new_path = shortest_path(view, source, destination)

        if not new_path or len(new_path) < 2:
            return None

        # Post-computation validation
        if not self._validate_route(new_path, network, source, destination):
            return None

        # If router is provided, update its routing table cache with the new safe next-hop
        if router is not None and hasattr(router, "routing_table"):
            router.routing_table.set_next_hop(destination, new_path[1])

        return new_path

    # ------------------------------------------------------------------
    # Validation Helper
    # ------------------------------------------------------------------

    def _validate_route(
        self,
        route: list[str],
        network: "Network",
        expected_source: str,
        expected_destination: str,
    ) -> bool:
        """Verify that a recalculated route is strictly valid and isolates all blacklisted nodes."""
        if not route or len(route) < 1:
            return False

        if route[0] != expected_source or route[-1] != expected_destination:
            return False

        # Ensure no isolated node appears anywhere in the route
        for node_id in route:
            if node_id in self._isolated_nodes:
                return False
            n = network.get_node(node_id)
            if n is None or not n.alive:
                return False

        # Verify physical link connectivity along every hop
        for i in range(len(route) - 1):
            sender_id = route[i]
            receiver_id = route[i + 1]
            try:
                alive_neighbor_ids = {n.id for n in network.get_neighbors(sender_id)}
            except KeyError:
                return False
            if receiver_id not in alive_neighbor_ids:
                return False

        return True

"""
security/detector.py
====================
Rule-based anomaly detection layer for identifying Vampire Attacks in Wireless
Sensor Networks (WSN).

Responsibilities
----------------
- Observes network behavior across four primary Vampire Attack indicators:
  1. Abnormal forwarding count (packet relay floods)
  2. Hop inflation (routes stretched beyond optimal Dijkstra paths)
  3. Route repetition / cycles (packets looping through carousel nodes)
  4. Abnormal energy consumption (excessive battery drain)
- Calculates normalized sub-scores for each behavioral signal.
- Synthesizes signals into a unified suspicion score [0.0, 1.0].
- Generates transparent, human-readable explanations in :class:`DetectionResult`.
- Supports single-node analysis and network-wide batch detection.
- Decoupled from concrete attack classes (behavioral detection only).
- Does NOT perform mitigation, isolation, or route modification (reserved for Phase 4).

Detection Formulas & Methodology
---------------------------------
1. Forwarding Anomaly:
   f_ratio = node.forwarded / forwarding_threshold
   Signal score = min(1.0, f_ratio)
   Flagged if node.forwarded >= forwarding_threshold.

2. Hop Inflation:
   inflation_ratio = observed_hops / expected_shortest_path_hops
   Signal score = min(1.0, (inflation_ratio - 1.0) / (hop_inflation_threshold - 1.0))
   Flagged if inflation_ratio >= hop_inflation_threshold.

3. Route Repetition / Cycle:
   count = route.count(node_id)
   Signal score = 1.0 if count > 1 else 0.0
   Flagged if count > 1.

4. Energy Anomaly:
   energy_ratio = (node.initial_energy - node.energy) / node.initial_energy
   Signal score = min(1.0, energy_ratio / energy_threshold)
   Flagged if energy_ratio >= energy_threshold.

5. Suspicion Score:
   score = (w_f * f_score) + (w_h * h_score) + (w_c * c_score) + (w_e * e_score)
   A node is marked suspicious if score >= detection_threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from routing.dijkstra import shortest_path

if TYPE_CHECKING:
    from core.network import Network
    from core.node import Node


@dataclass(frozen=True)
class DetectionResult:
    """Immutable data record summarizing the detection findings for a sensor node.

    Attributes
    ----------
    node_id : str
        Identifier of the evaluated sensor node.
    suspicious : bool
        True if the composite suspicion score meets or exceeds the detection threshold.
    suspicion_score : float
        Normalized composite suspicion score between 0.0 and 1.0.
    reasons : list[str]
        List of signal identifiers that breached their individual anomaly thresholds.
    signals : dict[str, float]
        Normalized sub-scores (0.0 to 1.0) for each evaluated metric:
        'forwarding', 'hop_inflation', 'route_cycle', 'energy'.
    details : dict[str, Any]
        Raw metric measurements (e.g. observed hops, cycle counts, energy ratio).
    """

    node_id: str
    suspicious: bool
    suspicion_score: float
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "SUSPICIOUS" if self.suspicious else "NORMAL"
        return (
            f"DetectionResult(node={self.node_id!r}, status={status}, "
            f"score={self.suspicion_score:.3f}, reasons={self.reasons})"
        )


class AttackDetector:
    """Rule-based anomaly detector for Vampire Attacks in a WSN.

    Parameters
    ----------
    forwarding_threshold : int, default 10
        Threshold for forwarded packet count above which forwarding is considered abnormal.
    hop_inflation_threshold : float, default 1.5
        Ratio of observed hops to optimal Dijkstra hops above which route is considered stretched.
    energy_threshold : float, default 0.4
        Fraction of initial battery drained (0.0 to 1.0) above which consumption is anomalous.
    detection_threshold : float, default 0.5
        Composite suspicion score threshold [0.0, 1.0] above which a node is marked suspicious.
    weight_forwarding : float, default 0.25
        Relative weight of forwarding count signal in composite score.
    weight_hop : float, default 0.30
        Relative weight of hop inflation signal in composite score.
    weight_cycle : float, default 0.30
        Relative weight of route cycle signal in composite score.
    weight_energy : float, default 0.15
        Relative weight of energy anomaly signal in composite score.

    Raises
    ------
    ValueError
        If thresholds or weights are negative, or if detection_threshold is out of (0, 1].
    TypeError
        If threshold parameters are of invalid types.
    """

    def __init__(
        self,
        forwarding_threshold: int = 10,
        hop_inflation_threshold: float = 1.5,
        energy_threshold: float = 0.4,
        detection_threshold: float = 0.5,
        weight_forwarding: float = 0.25,
        weight_hop: float = 0.30,
        weight_cycle: float = 0.30,
        weight_energy: float = 0.15,
    ) -> None:
        # Validate thresholds
        if isinstance(forwarding_threshold, bool) or not isinstance(forwarding_threshold, (int, float)):
            raise TypeError("forwarding_threshold must be a positive integer.")
        if forwarding_threshold <= 0:
            raise ValueError(f"forwarding_threshold must be positive, got {forwarding_threshold!r}.")
        self.forwarding_threshold: int = int(forwarding_threshold)

        if isinstance(hop_inflation_threshold, bool) or not isinstance(hop_inflation_threshold, (int, float)):
            raise TypeError("hop_inflation_threshold must be numeric.")
        if hop_inflation_threshold <= 1.0:
            raise ValueError(f"hop_inflation_threshold must be > 1.0, got {hop_inflation_threshold!r}.")
        self.hop_inflation_threshold: float = float(hop_inflation_threshold)

        if isinstance(energy_threshold, bool) or not isinstance(energy_threshold, (int, float)):
            raise TypeError("energy_threshold must be numeric.")
        if not (0.0 < energy_threshold <= 1.0):
            raise ValueError(f"energy_threshold must be in (0.0, 1.0], got {energy_threshold!r}.")
        self.energy_threshold: float = float(energy_threshold)

        if isinstance(detection_threshold, bool) or not isinstance(detection_threshold, (int, float)):
            raise TypeError("detection_threshold must be numeric.")
        if not (0.0 < detection_threshold <= 1.0):
            raise ValueError(f"detection_threshold must be in (0.0, 1.0], got {detection_threshold!r}.")
        self.detection_threshold: float = float(detection_threshold)

        # Validate and normalize weights
        weights = [weight_forwarding, weight_hop, weight_cycle, weight_energy]
        for w in weights:
            if isinstance(w, bool) or not isinstance(w, (int, float)) or w < 0:
                raise ValueError("All signal weights must be non-negative numbers.")
        total_weight = sum(weights)
        if total_weight <= 0:
            raise ValueError("Sum of signal weights must be strictly positive.")

        self.weight_forwarding: float = float(weight_forwarding) / total_weight
        self.weight_hop: float = float(weight_hop) / total_weight
        self.weight_cycle: float = float(weight_cycle) / total_weight
        self.weight_energy: float = float(weight_energy) / total_weight

    # ------------------------------------------------------------------
    # Public Analysis APIs
    # ------------------------------------------------------------------

    def analyze_node(
        self,
        node_id: str,
        network: "Network",
        route: Optional[list[str]] = None,
    ) -> DetectionResult:
        """Analyze a single node for suspicious Vampire Attack behavior.

        Parameters
        ----------
        node_id : str
            ID of the sensor node to inspect.
        network : Network
            The WSN network topology containing nodes and positions.
        route : list[str], optional
            An observed route traversed by a packet. Used to calculate hop inflation
            and cycle repetition signals for this node.

        Returns
        -------
        DetectionResult
            The comprehensive detection assessment for the given node.
        """
        node = network.get_node(node_id) if network else None
        if node is None:
            return DetectionResult(
                node_id=node_id,
                suspicious=False,
                suspicion_score=0.0,
                reasons=[],
                signals={"forwarding": 0.0, "hop_inflation": 0.0, "route_cycle": 0.0, "energy": 0.0},
                details={"error": "Node not found in network"},
            )

        # 1. Forwarding Signal
        f_score, f_flag, f_details = self._evaluate_forwarding(node)

        # 2. Hop Inflation Signal
        h_score, h_flag, h_details = self._evaluate_hop_inflation(node_id, network, route)

        # 3. Route Cycle Signal
        c_score, c_flag, c_details = self._evaluate_cycle(node_id, route)

        # 4. Energy Signal
        e_score, e_flag, e_details = self._evaluate_energy(node)

        # Weighted composite score: if route is not provided, evaluate over telemetry signals
        if route is not None and len(route) >= 2:
            composite_score = (
                self.weight_forwarding * f_score
                + self.weight_hop * h_score
                + self.weight_cycle * c_score
                + self.weight_energy * e_score
            )
        else:
            active_weight = self.weight_forwarding + self.weight_energy
            if active_weight > 0:
                composite_score = (
                    self.weight_forwarding * f_score + self.weight_energy * e_score
                ) / active_weight
            else:
                composite_score = 0.0

        # Normalize strictly to [0.0, 1.0]
        composite_score = max(0.0, min(1.0, round(composite_score, 4)))

        # Compile reasons
        reasons: list[str] = []
        if f_flag:
            reasons.append("abnormal_forwarding")
        if h_flag:
            reasons.append("hop_inflation")
        if c_flag:
            reasons.append("route_cycle")
        if e_flag:
            reasons.append("abnormal_energy")

        suspicious = composite_score >= self.detection_threshold

        signals = {
            "forwarding": f_score,
            "hop_inflation": h_score,
            "route_cycle": c_score,
            "energy": e_score,
        }
        details = {
            **f_details,
            **h_details,
            **c_details,
            **e_details,
        }

        return DetectionResult(
            node_id=node_id,
            suspicious=suspicious,
            suspicion_score=composite_score,
            reasons=reasons,
            signals=signals,
            details=details,
        )

    def detect(
        self,
        network: "Network",
        routes: Optional[list[list[str]]] = None,
    ) -> list[DetectionResult]:
        """Inspect all nodes in the network and return ranked detection results.

        Parameters
        ----------
        network : Network
            The WSN network topology.
        routes : list[list[str]], optional
            List of observed packet routes to evaluate. If multiple routes are provided,
            each node is evaluated against the route in which it exhibited highest suspicion.

        Returns
        -------
        list[DetectionResult]
            List of detection results for all nodes in the network, sorted by
            suspicion_score in descending order.
        """
        if not network or not network.nodes:
            return []

        results: list[DetectionResult] = []
        node_ids = list(network.nodes.keys())

        if not routes:
            for n_id in node_ids:
                results.append(self.analyze_node(n_id, network, route=None))
        else:
            # For each node, find the route that yields the highest suspicion score
            for n_id in node_ids:
                best_result: Optional[DetectionResult] = None
                for r in routes:
                    res = self.analyze_node(n_id, network, route=r)
                    if best_result is None or res.suspicion_score > best_result.suspicion_score:
                        best_result = res
                if best_result is not None:
                    results.append(best_result)

        # Sort descending by suspicion score
        results.sort(key=lambda r: r.suspicion_score, reverse=True)
        return results

    def detect_from_route(
        self,
        route: list[str],
        network: "Network",
    ) -> list[DetectionResult]:
        """Inspect all nodes present in a specific route.

        Parameters
        ----------
        route : list[str]
            Ordered list of node IDs visited by a packet.
        network : Network
            The WSN network topology.

        Returns
        -------
        list[DetectionResult]
            Detection results for nodes appearing in the route, sorted by suspicion score.
        """
        if not route or not network:
            return []

        unique_nodes = list(dict.fromkeys(route))
        results = [self.analyze_node(n_id, network, route=route) for n_id in unique_nodes]
        results.sort(key=lambda r: r.suspicion_score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # Individual Signal Evaluators
    # ------------------------------------------------------------------

    def _evaluate_forwarding(self, node: "Node") -> tuple[float, bool, dict[str, Any]]:
        """Evaluate packet forwarding activity for a node."""
        f_count = node.forwarded
        f_ratio = f_count / self.forwarding_threshold
        # Normalize score: reaches 1.0 when at or above twice the threshold
        f_score = min(1.0, f_ratio / 2.0) if f_count < self.forwarding_threshold else min(1.0, 0.5 + (f_ratio - 1.0) * 0.5)
        f_flag = f_count >= self.forwarding_threshold
        return f_score, f_flag, {"forwarded_count": f_count, "forwarding_threshold": self.forwarding_threshold}

    def _evaluate_hop_inflation(
        self,
        node_id: str,
        network: "Network",
        route: Optional[list[str]],
    ) -> tuple[float, bool, dict[str, Any]]:
        """Evaluate hop inflation of an observed route with respect to optimal Dijkstra route."""
        if not route or len(route) < 2 or node_id not in route:
            return 0.0, False, {"hop_inflation_ratio": 1.0, "observed_hops": 0, "optimal_hops": 0}

        # Do not accuse the ultimate sink/destination for path extension initiated by relays
        if node_id == route[-1]:
            return 0.0, False, {"hop_inflation_ratio": 1.0, "observed_hops": len(route) - 1, "optimal_hops": 0}

        source = route[0]
        destination = route[-1]

        # Calculate optimal shortest path hops using existing Dijkstra implementation
        opt_path = shortest_path(network, source, destination)
        if opt_path is None or len(opt_path) < 2:
            return 0.0, False, {"hop_inflation_ratio": 1.0, "observed_hops": len(route) - 1, "optimal_hops": 0}

        opt_hops = len(opt_path) - 1
        obs_hops = len(route) - 1

        if obs_hops <= opt_hops:
            return 0.0, False, {"hop_inflation_ratio": 1.0, "observed_hops": obs_hops, "optimal_hops": opt_hops}

        inflation_ratio = obs_hops / opt_hops
        # Score scales from 0.0 at 1.0x to 1.0 at >= 2x the inflation threshold
        score = min(1.0, (inflation_ratio - 1.0) / (self.hop_inflation_threshold - 1.0))
        flag = inflation_ratio >= self.hop_inflation_threshold

        return score, flag, {
            "hop_inflation_ratio": round(inflation_ratio, 3),
            "observed_hops": obs_hops,
            "optimal_hops": opt_hops,
        }

    def _evaluate_cycle(
        self,
        node_id: str,
        route: Optional[list[str]],
    ) -> tuple[float, bool, dict[str, Any]]:
        """Evaluate whether a node is involved in a routing cycle/loop."""
        if not route or len(route) < 2:
            return 0.0, False, {"cycle_count": 0, "has_cycle": False}

        count = route.count(node_id)
        has_cycle = count > 1

        if not has_cycle:
            return 0.0, False, {"cycle_count": 1, "has_cycle": False}

        # Node appears multiple times: score scales with repetition frequency
        score = min(1.0, 0.6 + (count - 2) * 0.2) if count > 1 else 0.0
        return score, True, {"cycle_count": count, "has_cycle": True}

    def _evaluate_energy(self, node: "Node") -> tuple[float, bool, dict[str, Any]]:
        """Evaluate battery depletion ratio of a node."""
        if node.initial_energy <= 0:
            return 0.0, False, {"energy_depletion_ratio": 0.0}

        consumed = node.initial_energy - node.energy
        depletion_ratio = consumed / node.initial_energy

        score = min(1.0, depletion_ratio / self.energy_threshold)
        flag = depletion_ratio >= self.energy_threshold

        return score, flag, {
            "energy_depletion_ratio": round(depletion_ratio, 3),
            "energy_consumed": round(consumed, 6),
        }

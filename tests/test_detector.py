"""
tests/test_detector.py
======================
Unit tests for Vampire Attack Detection layer (Phase 3).
"""

import pytest

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from security.detector import AttackDetector, DetectionResult


@pytest.fixture
def sample_network():
    """A standard network topology with multiple routes."""
    net = Network(communication_range=30.0)
    nodes = [
        Node("N1", 0, 0, 10.0),
        Node("N2", 20, 0, 10.0),
        Node("N3", 40, 0, 10.0),
        Node("SINK", 60, 0, 10.0),
        # Side path for detour / stretch
        Node("N4", 20, 20, 10.0),
        Node("N5", 40, 20, 10.0),
    ]
    for n in nodes:
        net.add_node(n)
    net.set_sink("SINK")
    net.update_neighbors()
    return net


# ======================================================================
# BASIC TESTS
# ======================================================================

class TestDetectorInitialization:
    """Tests for AttackDetector creation and configuration validation."""

    def test_instantiation_defaults(self):
        detector = AttackDetector()
        assert detector.forwarding_threshold == 10
        assert detector.hop_inflation_threshold == 1.5
        assert detector.energy_threshold == 0.4
        assert detector.detection_threshold == 0.5
        assert 0.99 <= (detector.weight_forwarding + detector.weight_hop + detector.weight_cycle + detector.weight_energy) <= 1.01

    def test_custom_thresholds(self):
        detector = AttackDetector(
            forwarding_threshold=5,
            hop_inflation_threshold=1.2,
            energy_threshold=0.3,
            detection_threshold=0.6,
        )
        assert detector.forwarding_threshold == 5
        assert detector.hop_inflation_threshold == 1.2
        assert detector.energy_threshold == 0.3
        assert detector.detection_threshold == 0.6

    @pytest.mark.parametrize("invalid_val", [0, -1, -5.0])
    def test_invalid_forwarding_threshold(self, invalid_val):
        with pytest.raises(ValueError):
            AttackDetector(forwarding_threshold=invalid_val)

    @pytest.mark.parametrize("invalid_hop", [1.0, 0.5, -1.0])
    def test_invalid_hop_inflation_threshold(self, invalid_hop):
        with pytest.raises(ValueError):
            AttackDetector(hop_inflation_threshold=invalid_hop)

    @pytest.mark.parametrize("invalid_energy", [0.0, -0.1, 1.5])
    def test_invalid_energy_threshold(self, invalid_energy):
        with pytest.raises(ValueError):
            AttackDetector(energy_threshold=invalid_energy)

    @pytest.mark.parametrize("invalid_detection", [0.0, -0.5, 1.5])
    def test_invalid_detection_threshold(self, invalid_detection):
        with pytest.raises(ValueError):
            AttackDetector(detection_threshold=invalid_detection)

    def test_type_error_for_non_numeric(self):
        with pytest.raises(TypeError):
            AttackDetector(forwarding_threshold="10")
        with pytest.raises(TypeError):
            AttackDetector(hop_inflation_threshold="1.5")


# ======================================================================
# FORWARDING SIGNAL TESTS
# ======================================================================

class TestForwardingSignal:
    """Tests for detecting abnormal packet forwarding counts."""

    def test_normal_forwarding_not_suspicious(self, sample_network):
        detector = AttackDetector(forwarding_threshold=10)
        node = sample_network.get_node("N2")
        node.forwarded = 2  # Low, normal forwarding

        result = detector.analyze_node("N2", sample_network)
        assert "abnormal_forwarding" not in result.reasons
        assert result.signals["forwarding"] < 0.5

    def test_excessive_forwarding_increases_suspicion(self, sample_network):
        detector = AttackDetector(forwarding_threshold=10)
        node = sample_network.get_node("N2")
        node.forwarded = 25  # High forwarding count

        result = detector.analyze_node("N2", sample_network)
        assert "abnormal_forwarding" in result.reasons
        assert result.signals["forwarding"] >= 0.5
        assert result.suspicion_score > 0.0

    def test_zero_forwarding_zero_score(self, sample_network):
        detector = AttackDetector()
        node = sample_network.get_node("N1")
        node.forwarded = 0

        result = detector.analyze_node("N1", sample_network)
        assert result.signals["forwarding"] == 0.0


# ======================================================================
# HOP INFLATION TESTS
# ======================================================================

class TestHopInflationSignal:
    """Tests for detecting stretched routes."""

    def test_normal_shortest_route_not_inflated(self, sample_network):
        detector = AttackDetector(hop_inflation_threshold=1.5)
        # Normal shortest path: N1 -> N2 -> N3 -> SINK (3 hops)
        route = ["N1", "N2", "N3", "SINK"]

        result = detector.analyze_node("N2", sample_network, route=route)
        assert "hop_inflation" not in result.reasons
        assert result.signals["hop_inflation"] == 0.0

    def test_stretched_route_triggers_hop_inflation(self, sample_network):
        detector = AttackDetector(hop_inflation_threshold=1.5)
        # Detour route: N1 -> N2 -> N4 -> N5 -> N3 -> SINK (5 hops vs 3 shortest hops = 1.67x)
        stretched_route = ["N1", "N2", "N4", "N5", "N3", "SINK"]

        result = detector.analyze_node("N2", sample_network, route=stretched_route)
        assert "hop_inflation" in result.reasons
        assert result.signals["hop_inflation"] >= 0.5

    def test_destination_node_not_accused_of_hop_inflation(self, sample_network):
        detector = AttackDetector(hop_inflation_threshold=1.5)
        stretched_route = ["N1", "N2", "N4", "N5", "N3", "SINK"]

        # Final sink/destination node should not be blamed for route inflation
        result = detector.analyze_node("SINK", sample_network, route=stretched_route)
        assert "hop_inflation" not in result.reasons


# ======================================================================
# ROUTE CYCLE TESTS
# ======================================================================

class TestRouteCycleSignal:
    """Tests for detecting routing cycles and repeated nodes."""

    def test_unique_route_has_no_cycle(self, sample_network):
        detector = AttackDetector()
        route = ["N1", "N2", "N3", "SINK"]

        result = detector.analyze_node("N2", sample_network, route=route)
        assert "route_cycle" not in result.reasons
        assert result.signals["route_cycle"] == 0.0

    def test_repeated_node_triggers_cycle_detection(self, sample_network):
        detector = AttackDetector()
        # Route with cycle: N1 -> N2 -> N3 -> N2 -> N3 -> SINK
        cycle_route = ["N1", "N2", "N3", "N2", "N3", "SINK"]

        result = detector.analyze_node("N2", sample_network, route=cycle_route)
        assert "route_cycle" in result.reasons
        assert result.signals["route_cycle"] > 0.0
        assert result.details["has_cycle"] is True
        assert result.details["cycle_count"] == 2

    def test_node_outside_cycle_has_zero_cycle_score(self, sample_network):
        detector = AttackDetector()
        cycle_route = ["N1", "N2", "N3", "N2", "N3", "SINK"]

        # N1 appears only once, not in the cycle
        result = detector.analyze_node("N1", sample_network, route=cycle_route)
        assert "route_cycle" not in result.reasons
        assert result.signals["route_cycle"] == 0.0


# ======================================================================
# ENERGY ANOMALY TESTS
# ======================================================================

class TestEnergySignal:
    """Tests for detecting abnormal energy drainage."""

    def test_normal_energy_consumption_not_suspicious(self, sample_network):
        detector = AttackDetector(energy_threshold=0.4)
        node = sample_network.get_node("N2")
        # Drain 5% battery
        node.consume_energy(node.initial_energy * 0.05)

        result = detector.analyze_node("N2", sample_network)
        assert "abnormal_energy" not in result.reasons
        assert result.signals["energy"] < 0.5

    def test_excessive_energy_drain_triggers_anomaly(self, sample_network):
        detector = AttackDetector(energy_threshold=0.4)
        node = sample_network.get_node("N2")
        # Drain 60% battery
        node.consume_energy(node.initial_energy * 0.60)

        result = detector.analyze_node("N2", sample_network)
        assert "abnormal_energy" in result.reasons
        assert result.signals["energy"] >= 1.0


# ======================================================================
# COMPOSITE SCORING & INTEGRATION
# ======================================================================

class TestCompositeScoring:
    """Tests for multi-signal fusion, score bounds, and thresholding."""

    def test_multiple_anomalies_produce_suspicious_verdict(self, sample_network):
        detector = AttackDetector(detection_threshold=0.5)
        node = sample_network.get_node("N2")
        node.forwarded = 20                           # Signal 1: Forwarding
        node.consume_energy(node.initial_energy * 0.5) # Signal 4: Energy

        # Route with cycle (Signal 3) and hop inflation (Signal 2)
        route = ["N1", "N2", "N4", "N5", "N2", "N3", "SINK"]

        result = detector.analyze_node("N2", sample_network, route=route)
        assert result.suspicious is True
        assert result.suspicion_score >= 0.5
        assert len(result.reasons) >= 2

    def test_normal_node_remains_below_threshold(self, sample_network):
        detector = AttackDetector(detection_threshold=0.5)
        node = sample_network.get_node("N1")
        node.forwarded = 0
        normal_route = ["N1", "N2", "N3", "SINK"]

        result = detector.analyze_node("N1", sample_network, route=normal_route)
        assert result.suspicious is False
        assert result.suspicion_score < 0.2
        assert len(result.reasons) == 0

    def test_score_normalized_between_0_and_1(self, sample_network):
        detector = AttackDetector()
        node = sample_network.get_node("N2")
        node.forwarded = 99999
        node.consume_energy(node.initial_energy)
        extreme_route = ["N1"] + ["N2", "N3"] * 50 + ["SINK"]

        result = detector.analyze_node("N2", sample_network, route=extreme_route)
        assert 0.0 <= result.suspicion_score <= 1.0


# ======================================================================
# ATTACK-SPECIFIC BEHAVIORAL VALIDATION
# ======================================================================

class TestAttackDetectionIntegration:
    """Validates that detector flags behaviors generated by StretchAttack and CarouselAttack."""

    def test_stretch_attack_triggers_hop_inflation(self, sample_network):
        attack = StretchAttack(attacker_node_id="N2")
        normal_route = ["N1", "N2", "N3", "SINK"]
        # Generate stretched route
        stretched_route = attack.apply(normal_route, network=sample_network)
        assert len(stretched_route) > len(normal_route)

        detector = AttackDetector(hop_inflation_threshold=1.3)
        result = detector.analyze_node("N2", sample_network, route=stretched_route)
        assert "hop_inflation" in result.reasons

    def test_carousel_attack_triggers_cycle_detection(self, sample_network):
        attack = CarouselAttack(attacker_node_id="N2")
        normal_route = ["N1", "N2", "N3", "SINK"]
        # Generate carousel route
        carousel_route = attack.apply(normal_route, network=sample_network, ttl=15)
        assert carousel_route.count("N2") > 1

        detector = AttackDetector()
        result = detector.analyze_node("N2", sample_network, route=carousel_route)
        assert "route_cycle" in result.reasons
        assert result.details["has_cycle"] is True


# ======================================================================
# BATCH DETECTION & EDGE CASES
# ======================================================================

class TestBatchDetectionAndEdgeCases:
    """Tests for detect(), detect_from_route(), and edge boundary cases."""

    def test_batch_detect_ranks_suspicious_nodes_first(self, sample_network):
        detector = AttackDetector()
        # Make N2 heavily anomalous
        n2 = sample_network.get_node("N2")
        n2.forwarded = 30
        n2.consume_energy(n2.initial_energy * 0.7)

        results = detector.detect(sample_network)
        assert len(results) == len(sample_network.nodes)
        # N2 should be ranked top
        assert results[0].node_id == "N2"
        assert results[0].suspicious is True

    def test_detect_from_route(self, sample_network):
        detector = AttackDetector()
        route = ["N1", "N2", "N3", "SINK"]
        results = detector.detect_from_route(route, sample_network)
        assert len(results) == 4

    def test_empty_route_safe(self, sample_network):
        detector = AttackDetector()
        result = detector.analyze_node("N2", sample_network, route=[])
        assert result.signals["hop_inflation"] == 0.0
        assert result.signals["route_cycle"] == 0.0

    def test_single_node_route_safe(self, sample_network):
        detector = AttackDetector()
        result = detector.analyze_node("N2", sample_network, route=["N2"])
        assert result.signals["hop_inflation"] == 0.0
        assert result.signals["route_cycle"] == 0.0

    def test_source_equals_destination_safe(self, sample_network):
        detector = AttackDetector()
        result = detector.analyze_node("N1", sample_network, route=["N1"])
        assert not result.suspicious

    def test_missing_node_returns_safe_result(self, sample_network):
        detector = AttackDetector()
        result = detector.analyze_node("GHOST_NODE", sample_network)
        assert result.node_id == "GHOST_NODE"
        assert not result.suspicious
        assert result.suspicion_score == 0.0

    def test_missing_network_handled_safely(self):
        detector = AttackDetector()
        result = detector.analyze_node("N1", network=None)
        assert not result.suspicious

    def test_empty_network_returns_empty_list(self):
        empty_net = Network(communication_range=10.0)
        detector = AttackDetector()
        assert detector.detect(empty_net) == []
        assert detector.detect_from_route([], empty_net) == []

    def test_representation(self):
        result = DetectionResult(
            node_id="N7",
            suspicious=True,
            suspicion_score=0.75,
            reasons=["hop_inflation"],
        )
        assert "N7" in repr(result)
        assert "SUSPICIOUS" in repr(result)

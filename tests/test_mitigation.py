"""
tests/test_mitigation.py
========================
Unit tests for Vampire Attack Mitigation and Rerouting layer (Phase 4).
"""

import pytest

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from routing.dijkstra import shortest_path
from routing.router import Router
from energy.energy_model import EnergyModel
from security.detector import AttackDetector, DetectionResult
from security.mitigation import MitigationManager, MitigationResult


@pytest.fixture
def diamond_network():
    """Network with two disjoint paths from N1 to SINK.

    Top path:    N1 (0,0) --- N2 (25,10) --- N3 (50,10) --- SINK (75,0)
    Bottom path: N1 (0,0) --- N4 (25,-10) --- N5 (50,-10) --- SINK (75,0)
    """
    net = Network(communication_range=35.0)
    nodes = [
        Node("N1", 0, 0, 10.0),
        Node("N2", 25, 10, 10.0),
        Node("N3", 50, 10, 10.0),
        Node("N4", 25, -10, 10.0),
        Node("N5", 50, -10, 10.0),
        Node("SINK", 75, 0, 10.0),
    ]
    for n in nodes:
        net.add_node(n)
    net.set_sink("SINK")
    net.update_neighbors()
    return net


# ======================================================================
# BASIC ISOLATION MANAGEMENT TESTS (Step 15)
# ======================================================================

class TestIsolationManagement:
    """Tests for isolating, querying, and clearing node blacklists."""

    def test_manager_instantiation_defaults(self):
        manager = MitigationManager()
        assert len(manager.get_isolated_nodes()) == 0

    def test_manager_instantiation_with_initial_nodes(self):
        manager = MitigationManager(initial_isolated=["N2", "N7"])
        assert manager.is_isolated("N2")
        assert manager.is_isolated("N7")
        assert not manager.is_isolated("N1")
        assert len(manager.get_isolated_nodes()) == 2

    def test_isolate_node_marks_isolated(self):
        manager = MitigationManager()
        res = manager.isolate_node("N2", reasons=["hop_inflation"], suspicion_score=0.85)

        assert manager.is_isolated("N2")
        assert "N2" in manager.get_isolated_nodes()
        assert isinstance(res, MitigationResult)
        assert res.node_id == "N2"
        assert res.isolated is True
        assert res.reasons == ["hop_inflation"]
        assert res.suspicion_score == 0.85

    def test_isolate_node_idempotent(self):
        manager = MitigationManager()
        manager.isolate_node("N2")
        manager.isolate_node("N2")
        manager.isolate_node("N2")

        assert manager.get_isolated_nodes() == {"N2"}

    def test_clear_isolation_removes_node(self):
        manager = MitigationManager()
        manager.isolate_node("N2")
        assert manager.is_isolated("N2")

        cleared = manager.clear_isolation("N2")
        assert cleared is True
        assert not manager.is_isolated("N2")
        assert "N2" not in manager.get_isolated_nodes()

    def test_clear_non_isolated_node_safe(self):
        manager = MitigationManager()
        cleared = manager.clear_isolation("NON_EXISTENT")
        assert cleared is False

    def test_clear_all_removes_all_nodes(self):
        manager = MitigationManager(initial_isolated=["N1", "N2", "N3"])
        assert len(manager.get_isolated_nodes()) == 3

        manager.clear_all()
        assert len(manager.get_isolated_nodes()) == 0

    @pytest.mark.parametrize("invalid_id", ["", "   ", None, 123, []])
    def test_invalid_node_id_rejected(self, invalid_id):
        manager = MitigationManager()
        if isinstance(invalid_id, str):
            with pytest.raises(ValueError):
                manager.isolate_node(invalid_id)
        else:
            with pytest.raises(TypeError):
                manager.isolate_node(invalid_id)


# ======================================================================
# DETECTION RESULT INTEGRATION TESTS (Step 16)
# ======================================================================

class TestDetectionIntegration:
    """Tests for applying Phase 3 DetectionResults to the mitigation manager."""

    def test_apply_detection_suspicious_true_isolates(self):
        manager = MitigationManager()
        det_result = DetectionResult(
            node_id="N2",
            suspicious=True,
            suspicion_score=0.88,
            reasons=["hop_inflation", "route_cycle"],
            details={"observed_hops": 6},
        )

        mit_result = manager.apply_detection(det_result)
        assert mit_result is not None
        assert mit_result.isolated is True
        assert manager.is_isolated("N2")
        assert mit_result.reasons == ["hop_inflation", "route_cycle"]
        assert mit_result.suspicion_score == 0.88
        assert mit_result.details["observed_hops"] == 6

    def test_apply_detection_suspicious_false_does_not_isolate(self):
        manager = MitigationManager()
        det_result = DetectionResult(
            node_id="N1",
            suspicious=False,
            suspicion_score=0.15,
            reasons=[],
        )

        mit_result = manager.apply_detection(det_result)
        assert mit_result is None
        assert not manager.is_isolated("N1")
        assert len(manager.get_isolated_nodes()) == 0

    def test_apply_detections_multiple_results(self):
        manager = MitigationManager()
        results = [
            DetectionResult(node_id="N2", suspicious=True, suspicion_score=0.8, reasons=["route_cycle"]),
            DetectionResult(node_id="N5", suspicious=False, suspicion_score=0.1, reasons=[]),
            DetectionResult(node_id="N7", suspicious=True, suspicion_score=0.9, reasons=["abnormal_forwarding"]),
        ]

        mitigations = manager.apply_detections(results)
        assert len(mitigations) == 2
        assert manager.get_isolated_nodes() == {"N2", "N7"}
        assert not manager.is_isolated("N5")

    def test_evidence_preservation_in_records(self):
        manager = MitigationManager()
        det_result = DetectionResult(
            node_id="N2",
            suspicious=True,
            suspicion_score=0.75,
            reasons=["hop_inflation"],
            details={"detour_hops": 4},
        )
        manager.apply_detection(det_result)

        record = manager.get_isolation_record("N2")
        assert record is not None
        assert record.node_id == "N2"
        assert record.suspicion_score == 0.75
        assert record.reasons == ["hop_inflation"]
        assert record.details["detour_hops"] == 4


# ======================================================================
# ROUTING EXCLUSION & RECALCULATION TESTS (Steps 17, 18, 19)
# ======================================================================

class TestRoutingExclusionAndRecalculation:
    """Tests for computing alternate paths around blacklisted nodes."""

    def test_normal_route_before_isolation(self, diamond_network):
        norm_path = shortest_path(diamond_network, "N1", "SINK")
        assert norm_path is not None
        assert norm_path[0] == "N1"
        assert norm_path[-1] == "SINK"

    def test_single_node_isolation_forces_alternate_route(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N2")

        new_route = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert new_route is not None
        assert "N2" not in new_route
        assert new_route == ["N1", "N4", "N5", "SINK"]

    def test_multiple_node_isolation_switches_route(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N2")
        manager.isolate_node("N3")

        new_route = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert new_route is not None
        assert "N2" not in new_route
        assert "N3" not in new_route
        assert new_route == ["N1", "N4", "N5", "SINK"]

    def test_all_paths_isolated_returns_none(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N2")
        manager.isolate_node("N4")

        new_route = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert new_route is None

    def test_source_isolated_returns_none(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N1")

        assert manager.recalculate_route(diamond_network, "N1", "SINK") is None

    def test_destination_isolated_returns_none(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("SINK")

        assert manager.recalculate_route(diamond_network, "N1", "SINK") is None

    def test_source_equals_destination(self, diamond_network):
        manager = MitigationManager()
        route = manager.recalculate_route(diamond_network, "N1", "N1")
        assert route == ["N1"]

    def test_source_equals_destination_isolated_returns_none(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N1")
        assert manager.recalculate_route(diamond_network, "N1", "N1") is None

    def test_network_nodes_and_batteries_not_modified(self, diamond_network):
        manager = MitigationManager()
        n2 = diamond_network.get_node("N2")
        initial_energy = n2.energy
        initial_alive = n2.alive
        node_count_before = len(diamond_network.nodes)

        manager.isolate_node("N2")
        manager.recalculate_route(diamond_network, "N1", "SINK")

        assert "N2" in diamond_network.nodes
        assert len(diamond_network.nodes) == node_count_before
        assert n2.energy == initial_energy
        assert n2.alive == initial_alive

    def test_recovery_allows_routing_through_node_again(self, diamond_network):
        manager = MitigationManager()
        manager.isolate_node("N4")
        manager.isolate_node("N5")

        top_route = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert top_route == ["N1", "N2", "N3", "SINK"]

        manager.isolate_node("N2")
        assert manager.recalculate_route(diamond_network, "N1", "SINK") is None

        manager.clear_isolation("N4")
        manager.clear_isolation("N5")

        recovered_route = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert recovered_route == ["N1", "N4", "N5", "SINK"]


# ======================================================================
# ROUTER INTEGRATION & CACHE UPDATE TESTS
# ======================================================================

class TestRouterIntegration:
    """Tests verifying interaction with Router instance and routing table."""

    def test_recalculate_route_with_router_instance(self, diamond_network):
        em = EnergyModel()
        router = Router(diamond_network, em)
        manager = MitigationManager()
        manager.isolate_node("N2")

        new_route = manager.recalculate_route(router, "N1", "SINK")
        assert new_route == ["N1", "N4", "N5", "SINK"]
        assert router.routing_table.get_next_hop("SINK") == "N4"


# ======================================================================
# FULL END-TO-END FLOW (Step 20)
# ======================================================================

class TestFullMitigationFlow:
    """End-to-end integration: Attack -> Detection -> Mitigation -> Rerouting."""

    def test_stretch_attack_detection_and_mitigation_workflow(self, diamond_network):
        normal_route = ["N1", "N2", "N3", "SINK"]

        attack = StretchAttack(attacker_node_id="N2")
        stretched_route = attack.apply(normal_route, network=diamond_network)
        assert len(stretched_route) > len(normal_route)

        detector = AttackDetector(hop_inflation_threshold=1.3, detection_threshold=0.3)
        det_result = detector.analyze_node("N2", diamond_network, route=stretched_route)
        assert det_result.suspicious is True
        assert "hop_inflation" in det_result.reasons

        manager = MitigationManager()
        mit_res = manager.apply_detection(det_result)
        assert mit_res is not None
        assert manager.is_isolated("N2")

        rerouted = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert rerouted is not None
        assert "N2" not in rerouted
        assert rerouted == ["N1", "N4", "N5", "SINK"]

    def test_carousel_attack_detection_and_mitigation_workflow(self, diamond_network):
        normal_route = ["N1", "N2", "N3", "SINK"]

        attack = CarouselAttack(attacker_node_id="N2")
        carousel_route = attack.apply(normal_route, network=diamond_network, ttl=10)
        assert carousel_route.count("N2") > 1

        detector = AttackDetector()
        det_result = detector.analyze_node("N2", diamond_network, route=carousel_route)
        assert det_result.suspicious is True
        assert "route_cycle" in det_result.reasons

        manager = MitigationManager()
        manager.apply_detection(det_result)
        assert manager.is_isolated("N2")

        rerouted = manager.recalculate_route(diamond_network, "N1", "SINK")
        assert rerouted is not None
        assert "N2" not in rerouted
        assert rerouted == ["N1", "N4", "N5", "SINK"]

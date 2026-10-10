"""
tests/test_stretch_attack.py
============================
Unit tests for the Stretch Vampire Attack (Phase 2).
"""

import pytest

from attacks.base import AttackIntensity, AttackType
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from core.packet import Packet
from energy.energy_model import EnergyModel
from routing.router import Router
from simulator import Simulator


@pytest.fixture
def sample_network():
    """A network topology with multiple alternative paths from N2 to SINK.

    Topology:
        N1 (0,0)  --- N2 (20,0) --- SINK (60,0)   [Shortest: N1 -> N2 -> SINK]
                       |              ^
                       |              |
                      N3 (20,20) --- N4 (60,20)   [Detour: N2 -> N3 -> N4 -> SINK]
                       |              ^
                       |              |
                      N5 (20,40) --- N6 (60,40)   [Longest Detour: N2 -> N3 -> N5 -> N6 -> N4 -> SINK]
    """
    net = Network(communication_range=25.0)
    nodes = [
        Node("N1", 0, 0, 10.0),
        Node("N2", 20, 0, 10.0),      # Attacker
        Node("SINK", 40, 0, 10.0),
        Node("N3", 20, 20, 10.0),
        Node("N4", 40, 20, 10.0),
        Node("N5", 20, 40, 10.0),
        Node("N6", 40, 40, 10.0),
    ]
    for n in nodes:
        net.add_node(n)
    net.set_sink("SINK")
    net.update_neighbors()
    return net


@pytest.fixture
def sample_simulator_network():
    """The topology used by the simulator UI, with its N5 detour."""
    net = Network(communication_range=35.0)
    nodes = [
        Node("N1", 0.0, 0.0, 100.0),
        Node("N2", 25.0, 0.0, 100.0),
        Node("N3", 50.0, 0.0, 100.0),
        Node("N4", 75.0, 0.0, 100.0),
        Node("N5", 48.0, 24.0, 100.0),
        Node("N6", 72.0, 22.0, 100.0),
        Node("SINK", 100.0, 0.0, 500.0),
    ]
    for node in nodes:
        net.add_node(node)
    net.set_sink("SINK")
    net.update_neighbors()
    return net


class TestStretchAttackBasics:
    """Tests for initialization, types, and properties."""

    def test_instantiation_and_properties(self):
        attack = StretchAttack(
            attacker_node_id="N2",
            intensity=AttackIntensity.HIGH,
            start_time=10.0,
            duration=30.0,
        )
        assert attack.attacker_node_id == "N2"
        assert attack.attack_type == AttackType.STRETCH
        assert attack.intensity == AttackIntensity.HIGH
        assert attack.start_time == 10.0
        assert attack.duration == 30.0
        assert attack.end_time == 40.0

    def test_default_values(self):
        attack = StretchAttack(attacker_node_id="N2")
        assert attack.attacker_node_id == "N2"
        assert attack.attack_type == AttackType.STRETCH
        assert attack.intensity == AttackIntensity.MEDIUM
        assert attack.start_time == 0.0
        assert attack.duration == 100.0


class TestStretchAttackLifecycle:
    """Tests that attack respects its time window."""

    def test_inactive_before_start_time(self, sample_network):
        attack = StretchAttack("N2", start_time=15.0, duration=20.0)
        assert not attack.is_active(5.0)

        route = ["N1", "N2", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=5.0)
        assert manipulated == ["N1", "N2", "SINK"]

    def test_active_during_window(self, sample_network):
        attack = StretchAttack("N2", start_time=10.0, duration=20.0)
        assert attack.is_active(15.0)

        route = ["N1", "N2", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=15.0)
        assert len(manipulated) > len(route)

    def test_inactive_after_duration(self, sample_network):
        attack = StretchAttack("N2", start_time=10.0, duration=20.0)
        assert not attack.is_active(35.0)

        route = ["N1", "N2", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=35.0)
        assert manipulated == ["N1", "N2", "SINK"]

    def test_zero_duration_always_inactive(self, sample_network):
        attack = StretchAttack("N2", start_time=10.0, duration=0.0)
        assert not attack.is_active(10.0)
        route = ["N1", "N2", "SINK"]
        assert attack.apply(route, network=sample_network, current_time=10.0) == route


class TestStretchRouteManipulation:
    """Tests for route stretching logic and node validity."""

    def test_attacker_not_on_shortest_route_is_included(self, sample_simulator_network):
        normal_route = ["N1", "N2", "N3", "N4", "SINK"]
        attack = StretchAttack("N5")

        stretched = attack.apply(
            normal_route,
            network=sample_simulator_network,
            ttl=50,
        )

        assert stretched == ["N1", "N2", "N5", "N3", "N6", "N4", "SINK"]
        assert len(stretched) == len(set(stretched))
        for sender, receiver in zip(stretched, stretched[1:]):
            neighbor_ids = {
                neighbor.id for neighbor in sample_simulator_network.get_neighbors(sender)
            }
            assert receiver in neighbor_ids

    def test_simulator_forwards_and_reports_stretched_route(
        self,
        sample_simulator_network,
    ):
        energy_model = EnergyModel()
        router = Router(sample_simulator_network, energy_model)
        simulator = Simulator(
            sample_simulator_network,
            router,
            energy_model,
            StretchAttack("N5"),
        )
        progress: list[dict[str, object]] = []

        packet = simulator.run_packet(
            "N1",
            "SINK",
            ttl=50,
            on_progress=progress.append,
        )

        expected_route = ["N1", "N2", "N5", "N3", "N6", "N4", "SINK"]
        assert packet.status.name == "DELIVERED"
        assert packet.route == expected_route
        assert progress[-1]["planned_route"] == expected_route
        assert progress[-1]["route"] == expected_route

    def test_route_length_increases(self, sample_network):
        attack = StretchAttack("N2", intensity=AttackIntensity.HIGH, start_time=0, duration=50)
        normal_route = ["N1", "N2", "SINK"]

        stretched = attack.apply(normal_route, network=sample_network, current_time=1.0)
        assert len(stretched) > len(normal_route)

    def test_source_and_destination_preserved(self, sample_network):
        attack = StretchAttack("N2", intensity=AttackIntensity.MEDIUM, start_time=0, duration=50)
        normal_route = ["N1", "N2", "SINK"]

        stretched = attack.apply(normal_route, network=sample_network, current_time=1.0)
        assert stretched[0] == normal_route[0]
        assert stretched[-1] == normal_route[-1]

    def test_attacker_represented_in_route(self, sample_network):
        attack = StretchAttack("N2", intensity=AttackIntensity.LOW, start_time=0, duration=50)
        normal_route = ["N1", "N2", "SINK"]

        stretched = attack.apply(normal_route, network=sample_network, current_time=1.0)
        assert "N2" in stretched

    def test_all_consecutive_hops_are_valid_neighbors(self, sample_network):
        attack = StretchAttack("N2", intensity=AttackIntensity.HIGH, start_time=0, duration=50)
        normal_route = ["N1", "N2", "SINK"]

        stretched = attack.apply(normal_route, network=sample_network, current_time=1.0)
        for i in range(len(stretched) - 1):
            sender = stretched[i]
            receiver = stretched[i + 1]
            neighbor_ids = {n.id for n in sample_network.get_neighbors(sender)}
            assert receiver in neighbor_ids, f"Hop {sender} -> {receiver} is not a valid physical link!"

    def test_different_intensities_produce_severity_differences(self, sample_network):
        low_attack = StretchAttack("N2", intensity=AttackIntensity.LOW)
        med_attack = StretchAttack("N2", intensity=AttackIntensity.MEDIUM)
        high_attack = StretchAttack("N2", intensity=AttackIntensity.HIGH)

        route = ["N1", "N2", "SINK"]
        low_route = low_attack.apply(route, network=sample_network)
        med_route = med_attack.apply(route, network=sample_network)
        high_route = high_attack.apply(route, network=sample_network)

        assert len(low_route) <= len(med_route) <= len(high_route)
        assert len(low_route) > len(route)
        assert len(high_route) > len(low_route)

    def test_attacker_at_source(self, sample_network):
        # Attacker is N2, and route starts at N2
        attack = StretchAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N2", "SINK"]
        stretched = attack.apply(route, network=sample_network)
        assert stretched[0] == "N2"
        assert stretched[-1] == "SINK"
        assert len(stretched) > len(route)

    def test_attacker_at_destination_unchanged(self, sample_network):
        # Attacker is SINK; packet has already reached its final destination
        attack = StretchAttack("SINK", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "SINK"]
        stretched = attack.apply(route, network=sample_network)
        assert stretched == route


class TestStretchEdgeCases:
    """Tests for edge cases, missing data, and invalid inputs."""

    def test_route_without_attacker_unchanged_when_ttl_prevents_detour(
        self,
        sample_network,
    ):
        attack = StretchAttack("N5")
        route = ["N1", "N2", "SINK"]
        assert attack.apply(route, network=sample_network, ttl=2) == route

    def test_missing_network_returns_original(self):
        attack = StretchAttack("N2")
        route = ["N1", "N2", "SINK"]
        # Network is None -> safe fallback without inventing fake nodes
        assert attack.apply(route, network=None) == route

    def test_no_alternative_path_returns_original(self):
        # Linear network: A --- B --- C (no side paths exist)
        line_net = Network(communication_range=30.0)
        line_net.add_node(Node("A", 0, 0, 10.0))
        line_net.add_node(Node("B", 25, 0, 10.0))
        line_net.add_node(Node("C", 50, 0, 10.0))
        line_net.update_neighbors()

        attack = StretchAttack("B")
        route = ["A", "B", "C"]
        # No longer path exists -> safe fallback
        assert attack.apply(route, network=line_net) == route

    @pytest.mark.parametrize("invalid_route", [
        [],
        ["N1"],
        None,
        ["N1", 123],
    ])
    def test_invalid_routes_handled_safely(self, sample_network, invalid_route):
        attack = StretchAttack("N2")
        result = attack.apply(invalid_route, network=sample_network)
        assert isinstance(result, list)

    def test_works_with_packet_instance(self, sample_network):
        attack = StretchAttack("N2", intensity=AttackIntensity.HIGH)
        packet = Packet(source="N1", destination="SINK", ttl=20)
        # Manually advance to simulate arrival at N2
        packet.advance("N2")

        stretched = attack.apply(packet, network=sample_network)
        assert len(stretched) > len(packet.route)
        assert stretched[0] == "N1"
        assert stretched[-1] == "SINK"

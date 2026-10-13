"""
tests/test_carousel_attack.py
=============================
Unit tests for the Carousel Vampire Attack (Phase 2).
"""

import pytest

from attacks.base import AttackIntensity, AttackType
from attacks.carousel import CarouselAttack
from core.network import Network
from core.node import Node
from core.packet import Packet
from energy.energy_model import EnergyModel
from routing.router import Router
from simulator import Simulator


@pytest.fixture
def sample_network():
    """A standard network topology with adjacent nodes."""
    net = Network(communication_range=30.0)
    nodes = [
        Node("N1", 0, 0, 10.0),
        Node("N2", 25, 0, 10.0),      # Attacker
        Node("N3", 50, 0, 10.0),
        Node("SINK", 75, 0, 10.0),
    ]
    for n in nodes:
        net.add_node(n)
    net.set_sink("SINK")
    net.update_neighbors()
    return net


@pytest.fixture
def simulator_network():
    """The simulator's default topology, including the N5 and N6 detours."""
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


class TestCarouselAttackBasics:
    """Tests for CarouselAttack initialization and properties."""

    def test_instantiation_and_properties(self):
        attack = CarouselAttack(
            attacker_node_id="N2",
            intensity=AttackIntensity.HIGH,
            start_time=5.0,
            duration=40.0,
        )
        assert attack.attacker_node_id == "N2"
        assert attack.attack_type == AttackType.CAROUSEL
        assert attack.intensity == AttackIntensity.HIGH
        assert attack.start_time == 5.0
        assert attack.duration == 40.0
        assert attack.end_time == 45.0

    def test_default_values(self):
        attack = CarouselAttack(attacker_node_id="N2")
        assert attack.attacker_node_id == "N2"
        assert attack.attack_type == AttackType.CAROUSEL
        assert attack.intensity == AttackIntensity.MEDIUM
        assert attack.start_time == 0.0
        assert attack.duration == 100.0


class TestCarouselAttackLifecycle:
    """Tests for CarouselAttack time window lifecycle."""

    def test_inactive_before_start_time(self, sample_network):
        attack = CarouselAttack("N2", start_time=20.0, duration=30.0)
        assert not attack.is_active(10.0)

        route = ["N1", "N2", "N3", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=10.0)
        assert manipulated == route

    def test_active_during_window(self, sample_network):
        attack = CarouselAttack("N2", start_time=10.0, duration=20.0)
        assert attack.is_active(15.0)

        route = ["N1", "N2", "N3", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=15.0)
        assert len(manipulated) > len(route)

    def test_inactive_after_duration(self, sample_network):
        attack = CarouselAttack("N2", start_time=10.0, duration=20.0)
        assert not attack.is_active(30.0)

        route = ["N1", "N2", "N3", "SINK"]
        manipulated = attack.apply(route, network=sample_network, current_time=30.0)
        assert manipulated == route

    def test_zero_duration_always_inactive(self, sample_network):
        attack = CarouselAttack("N2", start_time=5.0, duration=0.0)
        assert not attack.is_active(5.0)
        route = ["N1", "N2", "N3", "SINK"]
        assert attack.apply(route, network=sample_network, current_time=5.0) == route


class TestCarouselRouteManipulation:
    """Tests for cycle insertion and node behavior."""

    def test_cycle_introduced(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.LOW, start_time=0, duration=50)
        route = ["N1", "N2", "N3", "SINK"]

        carousel_route = attack.apply(route, network=sample_network, ttl=10)
        assert carousel_route.count("N2") > 1
        assert carousel_route[-1] == "SINK"
        assert carousel_route[2:5] == ["N3", "N2", "N3"]

    def test_source_preserved_and_destination_excluded(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.MEDIUM)
        route = ["N1", "N2", "N3", "SINK"]

        carousel_route = attack.apply(route, network=sample_network, ttl=20)
        assert carousel_route[0] == "N1"
        assert carousel_route[-1] == "SINK"

    def test_attacker_appears_in_cycle(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]

        carousel_route = attack.apply(route, network=sample_network, ttl=30)
        # N2 appears repeatedly in the route
        assert carousel_route.count("N2") >= 2

    def test_intensity_differences(self, sample_network):
        low_attack = CarouselAttack("N2", intensity=AttackIntensity.LOW)
        med_attack = CarouselAttack("N2", intensity=AttackIntensity.MEDIUM)
        high_attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)

        route = ["N1", "N2", "N3", "SINK"]
        # Given a generous TTL budget (e.g. 30 hops)
        low_route = low_attack.apply(route, network=sample_network, ttl=30)
        med_route = med_attack.apply(route, network=sample_network, ttl=30)
        high_route = high_attack.apply(route, network=sample_network, ttl=30)

        assert len(low_route) <= len(med_route) <= len(high_route)
        assert low_route.count("N2") > 1
        assert len(high_route) > len(low_route)

    def test_attacker_at_source(self, sample_network):
        attack = CarouselAttack("N1", intensity=AttackIntensity.LOW)
        route = ["N1", "N2", "N3", "SINK"]

        carousel_route = attack.apply(route, network=sample_network, ttl=10)
        assert carousel_route[0] == "N1"
        assert carousel_route[-1] == "SINK"
        assert carousel_route.count("N1") > 1


class TestCarouselTTLAndSafetyConstraints:
    """Tests for TTL boundaries and infinite loop prevention."""

    def test_ttl_strictly_respected(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]  # 3 hops

        # Budget of 7 hops total
        ttl = 7
        carousel_route = attack.apply(route, network=sample_network, ttl=ttl)
        total_hops = len(carousel_route) - 1
        assert total_hops <= ttl

    def test_ttl_equal_to_1_never_routes_to_sink(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]
        carousel_route = attack.apply(route, network=sample_network, ttl=1)
        assert carousel_route == ["N1", "N2"]
        assert "SINK" not in carousel_route

    def test_high_intensity_uses_remaining_ttl_for_loop(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]  # 3 hops
        carousel_route = attack.apply(route, network=sample_network, ttl=4)
        assert carousel_route == ["N1", "N2", "N3", "N2", "N3"]
        assert len(carousel_route) - 1 == 4

    def test_no_infinite_loop_possible(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]

        # Run with default TTL (64)
        carousel_route = attack.apply(route, network=sample_network)
        assert len(carousel_route) < 100
        assert len(carousel_route) - 1 <= 64

    def test_attacker_at_destination_returns_original(self, sample_network):
        attack = CarouselAttack("SINK", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]
        assert attack.apply(route, network=sample_network) == route

    def test_route_without_attacker_returns_original(self, sample_network):
        attack = CarouselAttack("NON_EXISTENT")
        route = ["N1", "N2", "N3", "SINK"]
        assert attack.apply(route, network=sample_network) == route

    def test_missing_network_still_creates_cycle_with_next_hop(self):
        attack = CarouselAttack("N2", intensity=AttackIntensity.LOW)
        route = ["N1", "N2", "N3", "SINK"]
        carousel_route = attack.apply(route, network=None, ttl=10)
        assert carousel_route == ["N1", "N2", "N3", "N2"]

    @pytest.mark.parametrize("invalid_route", [
        [],
        ["N1"],
        None,
        ["N1", 99],
    ])
    def test_invalid_routes_handled_safely(self, sample_network, invalid_route):
        attack = CarouselAttack("N2")
        result = attack.apply(invalid_route, network=sample_network)
        assert isinstance(result, list)

    def test_works_with_packet_instance(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.LOW)
        packet = Packet(source="N1", destination="SINK", ttl=15)
        packet.advance("N2")

        carousel_route = attack.apply(packet, network=sample_network)
        assert len(carousel_route) > len(packet.route)
        assert carousel_route[0] == "N1"
        assert carousel_route[-1] == "SINK"
        assert carousel_route.count("N2") > 1


class TestCarouselSimulation:
    def test_packet_repeats_real_hops_and_expires_before_sink(self, sample_network):
        energy = EnergyModel()
        simulator = Simulator(
            sample_network,
            Router(sample_network, energy),
            energy,
            CarouselAttack("N2", intensity=AttackIntensity.HIGH),
        )
        progress: list[dict[str, object]] = []

        packet = simulator.run_packet(
            "N1",
            "SINK",
            packet_size=1000,
            ttl=11,
            on_progress=lambda event: progress.append(event.copy()),
        )

        assert packet.status.name == "EXPIRED"
        assert packet.route[0] == "N1"
        assert packet.route[1] == "N2"
        assert packet.route[-1] == "N2"
        assert packet.route.count("N2") > 1
        assert "SINK" not in packet.route
        assert sample_network.sink is not None
        assert sample_network.sink.received == 0
        assert [event["route"] for event in progress] == [
            packet.route[: index + 2] for index in range(len(progress))
        ]
        assert [
            (event["sender"], event["receiver"]) for event in progress
        ] == list(zip(packet.route, packet.route[1:]))
        assert all(event["route_kind"] == "attacked" for event in progress)
        result = simulator.get_results()[0]
        assert result["hops"] == packet.hops
        assert result["packet_status"] == "EXPIRED"

    def test_packet_loops_then_delivers_to_sink(self, simulator_network):
        energy = EnergyModel()
        simulator = Simulator(
            simulator_network,
            Router(simulator_network, energy),
            energy,
            CarouselAttack("N5", intensity=AttackIntensity.LOW),
        )
        progress: list[dict[str, object]] = []

        packet = simulator.run_packet(
            "N1",
            "SINK",
            ttl=8,
            on_progress=progress.append,
        )

        assert packet.status.name == "DELIVERED"
        assert packet.route[-1] == "SINK"
        assert any(
            packet.route[index : index + 3] == ["N2", "N5", "N2"]
            for index in range(len(packet.route) - 2)
        )
        assert packet.hops == len(packet.route) - 1
        assert packet.ttl == 8 - packet.hops
        assert progress[-1]["route"] == packet.route
        assert progress[-1]["status"] == "DELIVERED"
        assert progress[-1]["hops"] == packet.hops
        result = simulator.get_results()[0]
        assert result["hops"] == packet.hops
        assert result["packet_status"] == "DELIVERED"

    @pytest.mark.parametrize("attacker_id", ["N1", "N2", "N3", "N4", "N5", "N6"])
    def test_selected_attacker_is_used_in_actual_carousel_route(
        self,
        simulator_network,
        attacker_id,
    ):
        energy = EnergyModel()
        simulator = Simulator(
            simulator_network,
            Router(simulator_network, energy),
            energy,
            CarouselAttack(attacker_id, intensity=AttackIntensity.HIGH),
        )
        progress: list[dict[str, object]] = []

        packet = simulator.run_packet(
            "N1",
            "SINK",
            ttl=8,
            on_progress=progress.append,
        )

        assert packet.status.name == "EXPIRED"
        assert packet.hops == 8
        assert packet.route.count(attacker_id) > 1
        assert "SINK" not in packet.route
        for sender, receiver in zip(packet.route, packet.route[1:]):
            neighbor_ids = {
                neighbor.id for neighbor in simulator_network.get_neighbors(sender)
            }
            assert receiver in neighbor_ids

        assert progress[-1]["route"] == packet.route
        assert progress[-1]["status"] == "EXPIRED"
        result = simulator.get_results()[0]
        assert result["hops"] == packet.hops
        assert result["packet_status"] == packet.status.name

        if attacker_id == "N5":
            assert any(
                packet.route[index : index + 3] == ["N2", "N5", "N2"]
                for index in range(len(packet.route) - 2)
            )
        elif attacker_id == "N6":
            assert any(
                packet.route[index : index + 3] == ["N3", "N6", "N3"]
                for index in range(len(packet.route) - 2)
            )

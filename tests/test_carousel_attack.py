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
        assert len(carousel_route) > len(route)
        # N2 and N3 should repeat
        assert carousel_route.count("N2") > 1
        assert carousel_route.count("N3") > 1

    def test_source_and_destination_preserved(self, sample_network):
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
        assert len(low_route) > len(route)
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

    def test_ttl_equal_to_1_returns_original(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]
        # TTL of 1 cannot even support original 3-hop route
        assert attack.apply(route, network=sample_network, ttl=1) == route

    def test_ttl_budget_insufficient_for_cycle_returns_original(self, sample_network):
        attack = CarouselAttack("N2", intensity=AttackIntensity.HIGH)
        route = ["N1", "N2", "N3", "SINK"]  # 3 hops
        # TTL 4 has room for 1 hop, but a cycle needs 2 hops
        assert attack.apply(route, network=sample_network, ttl=4) == route

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
        # With network=None, Carousel uses next hop N3 safely
        carousel_route = attack.apply(route, network=None, ttl=10)
        assert carousel_route == ["N1", "N2", "N3", "N2", "N3", "SINK"]

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

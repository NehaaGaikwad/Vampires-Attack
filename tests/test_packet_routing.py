"""
tests/test_packet_routing.py
=============================
Comprehensive pytest tests for Part 2 of the Vampire Attack WSN simulator.

Coverage
--------
- Packet: creation, state, route, hops, TTL, visited, delivery, expiry, drop
- Dijkstra: shortest path under various topologies and edge cases
- RoutingTable: set/get/remove/has/clear operations
- Router: find_route, get_next_hop, route_packet
- Forwarding: energy, counters, route tracking, hop count, visited
- TTL: boundary conditions, expiry, no negative TTL
- Loop prevention: loop detection, packet dropped
- Energy integration: actual energy decreases
- Dead node: dead sender, dead receiver, dead intermediate
"""

from __future__ import annotations

import pytest

from core.node import Node
from core.network import Network
from core.packet import Packet, PacketStatus
from energy.energy_model import EnergyModel, NodeDeadError
from routing.dijkstra import shortest_path
from routing.routing_table import RoutingTable
from routing.router import Router


# ===========================================================================
# Shared fixtures
# ===========================================================================


@pytest.fixture
def linear_network() -> Network:
    """
    Linear chain topology:
    N1(0,0) -- N2(30,0) -- N3(60,0) -- SINK(90,0)
    All within communication range of 35.
    """
    net = Network(communication_range=35.0)
    net.add_node(Node("N1", 0.0, 0.0, 10.0))
    net.add_node(Node("N2", 30.0, 0.0, 10.0))
    net.add_node(Node("N3", 60.0, 0.0, 10.0))
    net.add_node(Node("SINK", 90.0, 0.0, 100.0))
    net.set_sink("SINK")
    net.update_neighbors()
    return net


@pytest.fixture
def em() -> EnergyModel:
    return EnergyModel()


@pytest.fixture
def router(linear_network, em) -> Router:
    return Router(linear_network, em)


@pytest.fixture
def multi_path_network() -> Network:
    """
    Multi-path topology:
      N1(0,0) -- N2(30,0)
      N1(0,0) -- N3(0,30)
      N2(30,0) -- SINK(30,30)
      N3(0,30) -- SINK(30,30)
    Communication range 35; distances:
      N1-N2 = 30, N1-N3 = 30, N2-SINK = 30, N3-SINK = 30
    Two equal-cost paths N1->N2->SINK and N1->N3->SINK (both distance=60).
    """
    net = Network(communication_range=35.0)
    net.add_node(Node("N1", 0.0, 0.0, 10.0))
    net.add_node(Node("N2", 30.0, 0.0, 10.0))
    net.add_node(Node("N3", 0.0, 30.0, 10.0))
    net.add_node(Node("SINK", 30.0, 30.0, 100.0))
    net.set_sink("SINK")
    net.update_neighbors()
    return net


@pytest.fixture
def isolated_network() -> Network:
    """
    Two nodes out of communication range of each other.
    N1(0,0) and N2(1000,0) with range 50.
    """
    net = Network(communication_range=50.0)
    net.add_node(Node("N1", 0.0, 0.0, 10.0))
    net.add_node(Node("N2", 1000.0, 0.0, 10.0))
    net.update_neighbors()
    return net


# ===========================================================================
# 1. PACKET TESTS
# ===========================================================================


class TestPacketCreation:
    """Packet instantiation and initial state."""

    def test_source(self):
        p = Packet("N1", "SINK")
        assert p.source == "N1"

    def test_destination(self):
        p = Packet("N1", "SINK")
        assert p.destination == "SINK"

    def test_default_ttl(self):
        p = Packet("N1", "SINK")
        assert p.ttl == Packet.DEFAULT_TTL

    def test_custom_ttl(self):
        p = Packet("N1", "SINK", ttl=10)
        assert p.ttl == 10

    def test_initial_hops_zero(self):
        p = Packet("N1", "SINK")
        assert p.hops == 0

    def test_initial_route_contains_source(self):
        p = Packet("N1", "SINK")
        assert p.route == ["N1"]

    def test_initial_current_node_is_source(self):
        p = Packet("N1", "SINK")
        assert p.current_node == "N1"

    def test_initial_visited_contains_source(self):
        p = Packet("N1", "SINK")
        assert "N1" in p.visited

    def test_initial_status_in_transit(self):
        p = Packet("N1", "SINK")
        assert p.in_transit is True
        assert p.delivered is False
        assert p.expired is False
        assert p.dropped is False

    def test_default_packet_size(self):
        p = Packet("N1", "SINK")
        assert p.packet_size == Packet.DEFAULT_PACKET_SIZE

    def test_custom_packet_size(self):
        p = Packet("N1", "SINK", packet_size=1000)
        assert p.packet_size == 1000

    def test_invalid_empty_source_raises(self):
        with pytest.raises(ValueError):
            Packet("", "SINK")

    def test_invalid_empty_destination_raises(self):
        with pytest.raises(ValueError):
            Packet("N1", "")

    def test_invalid_ttl_zero_raises(self):
        with pytest.raises(ValueError):
            Packet("N1", "SINK", ttl=0)

    def test_invalid_ttl_negative_raises(self):
        with pytest.raises(ValueError):
            Packet("N1", "SINK", ttl=-1)

    def test_invalid_negative_packet_size_raises(self):
        with pytest.raises(ValueError):
            Packet("N1", "SINK", packet_size=-1)

    def test_zero_packet_size_allowed(self):
        p = Packet("N1", "SINK", packet_size=0)
        assert p.packet_size == 0

    def test_source_equals_destination_allowed(self):
        # Source and destination may be the same — caller is responsible.
        p = Packet("N1", "N1")
        assert p.source == "N1"
        assert p.destination == "N1"

    def test_route_returns_copy(self):
        """Mutating the returned route list must not affect internal state."""
        p = Packet("N1", "SINK")
        r = p.route
        r.append("EVIL")
        assert p.route == ["N1"]

    def test_visited_returns_copy(self):
        """Mutating the returned visited set must not affect internal state."""
        p = Packet("N1", "SINK")
        v = p.visited
        v.add("EVIL")
        assert "EVIL" not in p.visited


class TestPacketAdvance:
    """Packet.advance() state transitions."""

    def test_advance_updates_current_node(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert p.current_node == "N2"

    def test_advance_increments_hops(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert p.hops == 1

    def test_advance_decrements_ttl(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert p.ttl == 4

    def test_advance_updates_route(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert p.route == ["N1", "N2"]

    def test_advance_updates_visited(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert "N2" in p.visited

    def test_advance_multi_hop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        p.advance("N3")
        p.advance("SINK")
        assert p.route == ["N1", "N2", "N3", "SINK"]
        assert p.hops == 3

    def test_advance_to_destination_delivers(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("SINK")
        assert p.delivered is True
        assert p.status == PacketStatus.DELIVERED

    def test_advance_to_non_destination_stays_in_transit(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        assert p.in_transit is True

    def test_advance_on_delivered_raises(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("SINK")
        with pytest.raises(RuntimeError):
            p.advance("ANYWHERE")

    def test_advance_on_expired_raises(self):
        p = Packet("N1", "SINK", ttl=1)
        p.advance("N2")  # TTL now 0
        p.advance("N3")  # should expire
        with pytest.raises(RuntimeError):
            p.advance("SINK")

    def test_advance_on_dropped_raises(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_dropped()
        with pytest.raises(RuntimeError):
            p.advance("N2")

    def test_advance_empty_node_id_raises(self):
        p = Packet("N1", "SINK", ttl=5)
        with pytest.raises(ValueError):
            p.advance("")


class TestPacketTTL:
    """TTL handling and expiry."""

    def test_ttl_decrements_each_hop(self):
        p = Packet("N1", "SINK", ttl=3)
        p.advance("N2")
        assert p.ttl == 2
        p.advance("N3")
        assert p.ttl == 1

    def test_ttl_1_allows_one_hop(self):
        p = Packet("N1", "SINK", ttl=1)
        p.advance("SINK")
        assert p.delivered is True

    def test_ttl_1_expires_if_destination_not_reached(self):
        p = Packet("N1", "SINK", ttl=1)
        p.advance("N2")  # Uses the 1 TTL — now TTL=0
        assert p.ttl == 0
        # Next advance should expire
        p.advance("SINK")  # TTL 0 → EXPIRED
        assert p.expired is True

    def test_ttl_exact_boundary_delivers(self):
        """3-hop route with TTL=3 should deliver successfully."""
        p = Packet("N1", "SINK", ttl=3)
        p.advance("N2")
        p.advance("N3")
        p.advance("SINK")
        assert p.delivered is True
        assert p.ttl == 0

    def test_ttl_too_small_expires(self):
        """3-hop route with TTL=2 should expire at the 3rd hop attempt."""
        p = Packet("N1", "SINK", ttl=2)
        p.advance("N2")
        p.advance("N3")
        # TTL now 0; next advance should expire
        p.advance("SINK")
        assert p.expired is True

    def test_ttl_never_negative(self):
        p = Packet("N1", "SINK", ttl=1)
        p.advance("N2")
        p.advance("SINK")
        assert p.ttl >= 0

    def test_no_forwarding_after_expiry(self):
        p = Packet("N1", "SINK", ttl=1)
        p.advance("N2")
        p.advance("SINK")  # expires here
        assert p.expired is True
        with pytest.raises(RuntimeError):
            p.advance("SINK")

    def test_mark_expired_when_in_transit(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_expired()
        assert p.expired is True

    def test_mark_expired_no_effect_when_delivered(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("SINK")
        p.mark_expired()
        assert p.delivered is True  # status unchanged

    def test_mark_expired_no_effect_when_dropped(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_dropped()
        p.mark_expired()
        assert p.dropped is True  # status unchanged


class TestPacketLoopPrevention:
    """Loop detection via visited set."""

    def test_revisit_detects_loop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        p.advance("N1")  # N1 already visited → DROPPED
        assert p.dropped is True

    def test_status_dropped_on_loop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        p.advance("N1")
        assert p.status == PacketStatus.DROPPED

    def test_no_hop_count_increment_on_loop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        hops_before = p.hops
        p.advance("N1")  # loop → DROPPED, hops should NOT increment
        assert p.hops == hops_before

    def test_no_route_update_on_loop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        route_before = p.route
        p.advance("N1")  # loop → DROPPED, route should NOT update
        assert p.route == route_before

    def test_no_ttl_decrement_on_loop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        ttl_before = p.ttl
        p.advance("N1")  # loop → DROPPED, TTL should NOT decrement
        assert p.ttl == ttl_before

    def test_no_forwarding_after_loop_drop(self):
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")
        p.advance("N1")  # dropped
        with pytest.raises(RuntimeError):
            p.advance("N3")

    def test_mark_dropped_when_in_transit(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_dropped()
        assert p.dropped is True

    def test_mark_dropped_no_effect_when_delivered(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("SINK")
        p.mark_dropped()
        assert p.delivered is True


class TestPacketDelivery:
    """Delivery state and completeness."""

    def test_delivered_flag(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        p.advance("SINK")
        assert p.delivered is True

    def test_route_preserved_after_delivery(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        p.advance("SINK")
        assert p.route == ["N1", "N2", "SINK"]

    def test_hops_count_after_delivery(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        p.advance("N3")
        p.advance("SINK")
        assert p.hops == 3

    def test_visited_after_delivery(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        p.advance("SINK")
        assert p.visited == {"N1", "N2", "SINK"}

    def test_current_node_after_delivery(self):
        p = Packet("N1", "SINK", ttl=5)
        p.advance("N2")
        p.advance("SINK")
        assert p.current_node == "SINK"


# ===========================================================================
# 2. DIJKSTRA TESTS
# ===========================================================================


class TestDijkstraSimple:
    """Basic path finding."""

    def test_two_node_direct_path(self):
        net = Network(communication_range=50.0)
        net.add_node(Node("A", 0.0, 0.0, 10.0))
        net.add_node(Node("B", 30.0, 0.0, 10.0))
        net.update_neighbors()
        path = shortest_path(net, "A", "B")
        assert path == ["A", "B"]

    def test_linear_chain(self, linear_network):
        path = shortest_path(linear_network, "N1", "SINK")
        assert path == ["N1", "N2", "N3", "SINK"]

    def test_source_equals_destination(self, linear_network):
        path = shortest_path(linear_network, "N1", "N1")
        assert path == ["N1"]

    def test_path_includes_source_and_destination(self, linear_network):
        path = shortest_path(linear_network, "N1", "SINK")
        assert path[0] == "N1"
        assert path[-1] == "SINK"

    def test_path_is_ordered_node_ids(self, linear_network):
        path = shortest_path(linear_network, "N1", "SINK")
        assert isinstance(path, list)
        assert all(isinstance(nid, str) for nid in path)


class TestDijkstraEdgeCases:
    """Nonexistent and dead node handling."""

    def test_nonexistent_source_returns_none(self, linear_network):
        assert shortest_path(linear_network, "GHOST", "SINK") is None

    def test_nonexistent_destination_returns_none(self, linear_network):
        assert shortest_path(linear_network, "N1", "GHOST") is None

    def test_dead_source_returns_none(self, linear_network):
        linear_network.get_node("N1").consume_energy(9999)
        assert shortest_path(linear_network, "N1", "SINK") is None

    def test_dead_destination_returns_none(self, linear_network):
        linear_network.get_node("SINK").consume_energy(9999)
        assert shortest_path(linear_network, "N1", "SINK") is None

    def test_dead_intermediate_reroutes(self, linear_network):
        # Kill N2; N1->N3 distance is 60 > range 35, so no path
        linear_network.get_node("N2").consume_energy(9999)
        result = shortest_path(linear_network, "N1", "SINK")
        # With range 35, N1 cannot reach N3 directly (distance 60 > 35)
        # So killing N2 should make SINK unreachable from N1
        assert result is None

    def test_unreachable_destination_returns_none(self, isolated_network):
        result = shortest_path(isolated_network, "N1", "N2")
        assert result is None

    def test_empty_path_returns_none_for_missing_source(self):
        net = Network(communication_range=50.0)
        net.add_node(Node("A", 0, 0, 10))
        net.update_neighbors()
        assert shortest_path(net, "GHOST", "A") is None


class TestDijkstraShortestPath:
    """Verifies minimum-distance path is selected."""

    def test_direct_path_preferred_over_longer(self):
        """
        Topology:
        N1(0,0) -- N2(10,0) -- SINK(20,0)
        N1 can also reach SINK directly if distance <= range,
        but let's use range 15: N1-N2=10, N2-SINK=10, N1-SINK=20 > 15
        So only path is N1->N2->SINK.
        """
        net = Network(communication_range=15.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 10.0, 0.0, 10.0))
        net.add_node(Node("SINK", 20.0, 0.0, 100.0))
        net.update_neighbors()
        path = shortest_path(net, "N1", "SINK")
        assert path == ["N1", "N2", "SINK"]

    def test_shorter_direct_path_chosen(self):
        """
        N1(0,0), N2(5,0), SINK(10,0), range=15
        N1 can reach N2 (dist=5) and SINK (dist=10) directly.
        Direct N1->SINK has cost 10; N1->N2->SINK has cost 5+5=10 (equal).
        Since both paths have equal total distance, Dijkstra may return either.
        What matters is that the returned path is VALID (connects N1 to SINK).
        """
        net = Network(communication_range=15.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 5.0, 0.0, 10.0))
        net.add_node(Node("SINK", 10.0, 0.0, 100.0))
        net.update_neighbors()
        path = shortest_path(net, "N1", "SINK")
        assert path is not None
        assert path[0] == "N1"
        assert path[-1] == "SINK"
        # Both ["N1", "SINK"] and ["N1", "N2", "SINK"] are valid (equal cost=10)



    def test_multi_path_equal_cost_deterministic(self, multi_path_network):
        """Both paths N1->N2->SINK and N1->N3->SINK have equal cost (60).
        Result should be deterministic (same call always gives same result).
        """
        path1 = shortest_path(multi_path_network, "N1", "SINK")
        path2 = shortest_path(multi_path_network, "N1", "SINK")
        assert path1 == path2

    def test_multi_path_returns_valid_path(self, multi_path_network):
        path = shortest_path(multi_path_network, "N1", "SINK")
        assert path is not None
        assert path[0] == "N1"
        assert path[-1] == "SINK"


class TestDijkstraCommunicationRange:
    """Topology respects communication range."""

    def test_nodes_outside_range_not_in_path(self):
        """
        N1(0,0) -- N2(30,0), N2-N3 distance 60 > range 35.
        SINK at N3 position is unreachable from N1.
        """
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("SINK", 90.0, 0.0, 100.0))
        net.update_neighbors()
        # N2 and SINK are 60 apart > range 35 — no path
        result = shortest_path(net, "N1", "SINK")
        assert result is None


# ===========================================================================
# 3. ROUTING TABLE TESTS
# ===========================================================================


class TestRoutingTableBasic:
    """Core set/get/has operations."""

    def test_set_and_get(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        assert rt.get_next_hop("SINK") == "N3"

    def test_has_route_after_set(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        assert rt.has_route("SINK") is True

    def test_has_route_missing(self):
        rt = RoutingTable()
        assert rt.has_route("SINK") is False

    def test_get_missing_returns_none(self):
        rt = RoutingTable()
        assert rt.get_next_hop("SINK") is None

    def test_update_existing_route(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N2")
        rt.set_next_hop("SINK", "N4")
        assert rt.get_next_hop("SINK") == "N4"

    def test_remove_route(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        rt.remove_route("SINK")
        assert rt.has_route("SINK") is False
        assert rt.get_next_hop("SINK") is None

    def test_remove_nonexistent_silent(self):
        rt = RoutingTable()
        # Should not raise
        rt.remove_route("GHOST")

    def test_clear(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        rt.set_next_hop("N3", "N2")
        rt.clear()
        assert rt.has_route("SINK") is False
        assert rt.has_route("N3") is False
        assert len(rt) == 0

    def test_len_empty(self):
        rt = RoutingTable()
        assert len(rt) == 0

    def test_len_after_additions(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        rt.set_next_hop("N3", "N2")
        assert len(rt) == 2

    def test_invalid_empty_destination_raises(self):
        rt = RoutingTable()
        with pytest.raises(ValueError):
            rt.set_next_hop("", "N3")

    def test_invalid_empty_next_hop_raises(self):
        rt = RoutingTable()
        with pytest.raises(ValueError):
            rt.set_next_hop("SINK", "")

    def test_multiple_destinations(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N3")
        rt.set_next_hop("N4", "N2")
        assert rt.get_next_hop("SINK") == "N3"
        assert rt.get_next_hop("N4") == "N2"


# ===========================================================================
# 4. ROUTER TESTS
# ===========================================================================


class TestRouterFindRoute:
    """Router.find_route() tests."""

    def test_finds_linear_route(self, router):
        route = router.find_route("N1", "SINK")
        assert route == ["N1", "N2", "N3", "SINK"]

    def test_source_equals_destination(self, router):
        route = router.find_route("N1", "N1")
        assert route == ["N1"]

    def test_nonexistent_source_returns_none(self, router):
        assert router.find_route("GHOST", "SINK") is None

    def test_nonexistent_destination_returns_none(self, router):
        assert router.find_route("N1", "GHOST") is None

    def test_dead_source_returns_none(self, router, linear_network):
        linear_network.get_node("N1").consume_energy(9999)
        assert router.find_route("N1", "SINK") is None

    def test_dead_destination_returns_none(self, router, linear_network):
        linear_network.get_node("SINK").consume_energy(9999)
        assert router.find_route("N1", "SINK") is None

    def test_unreachable_returns_none(self, em):
        net = Network(communication_range=50.0)
        net.add_node(Node("A", 0, 0, 10))
        net.add_node(Node("B", 1000, 0, 10))
        net.update_neighbors()
        r = Router(net, em)
        assert r.find_route("A", "B") is None

    def test_route_starts_with_source(self, router):
        route = router.find_route("N1", "SINK")
        assert route[0] == "N1"

    def test_route_ends_with_destination(self, router):
        route = router.find_route("N1", "SINK")
        assert route[-1] == "SINK"

    def test_dead_intermediate_makes_unreachable(self, router, linear_network):
        linear_network.get_node("N2").consume_energy(9999)
        # Chain is N1-N2-N3-SINK; killing N2 disconnects N1
        assert router.find_route("N1", "SINK") is None


class TestRouterGetNextHop:
    """Router.get_next_hop() tests."""

    def test_first_hop_from_source(self, router):
        assert router.get_next_hop("N1", "SINK") == "N2"

    def test_middle_hop(self, router):
        assert router.get_next_hop("N2", "SINK") == "N3"

    def test_last_hop_before_sink(self, router):
        assert router.get_next_hop("N3", "SINK") == "SINK"

    def test_current_equals_destination_returns_none(self, router):
        assert router.get_next_hop("SINK", "SINK") is None

    def test_unreachable_returns_none(self, router, linear_network):
        linear_network.get_node("N2").consume_energy(9999)
        assert router.get_next_hop("N1", "SINK") is None

    def test_repeated_calls_consistent(self, router):
        r1 = router.get_next_hop("N1", "SINK")
        r2 = router.get_next_hop("N1", "SINK")
        assert r1 == r2


class TestRouterRoutePacket:
    """Router.route_packet() end-to-end tests."""

    def test_single_hop_delivery(self, em):
        net = Network(communication_range=50.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("SINK", 30.0, 0.0, 100.0))
        net.set_sink("SINK")
        net.update_neighbors()
        r = Router(net, em)
        p = Packet("N1", "SINK", ttl=5)
        result = r.route_packet(p)
        assert result.delivered is True

    def test_multi_hop_delivery(self, router):
        p = Packet("N1", "SINK", ttl=10)
        result = router.route_packet(p)
        assert result.delivered is True

    def test_delivered_route_is_complete(self, router):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert p.route == ["N1", "N2", "N3", "SINK"]

    def test_hop_count_after_delivery(self, router):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert p.hops == 3

    def test_visited_nodes_after_delivery(self, router):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert p.visited == {"N1", "N2", "N3", "SINK"}

    def test_unreachable_drops_packet(self, em, isolated_network):
        r = Router(isolated_network, em)
        p = Packet("N1", "N2", ttl=10)
        result = r.route_packet(p)
        assert result.dropped is True

    def test_non_in_transit_packet_returned_unchanged(self, router):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_dropped()
        status_before = p.status
        result = router.route_packet(p)
        assert result.status == status_before

    def test_source_equals_destination(self, router):
        p = Packet("N1", "N1", ttl=5)
        result = router.route_packet(p)
        assert result.delivered is True


# ===========================================================================
# 5. FORWARDING COUNTER TESTS
# ===========================================================================


class TestForwardedCounters:
    """Verify node.forwarded is set correctly."""

    def test_source_forwarded_zero(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N1").forwarded == 0

    def test_destination_forwarded_zero(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("SINK").forwarded == 0

    def test_intermediate_n2_forwarded_one(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N2").forwarded == 1

    def test_intermediate_n3_forwarded_one(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N3").forwarded == 1

    def test_sent_counter_incremented_on_transmit(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        # N1, N2, N3 each sent one packet to the next node.
        assert linear_network.get_node("N1").sent == 1
        assert linear_network.get_node("N2").sent == 1
        assert linear_network.get_node("N3").sent == 1
        # SINK receives but doesn't send
        assert linear_network.get_node("SINK").sent == 0

    def test_received_counter_incremented(self, router, linear_network):
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N2").received == 1
        assert linear_network.get_node("N3").received == 1
        assert linear_network.get_node("SINK").received == 1
        # Source (N1) receives nothing in this simple case
        assert linear_network.get_node("N1").received == 0

    def test_forwarded_not_incremented_on_drop(self, em):
        """If packet drops at unreachable, no forwarded incremented."""
        net = Network(communication_range=50.0)
        net.add_node(Node("N1", 0, 0, 10))
        net.add_node(Node("N2", 1000, 0, 10))
        net.update_neighbors()
        r = Router(net, em)
        p = Packet("N1", "N2", ttl=10)
        r.route_packet(p)
        assert net.get_node("N1").forwarded == 0


# ===========================================================================
# 6. TTL INTEGRATION TESTS (Router level)
# ===========================================================================


class TestTTLIntegration:
    """TTL enforcement through Router.route_packet()."""

    def test_sufficient_ttl_delivers(self, router):
        # 3-hop path; TTL=3 is exactly sufficient
        p = Packet("N1", "SINK", ttl=3)
        router.route_packet(p)
        assert p.delivered is True

    def test_insufficient_ttl_expires(self, router):
        # 3-hop path; TTL=2 is not enough
        p = Packet("N1", "SINK", ttl=2)
        router.route_packet(p)
        assert p.expired is True

    def test_ttl_1_too_small_for_multi_hop(self, router):
        # TTL=1: N1->N2 OK, then TTL=0 → expire at next attempt
        p = Packet("N1", "SINK", ttl=1)
        router.route_packet(p)
        assert p.expired is True

    def test_ttl_never_negative_after_routing(self, router):
        p = Packet("N1", "SINK", ttl=2)
        router.route_packet(p)
        assert p.ttl >= 0

    def test_high_ttl_delivers_correctly(self, router):
        p = Packet("N1", "SINK", ttl=50)
        router.route_packet(p)
        assert p.delivered is True


# ===========================================================================
# 7. ENERGY INTEGRATION TESTS
# ===========================================================================


class TestEnergyIntegration:
    """Verify energy decreases on forwarding."""

    def test_sender_energy_decreases(self, router, linear_network):
        n1_energy_before = linear_network.get_node("N1").energy
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N1").energy < n1_energy_before

    def test_receiver_energy_decreases(self, router, linear_network):
        sink_energy_before = linear_network.get_node("SINK").energy
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("SINK").energy < sink_energy_before

    def test_intermediate_energy_decreases(self, router, linear_network):
        n2_before = linear_network.get_node("N2").energy
        n3_before = linear_network.get_node("N3").energy
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert linear_network.get_node("N2").energy < n2_before
        assert linear_network.get_node("N3").energy < n3_before

    def test_energy_not_affected_for_unreachable(self, em):
        net = Network(communication_range=50.0)
        n1 = Node("N1", 0, 0, 10)
        n2 = Node("N2", 1000, 0, 10)
        net.add_node(n1)
        net.add_node(n2)
        net.update_neighbors()
        r = Router(net, em)
        n1_before = n1.energy
        p = Packet("N1", "N2", ttl=10)
        r.route_packet(p)
        assert n1.energy == n1_before  # no energy consumed — no route found


# ===========================================================================
# 8. DEAD NODE HANDLING TESTS
# ===========================================================================


class TestDeadNodeHandling:
    """Routing respects dead nodes."""

    def test_dead_intermediate_drops_packet(self, router, linear_network):
        # Kill N2 after building router; route should fail
        linear_network.get_node("N2").consume_energy(9999)
        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)
        assert p.dropped is True

    def test_no_route_through_dead_node(self, linear_network, em):
        linear_network.get_node("N2").consume_energy(9999)
        r = Router(linear_network, em)
        route = r.find_route("N1", "SINK")
        assert route is None

    def test_dead_source_find_route_none(self, router, linear_network):
        linear_network.get_node("N1").consume_energy(9999)
        assert router.find_route("N1", "SINK") is None

    def test_dead_destination_find_route_none(self, router, linear_network):
        linear_network.get_node("SINK").consume_energy(9999)
        assert router.find_route("N1", "SINK") is None

    def test_dead_sender_drops_packet(self, em):
        """If the sender dies between route calculation and forwarding."""
        net = Network(communication_range=50.0)
        n1 = Node("N1", 0, 0, 0.000001)  # tiny energy
        n2 = Node("SINK", 30, 0, 100)
        net.add_node(n1)
        net.add_node(n2)
        net.set_sink("SINK")
        net.update_neighbors()
        r = Router(net, em)
        # Drain N1's energy so it's dead before routing
        n1.consume_energy(9999)
        p = Packet("N1", "SINK", ttl=5)
        result = r.route_packet(p)
        assert result.dropped is True

    def test_routing_table_cache_invalidated_on_dead_node(self, router, linear_network):
        """If cached next hop dies, router should recalculate or return None."""
        # Populate cache
        router.get_next_hop("N1", "SINK")
        # Kill the cached next hop (N2)
        linear_network.get_node("N2").consume_energy(9999)
        # Should detect dead cached node and recalculate (which finds no path)
        result = router.get_next_hop("N1", "SINK")
        assert result is None


# ===========================================================================
# 9. INTEGRATION / ROUND-TRIP TESTS
# ===========================================================================


class TestIntegration:
    """End-to-end integration covering the full Member 2 workflow."""

    def test_full_linear_route_packet(self):
        """Complete multi-hop packet delivery with energy and counter checks."""
        net = Network(communication_range=35.0)
        n1 = Node("N1", 0.0, 0.0, 10.0)
        n2 = Node("N2", 30.0, 0.0, 10.0)
        n3 = Node("N3", 60.0, 0.0, 10.0)
        sink = Node("SINK", 90.0, 0.0, 100.0)
        for node in (n1, n2, n3, sink):
            net.add_node(node)
        net.set_sink("SINK")
        net.update_neighbors()

        em = EnergyModel()
        router = Router(net, em)

        p = Packet("N1", "SINK", ttl=10)
        router.route_packet(p)

        # Delivery
        assert p.delivered is True
        assert p.route == ["N1", "N2", "N3", "SINK"]
        assert p.hops == 3

        # Counters
        assert n1.sent == 1
        assert n1.forwarded == 0
        assert n2.received == 1
        assert n2.forwarded == 1
        assert n3.received == 1
        assert n3.forwarded == 1
        assert sink.received == 1
        assert sink.forwarded == 0

        # Energy consumed
        assert n1.energy < 10.0
        assert n2.energy < 10.0
        assert n3.energy < 10.0
        assert sink.energy < 100.0

    def test_packet_dropped_when_no_route(self):
        net = Network(communication_range=10.0)
        net.add_node(Node("N1", 0, 0, 10))
        net.add_node(Node("SINK", 1000, 0, 100))
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)
        p = Packet("N1", "SINK", ttl=5)
        r.route_packet(p)
        assert p.dropped is True
        assert p.hops == 0

    def test_ttl_expiry_during_routing(self):
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("N3", 60.0, 0.0, 10.0))
        net.add_node(Node("SINK", 90.0, 0.0, 100.0))
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)
        # TTL=2 for a 3-hop path → should expire
        p = Packet("N1", "SINK", ttl=2)
        r.route_packet(p)
        assert p.expired is True
        assert p.ttl >= 0  # never negative

    def test_routing_table_populated_by_get_next_hop(self):
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("SINK", 60.0, 0.0, 100.0))
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)
        # Initially empty
        assert r.routing_table.has_route("SINK") is False
        r.get_next_hop("N1", "SINK")
        # After call, should be populated
        assert r.routing_table.has_route("SINK") is True

    def test_multiple_packets_accumulate_forwarded(self):
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("SINK", 60.0, 0.0, 100.0))
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)
        for _ in range(3):
            p = Packet("N1", "SINK", ttl=10)
            r.route_packet(p)
        # N2 should have forwarded 3 packets
        assert net.get_node("N2").forwarded == 3

    def test_repr_packet(self):
        p = Packet("N1", "SINK", ttl=5)
        r = repr(p)
        assert "N1" in r
        assert "SINK" in r

    def test_repr_routing_table(self):
        rt = RoutingTable()
        rt.set_next_hop("SINK", "N2")
        assert "SINK" in repr(rt)


# ===========================================================================
# 10. REGRESSION — Member 1 tests still importable
# ===========================================================================

class TestMember1Regression:
    """Smoke-level check that Member 1 APIs still function after Member 2."""

    def test_node_alive(self):
        n = Node("X", 0, 0, 10)
        assert n.alive is True

    def test_network_distance(self):
        net = Network(communication_range=50)
        a = Node("A", 0, 0, 10)
        b = Node("B", 3, 4, 10)
        net.add_node(a)
        net.add_node(b)
        import math
        assert net.distance(a, b) == pytest.approx(5.0)

    def test_energy_model_transmit(self):
        em = EnergyModel()
        s = Node("S", 0, 0, 10)
        r = Node("R", 10, 0, 10)
        result = em.transmit(s, r, 4000, 10.0)
        assert s.sent == 1
        assert r.received == 1


# ===========================================================================
# 11. ADDITIONAL COVERAGE — gaps found during verification pass
# ===========================================================================


class TestPacketMarkDelivered:
    """Packet.mark_delivered() — public API for source==destination case."""

    def test_mark_delivered_when_in_transit(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_delivered()
        assert p.delivered is True
        assert p.status == PacketStatus.DELIVERED

    def test_mark_delivered_no_effect_when_expired(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_expired()
        p.mark_delivered()
        assert p.expired is True  # terminal state unchanged

    def test_mark_delivered_no_effect_when_dropped(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_dropped()
        p.mark_delivered()
        assert p.dropped is True  # terminal state unchanged

    def test_mark_delivered_no_effect_when_already_delivered(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_delivered()
        p.mark_delivered()  # second call — no error, no change
        assert p.delivered is True

    def test_advance_raises_after_mark_delivered(self):
        p = Packet("N1", "SINK", ttl=5)
        p.mark_delivered()
        with pytest.raises(RuntimeError):
            p.advance("N2")


class TestRoutePacketPacketSizeOverride:
    """route_packet() packet_size parameter correctly overrides packet's own size."""

    def test_packet_size_override_changes_energy_cost(self):
        """Routing with a larger packet_size should consume more energy."""
        net = Network(communication_range=50.0)
        n1a = Node("S1", 0.0, 0.0, 100.0)
        sk1 = Node("SK1", 30.0, 0.0, 100.0)
        net.add_node(n1a)
        net.add_node(sk1)
        net.set_sink("SK1")
        net.update_neighbors()

        # Route with small packet size
        em1 = EnergyModel()
        r1 = Router(net, em1)
        p1 = Packet("S1", "SK1", ttl=5, packet_size=100)
        r1.route_packet(p1)
        energy_after_small = net.get_node("S1").energy
        energy_consumed_small = 100.0 - energy_after_small

        # Reset for second run
        net2 = Network(communication_range=50.0)
        n1b = Node("S1", 0.0, 0.0, 100.0)
        sk2 = Node("SK1", 30.0, 0.0, 100.0)
        net2.add_node(n1b)
        net2.add_node(sk2)
        net2.set_sink("SK1")
        net2.update_neighbors()

        # Route with larger overridden packet size
        em2 = EnergyModel()
        r2 = Router(net2, em2)
        p2 = Packet("S1", "SK1", ttl=5, packet_size=100)
        r2.route_packet(p2, packet_size=10000)  # override to larger size
        energy_consumed_large = 100.0 - net2.get_node("S1").energy

        assert energy_consumed_large > energy_consumed_small


class TestRoutePacketMidRoute:
    """route_packet() can start from a relay node, not just the source."""

    def test_route_from_intermediate_node(self):
        """A packet already at N2 can be routed onward to SINK."""
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("N3", 60.0, 0.0, 10.0))
        net.add_node(Node("SINK", 90.0, 0.0, 100.0))
        net.set_sink("SINK")
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)

        # Simulate a packet that is currently at N2 (already advanced once).
        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")  # moves packet to N2 manually
        assert p.current_node == "N2"
        assert p.in_transit

        # Now route_packet from N2
        r.route_packet(p)
        assert p.delivered is True
        assert p.current_node == "SINK"
        # Route should be N1 -> N2 -> N3 -> SINK
        assert p.route == ["N1", "N2", "N3", "SINK"]

    def test_hops_correct_for_mid_route_start(self):
        """Hops for a packet advanced manually then routed should be additive."""
        net = Network(communication_range=35.0)
        net.add_node(Node("N1", 0.0, 0.0, 10.0))
        net.add_node(Node("N2", 30.0, 0.0, 10.0))
        net.add_node(Node("SINK", 60.0, 0.0, 100.0))
        net.set_sink("SINK")
        net.update_neighbors()
        em = EnergyModel()
        r = Router(net, em)

        p = Packet("N1", "SINK", ttl=10)
        p.advance("N2")   # 1 hop manually
        r.route_packet(p)  # 1 more hop via router
        assert p.hops == 2
        assert p.delivered is True


class TestPacketHopsOnFailure:
    """Hops must not change when packet is dropped or expired."""

    def test_hops_zero_when_dropped_immediately(self, em):
        net = Network(communication_range=50.0)
        net.add_node(Node("N1", 0, 0, 10))
        net.add_node(Node("N2", 1000, 0, 10))
        net.update_neighbors()
        r = Router(net, em)
        p = Packet("N1", "N2", ttl=5)
        r.route_packet(p)
        assert p.hops == 0  # no hop was taken

    def test_hops_partial_when_expired(self, router):
        """With TTL=2 on a 3-hop route, 2 hops are taken then it expires."""
        p = Packet("N1", "SINK", ttl=2)
        router.route_packet(p)
        assert p.expired is True
        assert p.hops == 2  # exactly 2 hops were taken before expiry


class TestDijkstraSingleNode:
    """Dijkstra edge cases with a single node or no neighbours."""

    def test_single_node_source_equals_dest(self):
        net = Network(communication_range=50.0)
        net.add_node(Node("A", 0, 0, 10))
        net.update_neighbors()
        path = shortest_path(net, "A", "A")
        assert path == ["A"]

    def test_two_nodes_no_path_reversed(self, isolated_network):
        # Also check B->A direction
        path = shortest_path(isolated_network, "N2", "N1")
        assert path is None


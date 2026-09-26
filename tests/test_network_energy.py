"""
tests/test_network_energy.py
============================
Comprehensive pytest tests for Part 1 of the Vampire Attack WSN simulator.

Coverage
--------
- Node creation, energy, counters, liveness, neighbors, reset
- Network node management, distance, neighbor discovery, sink
- EnergyModel calculations, transmit operation, dead-node behaviour
"""

from __future__ import annotations

import math
import pytest

from core.node import Node
from core.network import Network
from energy.energy_model import EnergyModel, NodeDeadError, TransmissionResult


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def node_n1() -> Node:
    return Node("N1", 0.0, 0.0, 100.0)


@pytest.fixture
def node_n2() -> Node:
    return Node("N2", 30.0, 0.0, 100.0)


@pytest.fixture
def node_n3() -> Node:
    return Node("N3", 100.0, 0.0, 100.0)


@pytest.fixture
def node_sink() -> Node:
    return Node("SINK", 50.0, 50.0, 1000.0)


@pytest.fixture
def basic_network() -> Network:
    return Network(communication_range=50.0)


@pytest.fixture
def populated_network(node_n1, node_n2, node_n3, node_sink) -> Network:
    net = Network(communication_range=50.0)
    net.add_node(node_n1)
    net.add_node(node_n2)
    net.add_node(node_n3)
    net.add_node(node_sink)
    net.update_neighbors()
    return net


@pytest.fixture
def energy_model() -> EnergyModel:
    return EnergyModel()


# ===========================================================================
# 1. NODE TESTS
# ===========================================================================


class TestNodeCreation:
    """Test 1 — Node creation."""

    def test_node_id(self, node_n1):
        assert node_n1.id == "N1"

    def test_node_x(self, node_n1):
        assert node_n1.x == 0.0

    def test_node_y(self, node_n1):
        assert node_n1.y == 0.0

    def test_node_position(self, node_n1):
        assert node_n1.position == (0.0, 0.0)

    def test_node_initial_energy(self, node_n1):
        assert node_n1.initial_energy == 100.0

    def test_node_current_energy_equals_initial(self, node_n1):
        assert node_n1.energy == 100.0

    def test_node_alive_on_creation(self, node_n1):
        assert node_n1.alive is True

    def test_node_sent_zero(self, node_n1):
        assert node_n1.sent == 0

    def test_node_received_zero(self, node_n1):
        assert node_n1.received == 0

    def test_node_forwarded_zero(self, node_n1):
        assert node_n1.forwarded == 0

    def test_node_no_neighbors_on_creation(self, node_n1):
        assert len(node_n1.neighbors) == 0

    def test_invalid_initial_energy_raises(self):
        with pytest.raises(ValueError):
            Node("BAD", 0, 0, 0)

    def test_invalid_negative_energy_raises(self):
        with pytest.raises(ValueError):
            Node("BAD", 0, 0, -10)

    def test_position_is_tuple(self, node_n1):
        pos = node_n1.position
        assert isinstance(pos, tuple)
        assert len(pos) == 2

    def test_string_id(self):
        n = Node("SINK", 10, 20, 500)
        assert n.id == "SINK"
        assert n.x == 10.0
        assert n.y == 20.0


class TestNodeEnergyConsumption:
    """Test 2 — Partial energy consumption."""

    def test_energy_decreases(self, node_n1):
        node_n1.consume_energy(25)
        assert node_n1.energy == 75.0

    def test_alive_remains_true(self, node_n1):
        node_n1.consume_energy(25)
        assert node_n1.alive is True

    def test_initial_energy_unchanged(self, node_n1):
        node_n1.consume_energy(25)
        assert node_n1.initial_energy == 100.0

    def test_multiple_consumptions(self, node_n1):
        node_n1.consume_energy(30)
        node_n1.consume_energy(30)
        assert node_n1.energy == 40.0


class TestNodeExactDepletion:
    """Test 3 — Exact battery depletion."""

    def test_energy_zero(self, node_n1):
        node_n1.consume_energy(100)
        assert node_n1.energy == 0.0

    def test_alive_false_after_exact_depletion(self, node_n1):
        node_n1.consume_energy(100)
        assert node_n1.alive is False


class TestNodeExcessiveConsumption:
    """Test 4 — Consuming more than remaining energy."""

    def test_energy_clamps_to_zero(self, node_n1):
        node_n1.consume_energy(9999)
        assert node_n1.energy == 0.0

    def test_energy_never_negative(self, node_n1):
        node_n1.consume_energy(9999)
        assert node_n1.energy >= 0.0

    def test_alive_false_after_excess(self, node_n1):
        node_n1.consume_energy(9999)
        assert node_n1.alive is False

    def test_partial_then_excess(self, node_n1):
        node_n1.consume_energy(80)
        node_n1.consume_energy(999)
        assert node_n1.energy == 0.0


class TestNodeInvalidConsumption:
    """Test 5 — Invalid / negative energy consumption."""

    def test_negative_amount_ignored(self, node_n1):
        node_n1.consume_energy(-50)
        assert node_n1.energy == 100.0

    def test_zero_amount_ignored(self, node_n1):
        node_n1.consume_energy(0)
        assert node_n1.energy == 100.0

    def test_alive_not_affected_by_invalid(self, node_n1):
        node_n1.consume_energy(-50)
        assert node_n1.alive is True


class TestNodeNeighborManagement:
    """Test 6 — Neighbor add / remove / deduplication."""

    def test_add_neighbor(self, node_n1):
        node_n1.add_neighbor("N2")
        assert "N2" in node_n1.neighbors

    def test_no_duplicate_neighbors(self, node_n1):
        node_n1.add_neighbor("N2")
        node_n1.add_neighbor("N2")
        assert len([n for n in node_n1.neighbors if n == "N2"]) == 1

    def test_remove_neighbor(self, node_n1):
        node_n1.add_neighbor("N2")
        node_n1.remove_neighbor("N2")
        assert "N2" not in node_n1.neighbors

    def test_remove_nonexistent_neighbor_silently(self, node_n1):
        # Should not raise
        node_n1.remove_neighbor("GHOST")

    def test_multiple_different_neighbors(self, node_n1):
        node_n1.add_neighbor("N2")
        node_n1.add_neighbor("N3")
        assert "N2" in node_n1.neighbors
        assert "N3" in node_n1.neighbors
        assert len(node_n1.neighbors) == 2


class TestNodeReset:
    """Test for Node.reset()."""

    def test_reset_restores_energy(self, node_n1):
        node_n1.consume_energy(60)
        node_n1.reset()
        assert node_n1.energy == node_n1.initial_energy

    def test_reset_restores_alive(self, node_n1):
        node_n1.consume_energy(100)
        node_n1.reset()
        assert node_n1.alive is True

    def test_reset_clears_counters(self, node_n1):
        node_n1.sent = 5
        node_n1.received = 3
        node_n1.forwarded = 2
        node_n1.reset()
        assert node_n1.sent == 0
        assert node_n1.received == 0
        assert node_n1.forwarded == 0

    def test_reset_clears_neighbors(self, node_n1):
        node_n1.add_neighbor("N2")
        node_n1.reset()
        assert len(node_n1.neighbors) == 0


# ===========================================================================
# 2. NETWORK TESTS
# ===========================================================================


class TestNetworkAddNode:
    """Test 7 — add_node()."""

    def test_add_single_node(self, basic_network, node_n1):
        basic_network.add_node(node_n1)
        assert "N1" in basic_network.nodes

    def test_add_multiple_nodes(self, basic_network, node_n1, node_n2):
        basic_network.add_node(node_n1)
        basic_network.add_node(node_n2)
        assert len(basic_network.nodes) == 2

    def test_node_stored_by_id(self, basic_network, node_n1):
        basic_network.add_node(node_n1)
        assert basic_network.nodes["N1"] is node_n1


class TestNetworkGetNode:
    """Test 8 — get_node() with valid IDs."""

    def test_get_existing_node(self, basic_network, node_n1):
        basic_network.add_node(node_n1)
        assert basic_network.get_node("N1") is node_n1

    def test_get_node_returns_correct_object(self, basic_network, node_n1, node_n2):
        basic_network.add_node(node_n1)
        basic_network.add_node(node_n2)
        assert basic_network.get_node("N2") is node_n2


class TestNetworkGetNodeInvalid:
    """Test 9 — get_node() with non-existent IDs."""

    def test_get_nonexistent_returns_none(self, basic_network):
        result = basic_network.get_node("GHOST")
        assert result is None

    def test_get_nonexistent_empty_network(self, basic_network):
        assert basic_network.get_node("N1") is None


class TestNetworkDistance:
    """Test 10 — distance()."""

    def test_distance_3_4_5_triangle(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        b = Node("B", 3, 4, 100)
        net.add_node(a)
        net.add_node(b)
        assert net.distance(a, b) == pytest.approx(5.0)

    def test_distance_by_node_id(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        b = Node("B", 3, 4, 100)
        net.add_node(a)
        net.add_node(b)
        assert net.distance("A", "B") == pytest.approx(5.0)

    def test_distance_same_node_zero(self):
        net = Network(communication_range=100)
        a = Node("A", 5, 5, 100)
        net.add_node(a)
        assert net.distance(a, a) == pytest.approx(0.0)

    def test_distance_symmetric(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        b = Node("B", 3, 4, 100)
        net.add_node(a)
        net.add_node(b)
        assert net.distance(a, b) == pytest.approx(net.distance(b, a))

    def test_distance_mixed_node_and_string(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        b = Node("B", 3, 4, 100)
        net.add_node(a)
        net.add_node(b)
        assert net.distance(a, "B") == pytest.approx(5.0)

    def test_distance_invalid_id_raises(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        net.add_node(a)
        with pytest.raises(KeyError):
            net.distance("A", "GHOST")

    def test_distance_invalid_type_raises(self):
        net = Network(communication_range=100)
        with pytest.raises(TypeError):
            net.distance(42, 99)  # type: ignore[arg-type]


class TestNetworkCommunicationRange:
    """Test 11 — Nodes within / outside communication range."""

    def test_nodes_within_range_are_neighbors(self, populated_network):
        # N1=(0,0), N2=(30,0) → distance 30 ≤ 50
        neighbors = populated_network.get_neighbors("N1")
        neighbor_ids = {n.id for n in neighbors}
        assert "N2" in neighbor_ids

    def test_nodes_outside_range_not_neighbors(self, populated_network):
        # N1=(0,0), N3=(100,0) → distance 100 > 50
        neighbors = populated_network.get_neighbors("N1")
        neighbor_ids = {n.id for n in neighbors}
        assert "N3" not in neighbor_ids

    def test_exact_range_boundary_is_neighbor(self):
        net = Network(communication_range=50.0)
        a = Node("A", 0, 0, 100)
        b = Node("B", 50, 0, 100)  # exactly at range boundary
        net.add_node(a)
        net.add_node(b)
        net.update_neighbors()
        assert "B" in a.neighbors
        assert "A" in b.neighbors

    def test_just_outside_range_not_neighbor(self):
        net = Network(communication_range=50.0)
        a = Node("A", 0, 0, 100)
        b = Node("B", 50.01, 0, 100)
        net.add_node(a)
        net.add_node(b)
        net.update_neighbors()
        assert "B" not in a.neighbors


class TestNetworkBidirectionalNeighbors:
    """Test 12 — Bidirectional neighbor relationships."""

    def test_n1_has_n2_as_neighbor(self, populated_network):
        assert "N2" in populated_network.get_node("N1").neighbors

    def test_n2_has_n1_as_neighbor(self, populated_network):
        assert "N1" in populated_network.get_node("N2").neighbors

    def test_symmetry_general(self):
        net = Network(communication_range=100)
        a = Node("A", 0, 0, 100)
        b = Node("B", 40, 0, 100)
        c = Node("C", 80, 0, 100)
        for n in (a, b, c):
            net.add_node(n)
        net.update_neighbors()

        # B is 80 units from A and 40 units from C
        assert "B" in a.neighbors and "A" in b.neighbors
        assert "C" in b.neighbors and "B" in c.neighbors


class TestNetworkNeighborRebuilding:
    """Test 13 — Stale neighbors are removed after rebuild."""

    def test_rebuild_removes_stale_neighbors(self):
        net = Network(communication_range=50)
        a = Node("A", 0, 0, 100)
        b = Node("B", 30, 0, 100)
        net.add_node(a)
        net.add_node(b)
        net.update_neighbors()

        assert "B" in a.neighbors  # they are neighbors initially

        # Now move B far away (simulate position change)
        b._x = 200
        net.update_neighbors()

        assert "B" not in a.neighbors  # stale relationship removed

    def test_new_node_picked_up_after_rebuild(self):
        net = Network(communication_range=50)
        a = Node("A", 0, 0, 100)
        net.add_node(a)
        net.update_neighbors()

        c = Node("C", 20, 0, 100)
        net.add_node(c)
        net.update_neighbors()

        assert "C" in a.neighbors


class TestNetworkDeadNeighborExclusion:
    """Test 14 — Dead nodes excluded from get_neighbors()."""

    def test_dead_node_not_in_get_neighbors(self, populated_network):
        # N1 and N2 are neighbors; kill N2
        populated_network.get_node("N2").consume_energy(100)
        assert not populated_network.get_node("N2").alive

        neighbors = populated_network.get_neighbors("N1")
        neighbor_ids = {n.id for n in neighbors}
        assert "N2" not in neighbor_ids

    def test_dead_node_still_in_nodes_dict(self, populated_network):
        populated_network.get_node("N2").consume_energy(100)
        assert "N2" in populated_network.nodes

    def test_alive_neighbors_still_returned(self, populated_network):
        # N1 neighbors: N2 (at 30,0) and SINK (at 50,50 → dist ~70.7 > 50? no)
        # Let's check which nodes N1 actually can reach at range 50
        # N1=(0,0), N2=(30,0)=30, SINK=(50,50)≈70.7, N3=(100,0)=100
        # So N1 should only see N2 as neighbor.
        # Kill N2, then no alive neighbors for N1.
        populated_network.get_node("N2").consume_energy(100)
        neighbors = populated_network.get_neighbors("N1")
        # No alive neighbor should remain for N1 in this topology
        assert all(n.alive for n in neighbors)


class TestNetworkSink:
    """Test 15 — Sink / Base Station."""

    def test_set_valid_sink(self, basic_network, node_sink):
        basic_network.add_node(node_sink)
        basic_network.set_sink("SINK")
        assert basic_network.sink is node_sink

    def test_sink_initially_none(self, basic_network):
        assert basic_network.sink is None

    def test_set_invalid_sink_raises(self, basic_network):
        with pytest.raises(KeyError):
            basic_network.set_sink("GHOST")

    def test_sink_is_same_node_object(self, basic_network, node_sink):
        basic_network.add_node(node_sink)
        basic_network.set_sink("SINK")
        # sink property should be the exact same object
        assert basic_network.sink is basic_network.get_node("SINK")


# ===========================================================================
# 3. ENERGY MODEL TESTS
# ===========================================================================


class TestTransmissionEnergyCalculation:
    """Test 16 — Transmission energy formula."""

    def test_formula_manual(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        packet_size = 4000  # bits
        distance = 10.0    # metres
        expected = 50e-9 * 4000 + 100e-12 * 4000 * 10.0 ** 2
        assert e.transmission_energy(packet_size, distance) == pytest.approx(expected)

    def test_zero_distance_no_amp_cost(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        tx = e.transmission_energy(4000, 0)
        assert tx == pytest.approx(50e-9 * 4000)

    def test_larger_distance_more_energy(self):
        e = EnergyModel()
        tx_near = e.transmission_energy(4000, 10)
        tx_far = e.transmission_energy(4000, 100)
        assert tx_far > tx_near

    def test_zero_packet_size(self):
        e = EnergyModel()
        assert e.transmission_energy(0, 10) == pytest.approx(0.0)

    def test_negative_packet_size_raises(self):
        with pytest.raises(ValueError):
            EnergyModel().transmission_energy(-1, 10)

    def test_negative_distance_raises(self):
        with pytest.raises(ValueError):
            EnergyModel().transmission_energy(4000, -1)


class TestReceptionEnergyCalculation:
    """Test 17 — Reception energy formula."""

    def test_formula_manual(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        packet_size = 4000
        expected = 50e-9 * 4000
        assert e.reception_energy(packet_size) == pytest.approx(expected)

    def test_zero_packet_size(self):
        assert EnergyModel().reception_energy(0) == pytest.approx(0.0)

    def test_negative_packet_size_raises(self):
        with pytest.raises(ValueError):
            EnergyModel().reception_energy(-1)

    def test_rx_less_than_tx_for_nonzero_distance(self):
        e = EnergyModel()
        tx = e.transmission_energy(4000, 10)
        rx = e.reception_energy(4000)
        assert rx < tx


class TestTransmitOperation:
    """Test 18 — transmit() updates energy and counters."""

    def test_sender_energy_decreases(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert sender.energy < 1.0

    def test_receiver_energy_decreases(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert receiver.energy < 1.0

    def test_sender_sent_incremented(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert sender.sent == 1

    def test_receiver_received_incremented(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert receiver.received == 1

    def test_forwarded_not_incremented(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert sender.forwarded == 0
        assert receiver.forwarded == 0

    def test_returns_transmission_result(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        result = energy_model.transmit(sender, receiver, 4000, 10.0)
        assert isinstance(result, TransmissionResult)

    def test_result_contains_correct_energies(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        result = energy_model.transmit(sender, receiver, 4000, 10.0)
        assert result.tx_energy == pytest.approx(
            energy_model.transmission_energy(4000, 10.0)
        )
        assert result.rx_energy == pytest.approx(
            energy_model.reception_energy(4000)
        )

    def test_multiple_transmissions_accumulate_counters(self, energy_model):
        sender = Node("S", 0, 0, 10.0)
        receiver = Node("R", 10, 0, 10.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        energy_model.transmit(sender, receiver, 4000, 10.0)
        assert sender.sent == 2
        assert receiver.received == 2


class TestTransmissionCausesDeath:
    """Test 19 — Transmission can deplete sender battery."""

    def test_sender_dies_after_transmit(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        # Give sender exactly the transmission energy it needs to die
        tx_cost = e.transmission_energy(4000, 10)
        sender = Node("S", 0, 0, tx_cost)
        receiver = Node("R", 10, 0, 1.0)
        result = e.transmit(sender, receiver, 4000, 10.0)
        assert sender.alive is False
        assert result.sender_alive is False

    def test_sender_energy_zero_after_fatal_transmit(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        tx_cost = e.transmission_energy(4000, 10)
        sender = Node("S", 0, 0, tx_cost)
        receiver = Node("R", 10, 0, 1.0)
        e.transmit(sender, receiver, 4000, 10.0)
        assert sender.energy == 0.0


class TestDeadSender:
    """Test 20 — Dead sender raises NodeDeadError."""

    def test_dead_sender_raises(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        sender.consume_energy(1.0)  # kill sender
        with pytest.raises(NodeDeadError) as exc_info:
            energy_model.transmit(sender, receiver, 4000, 10.0)
        assert exc_info.value.role == "sender"
        assert exc_info.value.node_id == "S"

    def test_dead_sender_receiver_unchanged(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        sender.consume_energy(1.0)
        try:
            energy_model.transmit(sender, receiver, 4000, 10.0)
        except NodeDeadError:
            pass
        # Receiver should be untouched
        assert receiver.energy == 1.0
        assert receiver.received == 0


class TestDeadReceiver:
    """Test 21 — Dead receiver raises NodeDeadError."""

    def test_dead_receiver_raises(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        receiver.consume_energy(1.0)  # kill receiver
        with pytest.raises(NodeDeadError) as exc_info:
            energy_model.transmit(sender, receiver, 4000, 10.0)
        assert exc_info.value.role == "receiver"
        assert exc_info.value.node_id == "R"

    def test_dead_receiver_sender_unchanged(self, energy_model):
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, 1.0)
        receiver.consume_energy(1.0)
        original_energy = sender.energy
        try:
            energy_model.transmit(sender, receiver, 4000, 10.0)
        except NodeDeadError:
            pass
        # Sender should be untouched (dead check happens before consumption)
        assert sender.energy == original_energy
        assert sender.sent == 0


class TestEnergyNeverNegative:
    """Test 22 — Energy is always >= 0."""

    def test_consume_more_than_available(self):
        n = Node("N", 0, 0, 10.0)
        n.consume_energy(9999)
        assert n.energy >= 0.0

    def test_energy_exactly_zero_after_max_consumption(self):
        n = Node("N", 0, 0, 10.0)
        n.consume_energy(9999)
        assert n.energy == 0.0

    def test_transmit_clamped_by_node(self):
        # Give sender tiny energy so tx will far exceed it
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        tx_cost = e.transmission_energy(4000, 10)
        # Give sender half the needed energy
        sender = Node("S", 0, 0, tx_cost / 2)
        receiver = Node("R", 10, 0, 1.0)
        e.transmit(sender, receiver, 4000, 10.0)
        assert sender.energy >= 0.0

    def test_receive_clamped_by_node(self):
        e = EnergyModel(e_elec=50e-9, e_amp=100e-12)
        rx_cost = e.reception_energy(4000)
        sender = Node("S", 0, 0, 1.0)
        receiver = Node("R", 10, 0, rx_cost / 2)  # tiny energy
        e.transmit(sender, receiver, 4000, 10.0)
        assert receiver.energy >= 0.0


# ===========================================================================
# Integration / manual walk-through
# ===========================================================================


class TestIntegration:
    """End-to-end integration test covering the full Part 1 workflow."""

    def test_full_workflow(self):
        # 1. Create a Network
        net = Network(communication_range=50.0)

        # 2. Create several Nodes
        n1 = Node("N1", 0, 0, 0.5)
        n2 = Node("N2", 30, 0, 0.5)
        n3 = Node("N3", 100, 0, 0.5)
        sink = Node("SINK", 15, 0, 1.0)

        # 3. Add them to the Network
        for node in (n1, n2, n3, sink):
            net.add_node(node)

        # 4. Assign Sink
        net.set_sink("SINK")
        assert net.sink is sink

        # 5. Update neighbors
        net.update_neighbors()

        # 6. Check neighbors (N1-N2 ≤50, SINK at 15 ≤50 from N1 & N2)
        n1_neighbors = {n.id for n in net.get_neighbors("N1")}
        assert "N2" in n1_neighbors
        assert "N3" not in n1_neighbors  # 100 > 50

        # 7. Distance check
        dist = net.distance("N1", "N2")
        assert dist == pytest.approx(30.0)
        dist_345 = net.distance(Node("A", 0, 0, 1), Node("B", 3, 4, 1))
        assert dist_345 == pytest.approx(5.0)

        # 8. Energy transmission
        em = EnergyModel()
        result = em.transmit(n1, n2, 4000, dist)
        assert n1.energy < 0.5
        assert n2.energy < 0.5
        assert n1.sent == 1
        assert n2.received == 1
        assert isinstance(result, TransmissionResult)

        # 9. Deplete n2 completely
        n2.consume_energy(n2.energy)
        assert n2.alive is False

        # 10. Dead node not returned as active neighbor
        alive_neighbors = net.get_neighbors("N1")
        assert all(n.alive for n in alive_neighbors)
        assert n2 not in alive_neighbors

        # 11. Dead node still in nodes dict
        assert "N2" in net.nodes

        # 12. Dead sender raises
        with pytest.raises(NodeDeadError):
            em.transmit(n2, n1, 4000, dist)

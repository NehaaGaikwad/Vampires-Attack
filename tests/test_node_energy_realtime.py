from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from threading import Event

import pytest

from PyQt5.QtWidgets import QApplication

from attacks.base import AttackIntensity
from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from core.packet import Packet, PacketStatus
from energy.energy_model import EnergyModel, NodeDeadError
from routing.dijkstra import shortest_path
from routing.router import Router
from security.detector import AttackDetector
from security.mitigation import MitigationManager
from simulator import Simulator
from ui.main_window import SimulatorMainWindow
from visualization.live_network_view import LiveNetworkView


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _build_test_network() -> Network:
    """Topology with primary and alternate routes:
    Primary route: A -> B -> C -> SINK
    Alternate route: A -> B -> D -> SINK
    """
    network = Network(communication_range=15.0)
    nodes = (
        Node("A", 0.0, 0.0, 100.0),
        Node("B", 10.0, 0.0, 100.0),
        Node("C", 20.0, 0.0, 100.0),
        Node("D", 10.0, 10.0, 100.0),
        Node("SINK", 30.0, 0.0, 500.0),
    )
    for node in nodes:
        network.add_node(node)
    network.set_sink("SINK")
    network.update_neighbors()
    # Explicit topology links
    for node in nodes:
        node.neighbors.clear()
    for u, v in (
        ("A", "B"),
        ("B", "C"),
        ("C", "SINK"),
        ("B", "D"),
        ("D", "SINK"),
    ):
        network.nodes[u].add_neighbor(v)
        network.nodes[v].add_neighbor(u)
    return network


# ---------------------------------------------------------------------------
# 1. Configured Initial Energy
# ---------------------------------------------------------------------------
def test_node_starts_with_configured_initial_energy() -> None:
    node = Node("N1", 0.0, 0.0, 100.0)
    assert node.initial_energy == 100.0
    assert node.energy == 100.0
    assert node.alive is True
    assert node.is_active is True
    assert node.is_dead is False


# ---------------------------------------------------------------------------
# 2. Transmission & Reception Reduces Energy
# ---------------------------------------------------------------------------
def test_transmission_and_reception_reduces_energy_correctly() -> None:
    network = _build_test_network()
    energy_model = EnergyModel(e_elec=0.001, e_amp=0.0001)
    sender = network.get_node("A")
    receiver = network.get_node("B")
    dist = network.distance(sender, receiver)

    tx_cost = energy_model.transmission_energy(packet_size=1000, distance=dist)
    rx_cost = energy_model.reception_energy(packet_size=1000)

    result = energy_model.transmit(
        sender=sender,
        receiver=receiver,
        packet_size=1000,
        distance=dist,
    )

    assert result.tx_energy == pytest.approx(tx_cost)
    assert result.rx_energy == pytest.approx(rx_cost)
    assert sender.energy == pytest.approx(100.0 - tx_cost)
    assert receiver.energy == pytest.approx(100.0 - rx_cost)
    assert sender.sent == 1
    assert receiver.received == 1


# ---------------------------------------------------------------------------
# 3. Real-Time Displayed Energy Updates
# ---------------------------------------------------------------------------
def test_displayed_energy_updates_in_real_time_with_exact_values() -> None:
    app = _app()
    network = _build_test_network()
    view = LiveNetworkView(network)

    # Initial state
    assert view.get_node_energy_text("A") == "100/100 J"
    assert view.get_node_energy_text("SINK") == "500/500 J"

    # Simulated step 1: energy drops to 97.5 J
    view.show_progress(
        {
            "route": ["A", "B"],
            "sender": "A",
            "receiver": "B",
            "node_energy": {"A": 97.5, "B": 99.8},
            "node_alive": {"A": True, "B": True},
        }
    )
    assert view.get_node_energy_text("A") == "97.5/100 J"

    # Simulated step 2: energy drops to 82 J
    view.show_progress(
        {
            "route": ["A", "B", "C"],
            "sender": "B",
            "receiver": "C",
            "node_energy": {"A": 82.0, "B": 95.0},
            "node_alive": {"A": True, "B": True},
        }
    )
    assert view.get_node_energy_text("A") == "82/100 J"

    # Simulated step 3: node energy depletes to 0 J
    view.show_progress(
        {
            "route": ["A", "B", "C"],
            "sender": "B",
            "receiver": "C",
            "node_energy": {"A": 0.0},
            "node_alive": {"A": False},
        }
    )
    assert view.get_node_energy_text("A") == "DEAD · 0 J"
    view.close()
    app.processEvents()


# ---------------------------------------------------------------------------
# 4. Energy Never Negative (Clamps to 0)
# ---------------------------------------------------------------------------
def test_energy_never_becomes_negative_and_clamps_to_zero() -> None:
    node = Node("N1", 0.0, 0.0, 10.0)
    node.consume_energy(5.0)
    assert node.energy == 5.0

    # Over-consumption clamps to 0
    node.consume_energy(100.0)
    assert node.energy == 0.0

    # Negative deduction amounts are ignored
    node.consume_energy(-50.0)
    assert node.energy == 0.0


# ---------------------------------------------------------------------------
# 5. Node Reaching 0 J Marked DEAD
# ---------------------------------------------------------------------------
def test_node_reaching_zero_energy_is_marked_dead() -> None:
    node = Node("N1", 0.0, 0.0, 20.0)
    assert node.alive is True
    assert node.is_active is True
    assert node.is_dead is False

    node.consume_energy(20.0)
    assert node.energy == 0.0
    assert node.alive is False
    assert node.is_active is False
    assert node.is_dead is True


# ---------------------------------------------------------------------------
# 6. Dead Nodes Cannot Forward or Transmit Packets
# ---------------------------------------------------------------------------
def test_dead_nodes_cannot_transmit_or_forward_packets() -> None:
    network = _build_test_network()
    energy_model = EnergyModel()
    router = Router(network, energy_model)

    sender = network.get_node("A")
    receiver = network.get_node("B")

    # Kill sender
    sender.consume_energy(sender.energy)
    assert not sender.alive

    with pytest.raises(NodeDeadError) as exc_info:
        energy_model.transmit(sender, receiver, 1000, 10.0)
    assert "sender" in str(exc_info.value)

    # Route packet starting from dead node fails immediately
    packet = Packet("A", "SINK")
    result = router.route_packet(packet)
    assert result.status is PacketStatus.FAILED
    assert result.failed is True
    assert result.delivered is False


# ---------------------------------------------------------------------------
# 7. Routing Algorithm Avoids Dead Nodes
# ---------------------------------------------------------------------------
def test_routing_algorithm_avoids_dead_nodes() -> None:
    network = _build_test_network()
    # Before death: optimal path is A -> B -> C -> SINK
    path_before = shortest_path(network, "A", "SINK")
    assert path_before == ["A", "B", "C", "SINK"]

    # Kill node C
    network.get_node("C").consume_energy(100.0)
    assert not network.get_node("C").alive

    # Dijkstra automatically excludes dead node C and selects A -> B -> D -> SINK
    path_after = shortest_path(network, "A", "SINK")
    assert path_after == ["A", "B", "D", "SINK"]
    assert "C" not in path_after


# ---------------------------------------------------------------------------
# 8. Automatic Alternate Route When Active Node Dies
# ---------------------------------------------------------------------------
def test_automatic_reroute_when_node_dies_in_flight() -> None:
    network = _build_test_network()
    energy_model = EnergyModel(e_elec=0.001, e_amp=0.0001)
    simulator = Simulator(network, Router(network, energy_model), energy_model)

    events: list[dict[str, object]] = []
    c_killed = False

    def on_progress(event: dict[str, object]) -> None:
        nonlocal c_killed
        events.append(event.copy())
        # While packet is at B, node C dies
        if event["receiver"] == "B" and not c_killed:
            network.get_node("C").consume_energy(network.get_node("C").energy)
            c_killed = True

    packet = simulator.run_packet("A", "SINK", packet_size=1000, ttl=10, on_progress=on_progress)

    assert c_killed
    assert packet.status is PacketStatus.DELIVERED
    assert packet.route == ["A", "B", "D", "SINK"]
    assert "C" not in packet.route
    assert not network.get_node("C").alive


# ---------------------------------------------------------------------------
# 9. Graceful Drop When No Alternative Route Exists
# ---------------------------------------------------------------------------
def test_packet_dropped_gracefully_when_no_alternative_route_exists() -> None:
    network = _build_test_network()
    energy_model = EnergyModel()
    simulator = Simulator(network, Router(network, energy_model), energy_model)

    # Kill both bottleneck options C and D
    network.get_node("C").consume_energy(100.0)
    network.get_node("D").consume_energy(100.0)

    packet = simulator.run_packet("A", "SINK", packet_size=1000, ttl=10)

    assert packet.status is PacketStatus.FAILED
    assert packet.failed is True
    assert packet.delivered is False
    assert simulator.get_results()[-1]["packet_status"] == "FAILED"


# ---------------------------------------------------------------------------
# 10. Attack Simulations and Mitigation Respect Dead Nodes
# ---------------------------------------------------------------------------
def test_attacks_and_mitigation_respect_dead_nodes() -> None:
    network = _build_test_network()

    # 1. Stretch Attack: when node C is dead, stretch cannot detour through C
    network.get_node("C").consume_energy(100.0)
    stretch = StretchAttack("B", intensity=AttackIntensity.HIGH)
    route = ["A", "B", "D", "SINK"]
    stretched = stretch.apply(route, network=network, ttl=10)
    assert "C" not in stretched

    # 2. Carousel Attack: when node C is dead, partner selection avoids C
    carousel = CarouselAttack("B", intensity=AttackIntensity.LOW)
    carousel_route = carousel.apply(route, network=network, ttl=10)
    assert "C" not in carousel_route

    # 3. MitigationManager: recalculated route avoids dead node
    mitigation = MitigationManager()
    mitigation.isolate_node("A", reasons=["suspicious"])
    safe_route = mitigation.recalculate_route(network, "B", "SINK")
    assert safe_route == ["B", "D", "SINK"]
    assert "C" not in safe_route
    assert "A" not in safe_route


# ---------------------------------------------------------------------------
# 11. Repeated/Duplicate Events Do Not Deduct Duplicate Energy
# ---------------------------------------------------------------------------
def test_repeated_or_duplicate_events_do_not_deduct_energy() -> None:
    app = _app()
    network = _build_test_network()
    view = LiveNetworkView(network)

    initial_a = network.get_node("A").energy

    event = {
        "route": ["A", "B"],
        "sender": "A",
        "receiver": "B",
        "status": "IN_TRANSIT",
        "hops": 1,
        "node_energy": {"A": 95.0, "B": 99.0},
        "node_alive": {"A": True, "B": True},
    }

    # Process event first time
    view.show_progress(event)
    assert view.get_node_energy_text("A") == "95/100 J"

    # Process duplicate/repeated event
    view.show_progress(event)
    view.show_progress(event)

    # Frontend display stays synchronized and backend energy was untouched by UI events
    assert view.get_node_energy_text("A") == "95/100 J"
    assert network.get_node("A").energy == initial_a
    view.close()
    app.processEvents()


# ---------------------------------------------------------------------------
# 12. Network Helper: get_alive_nodes
# ---------------------------------------------------------------------------
def test_network_get_alive_nodes_helper() -> None:
    network = _build_test_network()
    assert len(network.get_alive_nodes()) == 5

    network.get_node("C").consume_energy(100.0)
    alive_ids = {node.id for node in network.get_alive_nodes()}
    assert alive_ids == {"A", "B", "D", "SINK"}
    assert "C" not in alive_ids

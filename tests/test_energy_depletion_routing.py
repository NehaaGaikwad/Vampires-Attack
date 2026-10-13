from __future__ import annotations

import os
from threading import Event

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from core.packet import PacketStatus
from energy.energy_model import EnergyModel, NodeDeadError
from routing.router import Router
from simulator import Simulator
from ui.main_window import SimulatorMainWindow


def _network_with_alternate_path() -> Network:
    network = Network(communication_range=10.0)
    nodes = (
        Node("A", 0.0, 0.0, 100.0),
        Node("B", 1.0, 0.0, 100.0),
        Node("C", 2.0, 0.0, 100.0),
        Node("D", 1.0, 1.0, 100.0),
        Node("SINK", 3.0, 0.0, 100.0),
    )
    for node in nodes:
        network.add_node(node)
    network.set_sink("SINK")
    network.update_neighbors()
    for node in nodes:
        node.neighbors.clear()
    for left, right in (
        ("A", "B"),
        ("B", "C"),
        ("C", "SINK"),
        ("B", "D"),
        ("D", "SINK"),
    ):
        network.nodes[left].add_neighbor(right)
        network.nodes[right].add_neighbor(left)
    return network


def _simulator(
    network: Network,
    *,
    mode: str,
) -> Simulator:
    energy = EnergyModel()
    attack = (
        StretchAttack("C")
        if mode == "stretch"
        else CarouselAttack("C")
        if mode == "carousel"
        else None
    )
    return Simulator(network, Router(network, energy), energy, attack)


def test_radio_energy_depletes_node_and_blocks_later_transmissions() -> None:
    network = Network(communication_range=2.0)
    sender = Node("A", 0.0, 0.0, 1.0)
    receiver = Node("SINK", 1.0, 0.0, 5.0)
    network.add_node(sender)
    network.add_node(receiver)
    network.set_sink("SINK")
    network.update_neighbors()
    energy = EnergyModel(e_elec=1.0, e_amp=1e-12)
    simulator = Simulator(network, Router(network, energy), energy)

    first_packet = simulator.run_packet("A", "SINK", packet_size=1, ttl=2)

    assert first_packet.status is PacketStatus.DELIVERED
    assert sender.energy == 0
    assert sender.alive is False
    assert sender.sent == 1
    assert sum(node.energy for node in network.nodes.values()) == pytest.approx(
        sender.energy + receiver.energy
    )
    with pytest.raises(NodeDeadError):
        energy.transmit(sender, receiver, packet_size=1, distance=1)

    second_packet = simulator.run_packet("A", "SINK", packet_size=1, ttl=2)
    assert second_packet.status is PacketStatus.FAILED
    assert second_packet.delivered is False
    assert sender.sent == 1


def test_cached_next_hop_is_rejected_when_source_dies() -> None:
    network = _network_with_alternate_path()
    router = Router(network, EnergyModel())

    assert router.get_next_hop("A", "SINK") == "B"
    network.nodes["A"].consume_energy(network.nodes["A"].energy)

    assert router.get_next_hop("A", "SINK") is None


@pytest.mark.parametrize("mode", ["normal", "stretch", "carousel"])
def test_dead_route_node_is_replanned_around_in_every_mode(mode: str) -> None:
    network = _network_with_alternate_path()
    simulator = _simulator(network, mode=mode)
    progress: list[dict[str, object]] = []
    killed = False

    def on_progress(event: dict[str, object]) -> None:
        nonlocal killed
        progress.append(event.copy())
        if event["sender"] == "A" and not killed:
            network.nodes["C"].consume_energy(network.nodes["C"].energy)
            killed = True

    packet = simulator.run_packet(
        "A",
        "SINK",
        packet_size=1000,
        ttl=12,
        on_progress=on_progress,
    )

    assert killed
    assert not network.nodes["C"].alive
    assert packet.status is PacketStatus.DELIVERED
    assert packet.route == ["A", "B", "D", "SINK"]
    assert "C" not in packet.route
    assert sum(node.energy for node in network.nodes.values()) == pytest.approx(
        sum(progress[-1]["node_energy"].values())
    )
    assert progress[-1]["node_alive"]["C"] is False


@pytest.mark.parametrize("mode", ["normal", "stretch", "carousel"])
def test_unreachable_after_node_death_fails_without_delivery(mode: str) -> None:
    network = _network_with_alternate_path()
    simulator = _simulator(network, mode=mode)
    killed = False

    def on_progress(event: dict[str, object]) -> None:
        nonlocal killed
        if event["sender"] == "A" and not killed:
            for node_id in ("C", "D"):
                node = network.nodes[node_id]
                node.consume_energy(node.energy)
            killed = True

    packet = simulator.run_packet(
        "A",
        "SINK",
        packet_size=1000,
        ttl=12,
        on_progress=on_progress,
    )

    assert killed
    assert packet.status is PacketStatus.FAILED
    assert packet.failed
    assert packet.delivered is False
    assert simulator.get_results()[-1]["packet_status"] == "FAILED"


@pytest.mark.parametrize("mode", ["normal", "stretch", "carousel"])
def test_reset_restores_energy_for_a_second_run(mode: str) -> None:
    network = _network_with_alternate_path()
    simulator = _simulator(network, mode=mode)
    initial_energy = sum(node.initial_energy for node in network.nodes.values())
    first_packet = simulator.run_packet("A", "SINK", packet_size=1000, ttl=12)
    assert sum(node.energy for node in network.nodes.values()) < initial_energy

    simulator.reset()

    assert sum(node.energy for node in network.nodes.values()) == initial_energy
    assert all(node.alive for node in network.nodes.values())
    assert simulator.get_results() == []
    second_packet = simulator.run_packet("A", "SINK", packet_size=1000, ttl=12)
    assert second_packet.status is first_packet.status
    assert sum(node.energy for node in network.nodes.values()) < initial_energy


def test_progress_updates_node_status_energy_and_death_log() -> None:
    app = QApplication.instance() or QApplication([])
    network = Network(communication_range=2.0)
    network.add_node(Node("A", 0.0, 0.0, 10.0))
    network.add_node(Node("SINK", 1.0, 0.0, 10.0))
    network.set_sink("SINK")
    network.update_neighbors()
    energy = EnergyModel()
    window = SimulatorMainWindow(Simulator(network, Router(network, energy), energy))
    window._paused = True
    window._active_packet = True
    window._run_energy_start = 20.0
    window._run_alive_start = {"A": True, "SINK": True}
    window._progress_scenario = "Normal"

    window._show_progress(
        window._run_generation,
        {
            "route": ["A", "SINK"],
            "sender": "A",
            "receiver": "SINK",
            "status": "IN_TRANSIT",
            "hops": 1,
            "route_kind": "normal",
            "node_energy": {"A": 0.0, "SINK": 9.9},
            "node_alive": {"A": False, "SINK": True},
            "scenario": "Carousel",
        },
        Event(),
    )

    assert window.hud_energy.text() == "49.5000%"
    assert window.hud_energy_bar.value() == window.readout_energy_bar.value()
    assert window.metric_alive.text() == "1"
    assert window.network_view.node_alive == {"A": False, "SINK": True}
    event_names = [
        window.event_table.item(row, 2).text()
        for row in range(window.event_table.rowCount())
    ]
    assert "NODE DEATH" in event_names
    assert "PACKET HOP" in event_names
    window.close()
    app.processEvents()

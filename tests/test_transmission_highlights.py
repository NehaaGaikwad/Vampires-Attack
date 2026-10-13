from __future__ import annotations

import os
from threading import Event
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from core.network import Network
from core.node import Node
from core.packet import PacketStatus
from energy.energy_model import EnergyModel
from routing.router import Router
from simulator import Simulator
from ui.main_window import SimulatorMainWindow

_APP = QApplication.instance() or QApplication([])


def _window() -> SimulatorMainWindow:
    assert _APP is QApplication.instance()
    network = Network(communication_range=2.0)
    for node_id, x in (("A", 0.0), ("B", 1.0), ("C", 2.0)):
        network.add_node(Node(node_id, x, 0.0, 10.0))
    network.set_sink("C")
    network.update_neighbors()
    energy = EnergyModel()
    window = SimulatorMainWindow(Simulator(network, Router(network, energy), energy))
    window._paused = True
    return window


def _ignore_dialog(*args: str) -> None:
    del args


def _complete_edge(window: SimulatorMainWindow) -> None:
    window.network_view.show_progress(
        {"route": ["A", "B"], "sender": "A", "receiver": "B"}
    )
    window.network_view.set_packet_progress(1.0)


def test_second_transmission_starts_without_previous_highlights() -> None:
    window = _window()
    try:
        _complete_edge(window)
        assert window.network_view.traversed_edges == {("A", "B")}

        window._launch_worker(
            "simulation",
            {"source": "A", "destination": "C", "packet_size": 1000, "ttl": 5},
            description="Running normal simulation",
        )

        assert not window.network_view.traversed_edges
    finally:
        if window._thread is not None:
            window._reset_animation()
        window.close()


def test_comparison_mode_clears_highlights_between_scenarios() -> None:
    window = _window()
    try:
        window._show_progress(
            window._run_generation,
            {
                "route": ["A", "B"],
                "sender": "A",
                "receiver": "B",
                "status": "IN_TRANSIT",
                "hops": 1,
                "route_kind": "normal",
                "scenario": "normal",
            },
            Event(),
        )
        window.network_view.set_packet_progress(1.0)
        assert window.network_view.traversed_edges == {("A", "B")}

        window._show_progress(
            window._run_generation,
            {
                "route": ["B", "C"],
                "sender": "B",
                "receiver": "C",
                "status": "IN_TRANSIT",
                "hops": 1,
                "route_kind": "attacked",
                "scenario": "stretch",
            },
            Event(),
        )
        assert not window.network_view.traversed_edges
    finally:
        window.close()


def test_completion_and_worker_failure_clear_current_highlights() -> None:
    window = _window()
    window._show_message = _ignore_dialog
    failed_packet = SimpleNamespace(
        status=PacketStatus.FAILED,
        hops=1,
        route=["A", "B"],
        ttl=4,
        source="A",
        destination="C",
    )
    try:
        _complete_edge(window)
        window._show_completion(window._run_generation, "simulation", failed_packet)
        assert not window.network_view.traversed_edges

        _complete_edge(window)
        window._show_error(window._run_generation, "test worker failure")
        assert not window.network_view.traversed_edges
    finally:
        window.close()


def test_stale_completion_cannot_clear_new_run_highlights() -> None:
    window = _window()
    failed_packet = SimpleNamespace(
        status=PacketStatus.FAILED,
        hops=0,
        route=["A"],
        ttl=5,
        source="A",
        destination="C",
    )
    try:
        window._run_generation += 1
        _complete_edge(window)
        window._show_completion(
            window._run_generation - 1,
            "simulation",
            failed_packet,
        )
        assert window.network_view.traversed_edges == {("A", "B")}
    finally:
        window.close()

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from core.network import Network
from core.node import Node
from visualization.live_network_view import LiveNetworkView


def test_completed_edges_persist_and_render_after_consecutive_hops() -> None:
    app = QApplication.instance() or QApplication([])
    network = Network(communication_range=2.0)
    for node_id, x in (("A", 0.0), ("B", 1.0), ("C", 2.0)):
        network.add_node(Node(node_id, x, 0.0, 10.0))
    network.update_neighbors()
    view = LiveNetworkView(network)
    view.resize(600, 400)

    view.show_progress({"route": ["A", "B", "C"], "sender": "A", "receiver": "B"})
    view.set_packet_progress(1.0)
    first_edge = ("A", "B")
    assert first_edge in view.traversed_edges

    view.show_progress({"route": ["A", "B", "C"], "sender": "B", "receiver": "C"})
    assert first_edge in view.traversed_edges
    view.set_packet_progress(1.0)
    assert first_edge in view.traversed_edges
    assert ("B", "C") in view.traversed_edges

    image = QImage(view.size(), QImage.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    view.render(painter)
    painter.end()
    green = QColor("#3F9B45")
    edge_midpoints = ((174, 188), (426, 188))
    rendered_colors = [
        image.pixelColor(*point).name() for point in edge_midpoints
    ]
    assert rendered_colors == [green.name(), green.name()]

    view.reset_animation(clear_traversed=False)
    assert view.traversed_edges == {first_edge, ("B", "C")}
    view.reset_animation(clear_traversed=True)
    assert not view.traversed_edges
    view.close()
    app.processEvents()

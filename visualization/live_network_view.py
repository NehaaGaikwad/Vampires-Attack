from __future__ import annotations

from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QWidget

from core.network import Network


class LiveNetworkView(QWidget):
    """Paint the current topology, route, packet position, and node energy."""

    def __init__(self, network: Network, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.network = network
        self.attacker_node_id: str | None = None
        self.route: list[str] = []
        self.normal_route: list[str] = []
        self.route_kind = "normal"
        self.sender_id: str | None = None
        self.receiver_id: str | None = None
        self.packet_progress = 0.0
        self.node_energy: dict[str, float] = {}
        self.setMinimumHeight(300)
        self.setMinimumWidth(420)
        self.setAutoFillBackground(True)

    def set_attacker(self, node_id: str | None) -> None:
        self.attacker_node_id = node_id
        self.update()

    def show_progress(self, event: dict[str, object]) -> None:
        route = event.get("route", [])
        normal_route = event.get("normal_route", [])
        energy = event.get("node_energy", {})
        self.route = list(route) if isinstance(route, list) else []
        self.normal_route = (
            list(normal_route) if isinstance(normal_route, list) else []
        )
        self.route_kind = str(event.get("route_kind", "normal"))
        self.sender_id = str(event["sender"])
        self.receiver_id = str(event["receiver"])
        self.packet_progress = 0.0
        self.node_energy = (
            {str(node_id): float(value) for node_id, value in energy.items()}
            if isinstance(energy, dict)
            else {}
        )
        self.update()

    def set_packet_progress(self, progress: float) -> None:
        self.packet_progress = max(0.0, min(1.0, progress))
        self.update()

    def reset_animation(self) -> None:
        self.route = []
        self.normal_route = []
        self.sender_id = None
        self.receiver_id = None
        self.packet_progress = 0.0
        self.node_energy = {}
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#F8F6F0"))
        painter.setFont(self.font())

        nodes = list(self.network.nodes.values())
        if not nodes:
            painter.setPen(QColor("#292524"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No sensor nodes in network")
            return

        bounds = self.rect().adjusted(48, 30, -48, -54)
        min_x = min(node.x for node in nodes)
        max_x = max(node.x for node in nodes)
        min_y = min(node.y for node in nodes)
        max_y = max(node.y for node in nodes)
        scale_x = bounds.width() / max(max_x - min_x, 1.0)
        scale_y = bounds.height() / max(max_y - min_y, 1.0)
        scale = min(scale_x, scale_y)
        drawing_width = (max_x - min_x) * scale
        drawing_height = (max_y - min_y) * scale
        offset_x = bounds.left() + (bounds.width() - drawing_width) / 2
        offset_y = bounds.top() + (bounds.height() - drawing_height) / 2

        def point(node_id: str) -> QPointF:
            node = self.network.nodes[node_id]
            return QPointF(
                offset_x + (node.x - min_x) * scale,
                offset_y + (max_y - node.y) * scale,
            )

        def edge_points(sender_id: str, receiver_id: str) -> tuple[QPointF, QPointF]:
            start = point(sender_id)
            end = point(receiver_id)
            delta = end - start
            length = (delta.x() ** 2 + delta.y() ** 2) ** 0.5
            if length == 0:
                return start, end

            def clearance(node_id: str) -> float:
                node = self.network.nodes[node_id]
                radius = 13 if node is self.network.sink else 10
                return radius + 3

            direction = delta / length
            start = start + direction * clearance(sender_id)
            end = end - direction * clearance(receiver_id)
            return start, end

        def draw_node_label(text: str, baseline: QPointF) -> None:
            bounds = painter.fontMetrics().boundingRect(text).translated(
                round(baseline.x()),
                round(baseline.y()),
            )
            painter.fillRect(bounds.adjusted(-2, -1, 2, 1), QColor("#F8F6F0"))
            painter.setPen(QColor("#292524"))
            painter.drawText(baseline, text)

        inactive_edge = QColor("#292524")
        inactive_edge.setAlpha(105)
        painter.setPen(QPen(inactive_edge, 1.3))
        for node in nodes:
            for neighbor_id in node.neighbors:
                neighbor = self.network.nodes.get(neighbor_id)
                if neighbor is None or node.id >= neighbor_id:
                    continue
                start, end = edge_points(node.id, neighbor_id)
                painter.drawLine(start, end)
                midpoint = (start + end) / 2
                weight_font = QFont(self.font())
                weight_font.setPointSize(max(8, weight_font.pointSize() - 1))
                painter.setFont(weight_font)
                weight = f"{self.network.distance(node, neighbor):.1f}"
                text_bounds = painter.fontMetrics().boundingRect(weight)
                label_rect = text_bounds.translated(
                    round(midpoint.x() + 3),
                    round(midpoint.y() - 4),
                ).adjusted(-3, -1, 3, 1)
                painter.fillRect(label_rect, QColor("#F8F6F0"))
                painter.setPen(QColor("#292524"))
                painter.drawText(
                    label_rect.left() + 3,
                    label_rect.bottom() - 1,
                    weight,
                )
                painter.setPen(QPen(inactive_edge, 1.3))

        if self.normal_route and self.route_kind == "attacked":
            self._draw_route(
                painter, self.normal_route, edge_points, "#292524", True
            )
        if self.route:
            self._draw_route(
                painter, self.route, edge_points, "#292524", False, 6.0
            )
            self._draw_route(
                painter, self.route, edge_points, "#16A34A", False, 3.8
            )

        visit_counts: dict[str, int] = {}
        for node_id in self.route:
            visit_counts[node_id] = visit_counts.get(node_id, 0) + 1

        for node in nodes:
            center = point(node.id)
            is_sink = self.network.sink is node
            is_attacker = node.id == self.attacker_node_id
            radius = 13 if is_sink else 10
            if visit_counts.get(node.id, 0) > 1:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#16A34A"), 2.0))
                painter.drawEllipse(center, radius + 5, radius + 5)
            if not node.alive:
                fill = QColor("#292524")
            elif is_attacker:
                fill = QColor("#EA580C")
            elif is_sink:
                fill = QColor("#16A34A")
            else:
                fill = QColor("#FFFFFF")
            painter.setBrush(fill)
            painter.setPen(
                QPen(
                    QColor("#292524") if is_attacker else QColor("#292524"),
                    2.2 if is_attacker else 1.7,
                )
            )
            if is_sink:
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(center.x(), center.y() - radius),
                            QPointF(center.x() + radius, center.y()),
                            QPointF(center.x(), center.y() + radius),
                            QPointF(center.x() - radius, center.y()),
                        ]
                    )
                )
            else:
                painter.drawEllipse(center, radius, radius)

            painter.setPen(QColor("#292524"))
            label_font = QFont(self.font())
            label_font.setBold(True)
            painter.setFont(label_font)
            label = f"{node.id}  SINK" if is_sink else node.id
            visits = visit_counts.get(node.id, 0)
            if visits > 1:
                label += f" x{visits}"
            draw_node_label(label, center + QPointF(14, -7))
            energy = self.node_energy.get(node.id, node.energy)
            painter.setFont(self.font())
            painter.setPen(QColor("#292524"))
            draw_node_label(
                f"{energy:.3g}/{node.initial_energy:.3g} J",
                center + QPointF(14, 9),
            )

        self._draw_legend(painter)
        if self.sender_id in self.network.nodes and self.receiver_id in self.network.nodes:
            start = point(self.sender_id)
            end = point(self.receiver_id)
            packet = start + (end - start) * self.packet_progress
            painter.setBrush(QColor("#16A34A"))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawEllipse(packet, 6, 6)

    def _draw_route(
        self,
        painter: QPainter,
        route: list[str],
        edge_points,
        color: str,
        dashed: bool,
        width: float | None = None,
    ) -> None:
        line_width = width if width is not None else (2.0 if dashed else 4.5)
        pen = QPen(QColor(color), line_width)
        pen.setStyle(Qt.DashLine if dashed else Qt.SolidLine)
        painter.setPen(pen)
        for sender_id, receiver_id in zip(route, route[1:]):
            if sender_id in self.network.nodes and receiver_id in self.network.nodes:
                start, end = edge_points(sender_id, receiver_id)
                painter.drawLine(start, end)

    def _draw_legend(self, painter: QPainter) -> None:
        painter.setFont(self.font())
        painter.setPen(QColor("#292524"))
        labels = [
            ("#FFFFFF", "Sensor", "node"),
            ("#16A34A", "Sink", "sink"),
            ("#EA580C", "Selected attacker", "node"),
            ("#16A34A", "Active route", "route"),
            ("#292524", "Network edge", "edge"),
        ]
        x = 14
        y = self.height() - 18
        for color, label, marker in labels:
            pen_width = 3.0 if marker == "route" else 1.0
            painter.setPen(QPen(QColor("#292524"), 1.0))
            painter.setBrush(QColor(color))
            if marker in {"route", "edge"}:
                painter.setPen(QPen(QColor(color), pen_width))
                painter.drawLine(x, y - 5, x + 9, y - 5)
            elif marker == "sink":
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(x + 4, y - 10),
                            QPointF(x + 9, y - 5),
                            QPointF(x + 4, y),
                            QPointF(x - 1, y - 5),
                        ]
                    )
                )
            else:
                painter.drawEllipse(QPointF(x + 4, y - 5), 4, 4)
            painter.setPen(QColor("#292524"))
            painter.drawText(x + 13, y, label)
            x += 26 + painter.fontMetrics().horizontalAdvance(label)

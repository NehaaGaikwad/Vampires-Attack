from __future__ import annotations

from PyQt5.QtCore import QPointF, Qt, QTimer
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
        self.traversed_edges: set[tuple[str, str]] = set()
        self.packet_status = "IDLE"
        self.ttl_remaining = 0
        self.ttl_maximum = 1
        self.node_energy: dict[str, float] = {
            node.id: float(node.energy) for node in network.nodes.values()
        }
        self.node_alive: dict[str, bool] = {
            node.id: bool(node.alive) for node in network.nodes.values()
        }
        self._outcome_status = ""
        self._feedback_elapsed = 0
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setInterval(45)
        self._feedback_timer.timeout.connect(self._advance_feedback)
        self.setMinimumHeight(300)
        self.setMinimumWidth(330)
        self.setAutoFillBackground(True)

    def set_attacker(self, node_id: str | None) -> None:
        self.attacker_node_id = node_id
        self.update()

    def show_progress(self, event: dict[str, object]) -> None:
        if (
            self.sender_id is not None
            and self.receiver_id is not None
            and self.packet_progress >= 1.0
        ):
            self.traversed_edges.add(
                tuple(sorted((self.sender_id, self.receiver_id)))
            )
        route = event.get("route", [])
        normal_route = event.get("normal_route", [])
        energy = event.get("node_energy", {})
        alive = event.get("node_alive", {})
        self.route = list(route) if isinstance(route, list) else []
        self.normal_route = (
            list(normal_route) if isinstance(normal_route, list) else []
        )
        self.route_kind = str(event.get("route_kind", "normal"))
        self.sender_id = str(event["sender"])
        self.receiver_id = str(event["receiver"])
        self.packet_progress = 0.0
        self.packet_status = str(event.get("status", "IN_TRANSIT")).upper()
        remaining_ttl = event.get("ttl_remaining", self.ttl_remaining)
        maximum_ttl = event.get("ttl_max", self.ttl_maximum)
        self.ttl_remaining = (
            max(0, int(remaining_ttl))
            if isinstance(remaining_ttl, (int, float))
            else self.ttl_remaining
        )
        self.ttl_maximum = (
            max(1, int(maximum_ttl))
            if isinstance(maximum_ttl, (int, float))
            else self.ttl_maximum
        )
        self._outcome_status = ""
        self._feedback_timer.stop()
        if isinstance(energy, dict):
            for node_id, value in energy.items():
                val = float(value)
                self.node_energy[str(node_id)] = val
                if val <= 0.0:
                    self.node_alive[str(node_id)] = False
        if isinstance(alive, dict):
            for node_id, value in alive.items():
                node_key = str(node_id)
                if node_key in self.node_energy and self.node_energy[node_key] <= 0.0:
                    self.node_alive[node_key] = False
                elif isinstance(value, bool):
                    self.node_alive[node_key] = value
        self.update()

    def set_packet_progress(self, progress: float) -> None:
        self.packet_progress = max(0.0, min(1.0, progress))
        if (
            self.packet_progress >= 1.0
            and self.sender_id is not None
            and self.receiver_id is not None
        ):
            self.traversed_edges.add(
                tuple(sorted((self.sender_id, self.receiver_id)))
            )
        self.update()

    def reset_animation(self, *, clear_traversed: bool = True) -> None:
        self._feedback_timer.stop()
        self.route = []
        self.normal_route = []
        self.sender_id = None
        self.receiver_id = None
        self.packet_progress = 0.0
        if clear_traversed:
            self.traversed_edges.clear()
        self.packet_status = "IDLE"
        self.ttl_remaining = 0
        self.ttl_maximum = 1
        self._outcome_status = ""
        self._feedback_elapsed = 0
        self.node_energy = {
            node.id: float(node.energy) for node in self.network.nodes.values()
        }
        self.node_alive = {
            node.id: bool(node.alive) for node in self.network.nodes.values()
        }
        self.update()

    @staticmethod
    def format_energy_display(
        energy: float,
        initial_energy: float,
        is_alive: bool = True,
    ) -> str:
        """Format energy remaining text accurately in Joules."""
        if not is_alive or energy <= 0.0:
            return "DEAD · 0 J"

        if initial_energy == int(initial_energy):
            init_str = str(int(initial_energy))
        else:
            init_str = f"{initial_energy:.4g}"

        if energy >= initial_energy:
            return f"{init_str}/{init_str} J"

        if energy == int(energy):
            curr_str = str(int(energy))
        elif round(energy, 2) == round(energy, 6):
            curr_str = f"{energy:.4g}"
        else:
            curr_str = f"{energy:.4g}"
            if curr_str == init_str or float(curr_str) >= initial_energy:
                curr_str = f"{energy:.4f}".rstrip("0").rstrip(".")
                if curr_str == init_str or float(curr_str) >= initial_energy:
                    curr_str = f"{energy:.6f}".rstrip("0").rstrip(".")

        return f"{curr_str}/{init_str} J"

    def get_node_energy_text(self, node_id: str) -> str:
        """Return the user-facing formatted energy string for a node."""
        node = self.network.nodes.get(node_id)
        if node is None:
            return ""
        energy = self.node_energy.get(node_id, node.energy)
        is_alive = (
            self.node_alive.get(node_id, node.alive)
            and energy > 0.0
            and node.alive
        )
        return self.format_energy_display(energy, node.initial_energy, is_alive)


    def clear_traversed_edges(self) -> None:
        self.traversed_edges.clear()
        self.update()

    def set_outcome(self, status: str, ttl_remaining: object) -> None:
        self.packet_status = status.upper()
        try:
            self.ttl_remaining = max(0, int(ttl_remaining))
        except (TypeError, ValueError):
            pass
        self._outcome_status = self.packet_status
        self._feedback_elapsed = 0
        self._feedback_timer.start()
        self.update()

    def stop_feedback(self) -> None:
        self._feedback_timer.stop()

    def _advance_feedback(self) -> None:
        self._feedback_elapsed += self._feedback_timer.interval()
        if self._feedback_elapsed >= 720:
            self._feedback_timer.stop()
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#FFF7E9"))
        texture = QColor("#F3E6D3")
        painter.setPen(QPen(texture, 1))
        for x in range(12, self.width(), 24):
            painter.drawLine(x, 4, x, self.height() - 4)
        for y in range(12, self.height(), 24):
            painter.drawLine(4, y, self.width() - 4, y)
        painter.setPen(QPen(QColor("#34251E"), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.setFont(QFont("Courier New", 9, QFont.Bold))

        nodes = list(self.network.nodes.values())
        if not nodes:
            painter.setPen(QColor("#34251E"))
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
                if node.id == self.attacker_node_id:
                    return 25
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
            painter.fillRect(bounds.adjusted(-2, -1, 2, 1), QColor("#FFF7E9"))
            painter.setPen(QColor("#34251E"))
            painter.drawText(baseline, text)

        inactive_edge = QColor("#795D4A")
        painter.setPen(QPen(inactive_edge, 2))
        for node in nodes:
            for neighbor_id in node.neighbors:
                neighbor = self.network.nodes.get(neighbor_id)
                if neighbor is None or node.id >= neighbor_id:
                    continue
                start, end = edge_points(node.id, neighbor_id)
                self._draw_pixel_link(painter, start, end)
                midpoint = (start + end) / 2
                weight_font = QFont(self.font())
                weight_font.setFamily("Courier New")
                weight_font.setPointSize(8)
                weight_font.setBold(True)
                painter.setFont(weight_font)
                weight = f"{self.network.distance(node, neighbor):.1f}"
                text_bounds = painter.fontMetrics().boundingRect(weight)
                label_rect = text_bounds.translated(
                    round(midpoint.x() + 3),
                    round(midpoint.y() - 4),
                ).adjusted(-3, -1, 3, 1)
                painter.fillRect(label_rect, QColor("#FFF7E9"))
                painter.setPen(QColor("#795D4A"))
                painter.drawText(
                    label_rect.left() + 3,
                    label_rect.bottom() - 1,
                    weight,
                )
                painter.setPen(QPen(inactive_edge, 2))

        self._draw_active_route(painter, edge_points, point)

        visit_counts: dict[str, int] = {}
        for node_id in self.route:
            visit_counts[node_id] = visit_counts.get(node_id, 0) + 1

        for node in nodes:
            center = point(node.id)
            current_energy = self.node_energy.get(node.id, node.energy)
            is_alive = (
                self.node_alive.get(node.id, node.alive)
                and current_energy > 0.0
                and node.alive
            )
            is_sink = self.network.sink is node
            is_attacker = node.id == self.attacker_node_id
            radius = 22 if is_attacker else 13 if is_sink else 10
            if visit_counts.get(node.id, 0) > 1:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#4B8845"), 2))
                painter.drawRect(
                    round(center.x() - radius - 5),
                    round(center.y() - radius - 5),
                    (radius + 5) * 2,
                    (radius + 5) * 2,
                )
            if not is_alive:
                painter.setBrush(QColor("#44403C"))
                painter.setPen(QPen(QColor("#78716C"), 2))
                painter.drawRect(
                    round(center.x() - radius),
                    round(center.y() - radius),
                    radius * 2,
                    radius * 2,
                )
                painter.setPen(QPen(QColor("#DC2626"), 2))
                painter.drawLine(
                    round(center.x() - radius + 3),
                    round(center.y() - radius + 3),
                    round(center.x() + radius - 3),
                    round(center.y() + radius - 3),
                )
                painter.drawLine(
                    round(center.x() + radius - 3),
                    round(center.y() - radius + 3),
                    round(center.x() - radius + 3),
                    round(center.y() + radius - 3),
                )
            elif is_attacker:
                self._draw_vampire(painter, center)
            elif is_sink:
                painter.setBrush(QColor("#4B8845"))
                painter.setPen(QPen(QColor("#34251E"), 2))
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
                painter.setBrush(QColor("#E5EEDC"))
                painter.setPen(QPen(QColor("#34251E"), 2))
                painter.drawRect(
                    round(center.x() - radius),
                    round(center.y() - radius),
                    radius * 2,
                    radius * 2,
                )

            painter.setPen(QColor("#34251E"))
            label_font = QFont("Courier New", 9, QFont.Bold)
            painter.setFont(label_font)
            label = (
                f"{node.id} DEAD"
                if not is_alive
                else (node.id if node.id.upper() == "SINK" else f"{node.id} SINK")
                if is_sink
                else f"{node.id} VAMPIRE"
                if is_attacker
                else node.id
            )
            visits = visit_counts.get(node.id, 0)
            if visits > 1:
                label += f" x{visits}"
            label_width = painter.fontMetrics().horizontalAdvance(label)
            draw_node_label(
                label,
                QPointF(
                    center.x() - label_width / 2,
                    center.y() - radius - 5,
                ),
            )
            energy_text = self.format_energy_display(
                current_energy, node.initial_energy, is_alive
            )
            painter.setFont(self.font())
            painter.setPen(QColor("#292524") if is_alive else QColor("#DC2626"))
            energy_width = painter.fontMetrics().horizontalAdvance(energy_text)
            draw_node_label(
                energy_text,
                QPointF(
                    center.x() - energy_width / 2,
                    center.y() + radius + 14,
                ),
            )

        self._draw_legend(painter)
        if self.sender_id in self.network.nodes and self.receiver_id in self.network.nodes:
            start = point(self.sender_id)
            end = point(self.receiver_id)
            packet = self._pixel_link_point(start, end, self.packet_progress)
            intercepted = (
                self.route_kind == "attacked"
                and self.attacker_node_id in {self.sender_id, self.receiver_id}
            )
            lost = self._outcome_status in {"EXPIRED", "DROPPED", "FAILED"}
            if (
                intercepted
                and self.receiver_id == self.attacker_node_id
                and self.packet_progress >= 0.65
            ):
                self._draw_warning_burst(painter, point(self.attacker_node_id))
            if lost and self._feedback_elapsed < 360:
                self._draw_collapsing_character(
                    painter,
                    packet,
                    self._feedback_elapsed,
                )
            elif not lost:
                ttl_ratio = self.ttl_remaining / max(self.ttl_maximum, 1)
                self._draw_character(painter, packet, ttl_ratio, intercepted)
                self._draw_ttl_bubble(painter, packet, self.ttl_remaining)

        if self._feedback_elapsed < 720 and self._outcome_status:
            if self._outcome_status == "DELIVERED":
                self._draw_outcome_banner(painter, "DELIVERED!", "#4B8845")
                self._draw_victory_sparks(painter, self._feedback_elapsed)
            elif self._outcome_status in {"EXPIRED", "DROPPED", "FAILED"}:
                self._draw_outcome_banner(painter, "PACKET LOST", "#D95735")

    @staticmethod
    def _draw_pixel_link(
        painter: QPainter,
        start: QPointF,
        end: QPointF,
    ) -> None:
        painter.drawLine(start, end)

    def _draw_active_route(self, painter: QPainter, edge_points, point) -> None:
        current_edge = (
            (self.sender_id, self.receiver_id)
            if self.sender_id is not None and self.receiver_id is not None
            else None
        )
        route_color = QColor("#3F9B45")
        painter.setOpacity(1.0)
        for sender_id, receiver_id in sorted(self.traversed_edges):
            if (
                sender_id not in self.network.nodes
                or receiver_id not in self.network.nodes
            ):
                continue
            painter.setPen(QPen(route_color, 5, Qt.SolidLine, Qt.SquareCap))
            start, end = edge_points(sender_id, receiver_id)
            self._draw_pixel_link(painter, start, end)
            self._draw_route_arrow(painter, start, end, route_color.name())
        if (
            current_edge is not None
            and current_edge[0] in self.network.nodes
            and current_edge[1] in self.network.nodes
        ):
            start, end = edge_points(*current_edge)
            packet = self._pixel_link_point(
                point(current_edge[0]),
                point(current_edge[1]),
                self.packet_progress,
            )
            progress = self._project_link_progress(start, end, packet)
            current_key = tuple(sorted(current_edge))
            if current_key not in self.traversed_edges:
                self._draw_link_progress(
                    painter,
                    start,
                    end,
                    0.0,
                    progress,
                    route_color.name(),
                    width=5,
                )

    @staticmethod
    def _project_link_progress(
        start: QPointF,
        end: QPointF,
        position: QPointF,
    ) -> float:
        delta = end - start
        length_squared = delta.x() ** 2 + delta.y() ** 2
        if length_squared == 0:
            return 0.0
        offset = position - start
        progress = (
            offset.x() * delta.x() + offset.y() * delta.y()
        ) / length_squared
        return max(0.0, min(1.0, progress))

    @staticmethod
    def _draw_link_progress(
        painter: QPainter,
        start: QPointF,
        end: QPointF,
        start_progress: float,
        end_progress: float,
        color: str,
        width: float = 5,
    ) -> None:
        start_ratio = max(0.0, min(1.0, start_progress))
        end_ratio = max(start_ratio, min(1.0, end_progress))
        painter.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.SquareCap))
        painter.drawLine(
            start + (end - start) * start_ratio,
            start + (end - start) * end_ratio,
        )

    @staticmethod
    def _draw_character(
        painter: QPainter,
        center: QPointF,
        ttl_ratio: float,
        intercepted: bool,
    ) -> None:
        ratio = max(0.0, min(1.0, ttl_ratio))
        body = (
            QColor("#D95735")
            if intercepted or ratio <= 0.3
            else QColor("#D8B646")
            if ratio <= 0.6
            else QColor("#4B8845")
        )
        colors = {
            "D": QColor("#34251E"),
            "H": QColor("#328B65") if not intercepted else QColor("#D95735"),
            "W": QColor("#FFF7E9"),
            "S": QColor("#E4AA6D"),
            "B": body,
        }
        rows = (
            "...DDDD...",
            "..DHHHHD..",
            ".DHHHHHHD.",
            ".DHHWHHHD.",
            "..DDSSDD..",
            "...SSSS...",
            "..DDDDDD..",
            ".DDBBBBD.",
            ".DDBBBBD.",
            "..DBBBBD..",
            "...DBBD...",
            "...D..D...",
            "..DD..DD..",
        )
        pixel = 3
        left = round(center.x() - 15)
        top = round(center.y() - 36)
        painter.setPen(Qt.NoPen)
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell in colors:
                    painter.setBrush(colors[cell])
                    painter.drawRect(
                        left + x * pixel,
                        top + y * pixel,
                        pixel,
                        pixel,
                    )

    @staticmethod
    def _draw_vampire(
        painter: QPainter,
        center: QPointF,
        pixel_size: int = 3,
    ) -> None:
        colors = {
            "D": QColor("#34251E"),
            "F": QColor("#E4AA6D"),
            "W": QColor("#FFF7E9"),
            "R": QColor("#D95735"),
            "C": QColor("#FFF7E9"),
        }
        rows = (
            "....DDDDD....",
            "...DDDDDDD...",
            "..DDFFFFFDD..",
            ".DDFFWFWFFDD.",
            ".DFFFFFFFFFD.",
            "..DDFFFFFDD..",
            "...DDDDDDD...",
            "....DCD......",
            "..DDRRRRRDD..",
            ".DRRRRRRRRRD.",
            "DRRRRRRRRRRRD",
            "DDRRRRRRRRRDD",
            "DD..DD...DD..",
            "DD..DD...DD..",
        )
        width = len(rows[0]) * pixel_size
        height = len(rows) * pixel_size
        left = round(center.x() - width / 2)
        top = round(center.y() - height / 2)
        painter.setPen(Qt.NoPen)
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                color = colors.get(cell)
                if color is not None:
                    painter.setBrush(color)
                    painter.drawRect(
                        left + x * pixel_size,
                        top + y * pixel_size,
                        pixel_size,
                        pixel_size,
                    )

    @staticmethod
    def _draw_ttl_bubble(
        painter: QPainter,
        center: QPointF,
        ttl: int,
    ) -> None:
        rect_x = round(center.x() - 24)
        rect_y = round(center.y() - 56)
        painter.setPen(QPen(QColor("#34251E"), 2))
        painter.setBrush(QColor("#FFF7E9"))
        painter.drawRect(rect_x, rect_y, 49, 19)
        painter.setFont(QFont("Courier New", 8, QFont.Bold))
        painter.setPen(QColor("#34251E"))
        painter.drawText(rect_x + 4, rect_y + 12, f"TTL {ttl}")
        bar_color = (
            "#D95735" if ttl <= 3
            else "#D8B646" if ttl <= 10
            else "#4B8845"
        )
        painter.fillRect(rect_x + 3, rect_y + 15, 43, 2, QColor(bar_color))

    @staticmethod
    def _draw_warning_burst(painter: QPainter, center: QPointF) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D95735"))
        for x, y in (
            (-16, -14), (0, -19), (15, -13), (-19, 0),
            (19, 1), (-14, 13), (1, 18), (14, 13),
        ):
            painter.drawRect(round(center.x() + x), round(center.y() + y), 4, 4)

    @staticmethod
    def _draw_collapsing_character(
        painter: QPainter,
        center: QPointF,
        elapsed: int,
    ) -> None:
        painter.save()
        painter.setOpacity(max(0.0, 1.0 - elapsed / 360))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D95735"))
        spread = elapsed // 60
        painter.drawRect(
            round(center.x() - 9 - spread),
            round(center.y() - 2 - spread),
            5,
            3,
        )
        painter.drawRect(
            round(center.x() - 2),
            round(center.y() + spread),
            4,
            3,
        )
        painter.drawRect(
            round(center.x() + 5 + spread),
            round(center.y() - 3 - spread),
            4,
            3,
        )
        painter.restore()

    @staticmethod
    def _draw_outcome_banner(
        painter: QPainter,
        text: str,
        color: str,
    ) -> None:
        painter.save()
        painter.setFont(QFont("Courier New", 11, QFont.Bold))
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text) + 22
        left = (painter.device().width() - width) // 2
        painter.setPen(QPen(QColor("#34251E"), 2))
        painter.setBrush(QColor("#FFF7E9"))
        painter.drawRect(left, 12, width, 30)
        painter.fillRect(left + 3, 15, 5, 24, QColor(color))
        painter.setPen(QColor("#34251E"))
        painter.drawText(left + 14, 32, text)
        painter.restore()

    @staticmethod
    def _draw_victory_sparks(painter: QPainter, elapsed: int) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D8B646"))
        rise = (elapsed // 90) % 5
        for x, y in (
            (18, 64 - rise * 2),
            (30, 88 - rise * 2),
            (0, 105 - rise * 2),
            (0, 150 - rise * 2),
        ):
            painter.drawRect(x, y, 4, 4)

    @staticmethod
    def _pixel_link_point(
        start: QPointF,
        end: QPointF,
        progress: float,
    ) -> QPointF:
        ratio = max(0.0, min(1.0, progress))
        return start + (end - start) * ratio

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
                self._draw_pixel_link(painter, start, end)
                self._draw_route_arrow(painter, start, end, color)

    @staticmethod
    def _draw_route_arrow(
        painter: QPainter,
        start: QPointF,
        end: QPointF,
        color: str,
    ) -> None:
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        if abs(dy) >= abs(dx):
            direction = 1 if dy >= 0 else -1
            points = [
                QPointF(end.x(), end.y()),
                QPointF(end.x() - 4, end.y() - direction * 6),
                QPointF(end.x() + 4, end.y() - direction * 6),
            ]
        else:
            direction = 1 if dx >= 0 else -1
            points = [
                QPointF(end.x(), end.y()),
                QPointF(end.x() - direction * 6, end.y() - 4),
                QPointF(end.x() - direction * 6, end.y() + 4),
            ]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(points))

    def _draw_legend(self, painter: QPainter) -> None:
        painter.setFont(QFont("Courier New", 8, QFont.Bold))
        painter.setPen(QColor("#34251E"))
        labels = [
            ("#E5EEDC", "SENSOR", "node"),
            ("#4B8845", "SINK", "sink"),
            ("#D95735", "VAMPIRE", "node"),
            ("#4B8845", "ROUTE", "route"),
        ]
        x = 12
        y = self.height() - 12
        for color, label, marker in labels:
            pen_width = 3.0 if marker == "route" else 2.0
            painter.setPen(QPen(QColor("#34251E"), 1.0))
            painter.setBrush(QColor(color))
            if marker == "route":
                painter.setPen(QPen(QColor(color), pen_width))
                painter.drawLine(x, y - 4, x + 10, y - 4)
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
            elif marker == "node":
                painter.setPen(QPen(QColor("#34251E"), 2))
                painter.drawRect(x, y - 10, 8, 8)
            else:
                self._draw_vampire(painter, QPointF(x + 5, y - 6), 1)
            painter.setPen(QColor("#34251E"))
            painter.drawText(x + 12, y, label)
            x += 20 + painter.fontMetrics().horizontalAdvance(label)

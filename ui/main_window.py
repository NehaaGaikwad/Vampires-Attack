from __future__ import annotations

from collections.abc import Mapping
from threading import Event

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from simulator import Simulator
from visualization.live_network_view import LiveNetworkView


ResultValue = str | int | float | bool


class PacketDeliveredDialog(QDialog):
    """Custom success dialog showing final packet delivery metrics."""

    def __init__(
        self,
        scenario: str,
        hops: object,
        energy: str,
        ttl: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Packet Delivered Successfully!")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        card = QFrame()
        card.setObjectName("successCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(8)
        card_layout.setAlignment(Qt.AlignHCenter)

        success_icon = QLabel("✓")
        success_icon.setObjectName("successIcon")
        success_icon.setAlignment(Qt.AlignCenter)
        success_icon.setFixedSize(52, 52)
        card_layout.addWidget(success_icon, 0, Qt.AlignHCenter)

        title = QLabel("Packet Delivered Successfully!")
        title.setObjectName("successTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        card_layout.addWidget(title)

        message = QLabel(
            "Great news! Your packet has successfully reached the SINK."
        )
        message.setObjectName("successMessage")
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        card_layout.addWidget(message)

        details = QGridLayout()
        details.setContentsMargins(2, 4, 2, 2)
        details.setHorizontalSpacing(18)
        details.setVerticalSpacing(6)
        detail_rows = (
            ("Scenario", scenario),
            ("Hops", str(hops)),
            ("Energy Consumed", f"{energy} J"),
            ("TTL Remaining", str(ttl)),
        )
        for row, (label_text, value_text) in enumerate(detail_rows):
            label = QLabel(label_text)
            label.setObjectName("detailLabel")
            value = QLabel(value_text)
            value.setObjectName("detailValue")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            details.addWidget(label, row, 0)
            details.addWidget(value, row, 1)
        card_layout.addLayout(details)

        continue_button = QPushButton("Continue")
        continue_button.setObjectName("continueButton")
        continue_button.setMinimumWidth(120)
        continue_button.clicked.connect(self.accept)
        card_layout.addWidget(continue_button, 0, Qt.AlignHCenter)
        outer_layout.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow_color = QColor("#292524")
        shadow_color.setAlpha(42)
        shadow.setColor(shadow_color)
        card.setGraphicsEffect(shadow)
        self.setStyleSheet(
            """
            QDialog {
                background: transparent;
                font-family: "Segoe UI";
            }
            QFrame#successCard {
                background: #FFFFFF;
                border: 1px solid #F8F6F0;
                border-radius: 16px;
            }
            QLabel#successIcon {
                background: #16A34A;
                color: #FFFFFF;
                border-radius: 26px;
                font-size: 24pt;
                font-weight: 600;
            }
            QLabel#successTitle {
                color: #292524;
                font-size: 13pt;
                font-weight: 600;
            }
            QLabel#successMessage {
                color: #292524;
                font-size: 9pt;
                padding-bottom: 2px;
            }
            QLabel#detailLabel {
                color: #292524;
                font-size: 9pt;
            }
            QLabel#detailValue {
                color: #292524;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton#continueButton {
                background: #16A34A;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                min-height: 30px;
                padding: 3px 14px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton#continueButton:hover {
                background: #F8F6F0;
                color: #16A34A;
                border: 1px solid #16A34A;
            }
            QPushButton#continueButton:pressed {
                background: #292524;
            }
            """
        )


class StatusMessageDialog(QDialog):
    """Palette-matched dialog for validation and operation messages."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        card = QFrame()
        card.setObjectName("messageCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 14)
        card_layout.setSpacing(8)

        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(9)
        warning_icon = QLabel("!")
        warning_icon.setObjectName("messageIcon")
        warning_icon.setAlignment(Qt.AlignCenter)
        warning_icon.setFixedSize(28, 28)
        heading_layout.addWidget(warning_icon)

        heading = QLabel(title)
        heading.setObjectName("messageTitle")
        heading.setWordWrap(True)
        heading_layout.addWidget(heading, 1)
        card_layout.addLayout(heading_layout)

        body = QLabel(message)
        body.setObjectName("messageBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        card_layout.addWidget(body)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        close_button = QPushButton("OK")
        close_button.setObjectName("messageButton")
        close_button.setMinimumWidth(84)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        card_layout.addLayout(button_layout)
        outer_layout.addWidget(card)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow_color = QColor("#292524")
        shadow_color.setAlpha(42)
        shadow.setColor(shadow_color)
        card.setGraphicsEffect(shadow)

        self.setStyleSheet(
            """
            QDialog {
                background: transparent;
                font-family: "Segoe UI";
            }
            QFrame#messageCard {
                background: #FFFFFF;
                border: 1px solid #F8F6F0;
                border-radius: 12px;
            }
            QLabel#messageIcon {
                background: #EA580C;
                color: #FFFFFF;
                border-radius: 14px;
                font-size: 14pt;
                font-weight: 700;
            }
            QLabel#messageTitle {
                color: #292524;
                font-size: 10pt;
                font-weight: 600;
            }
            QLabel#messageBody {
                color: #292524;
                font-size: 9pt;
            }
            QPushButton#messageButton {
                background: #16A34A;
                color: #FFFFFF;
                border: 1px solid #16A34A;
                border-radius: 5px;
                min-height: 28px;
                padding: 2px 12px;
                font-size: 9pt;
                font-weight: 600;
            }
            QPushButton#messageButton:hover {
                background: #F8F6F0;
                color: #16A34A;
            }
            QPushButton#messageButton:pressed {
                background: #292524;
                color: #FFFFFF;
                border-color: #292524;
            }
            """
        )


class SimulationWorker(QObject):
    progress = pyqtSignal(object, object)
    completed = pyqtSignal(str, object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        simulator: Simulator,
        operation: str,
        options: dict[str, str | int],
        attack: StretchAttack | CarouselAttack | None = None,
    ) -> None:
        super().__init__()
        self.simulator = simulator
        self.operation = operation
        self.options = options
        self.attack = attack
        self.stop_event = Event()

    def run(self) -> None:
        original_attack = self.simulator.attack
        try:
            if self.operation == "simulation":
                self.simulator.attack = self.attack
                result = self.simulator.run_packet(
                    source=str(self.options["source"]),
                    destination=str(self.options["destination"]),
                    packet_size=int(self.options["packet_size"]),
                    ttl=int(self.options["ttl"]),
                    on_progress=self._report_progress,
                )
            else:
                attacker_id = str(self.options["attacker_node_id"])
                result = self.simulator.run_experiment(
                    source=str(self.options["source"]),
                    destination=str(self.options["destination"]),
                    packet_size=int(self.options["packet_size"]),
                    ttl=int(self.options["ttl"]),
                    stretch_attack=StretchAttack(attacker_id),
                    carousel_attack=CarouselAttack(attacker_id),
                    on_progress=self._report_progress,
                )
            self.completed.emit(self.operation, result)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.simulator.attack = original_attack
            self.finished.emit()

    def _report_progress(self, event: dict[str, object]) -> None:
        if self.stop_event.is_set():
            return
        gate = Event()
        self.progress.emit(event, gate)
        while not gate.wait(0.1):
            if self.stop_event.is_set():
                return


class SimulatorMainWindow(QMainWindow):
    """Simple dashboard for running packets and comparing attack scenarios."""

    def __init__(self, simulator: Simulator) -> None:
        super().__init__()
        self.simulator = simulator
        self._original_attack = simulator.attack
        self._scenario_labels: dict[int, str] = {}
        self._result_start_index = 0
        self._run_energy_start = 0.0
        self._delivery_popup_shown = False
        self._thread: QThread | None = None
        self._worker: SimulationWorker | None = None
        self._current_gate: Event | None = None
        self._packet_progress = 0.0
        self._paused = False
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._advance_animation)

        self.setWindowTitle("Vampire Attack Simulator")
        self.resize(1180, 860)
        self.setMinimumSize(920, 700)

        central_widget = QWidget(self)
        central_widget.setObjectName("application")
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("Vampire Attack Simulator")
        title.setObjectName("title")
        subtitle = QLabel("Wireless Sensor Network Simulation")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch(1)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusIndicator")
        header.addWidget(self.status_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        root_layout.addLayout(header)

        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.setHandleWidth(8)

        controls_panel = QFrame()
        controls_panel.setObjectName("controlsPanel")
        self._add_panel_shadow(controls_panel)
        controls_panel.setMinimumWidth(270)
        controls_panel.setMaximumWidth(350)
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.setSpacing(12)

        controls_heading = QLabel("Simulation controls")
        controls_heading.setObjectName("sectionHeading")
        controls_layout.addWidget(controls_heading)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        self.scenario_input = QComboBox()
        self.scenario_input.addItems(["Normal", "Stretch", "Carousel"])
        self.scenario_input.setMinimumWidth(110)
        self.scenario_input.setMaximumWidth(200)
        node_ids = list(self.simulator.network.nodes)
        sink = self.simulator.network.sink
        sink_id = sink.id if sink is not None else None
        sensor_ids = [node_id for node_id in node_ids if node_id != sink_id]

        self.source_input = QComboBox()
        self.source_input.addItems(node_ids)
        self.source_input.setCurrentText(
            self._preferred_node_id("N1", node_ids)
        )
        self.destination_input = QComboBox()
        self.destination_input.addItems(node_ids)
        self.destination_input.setCurrentText(
            self._preferred_node_id(sink_id or "SINK", node_ids)
        )
        self.attacker_input = QComboBox()
        self.attacker_input.setObjectName("attackerInput")
        self.attacker_input.addItems(sensor_ids)
        attacker_default = "N2"
        if attacker_default not in sensor_ids and self.simulator.attack is not None:
            attacker_default = self.simulator.attack.attacker_node_id
        self.attacker_input.setCurrentText(
            self._preferred_node_id(attacker_default, sensor_ids)
        )
        for node_input in (
            self.source_input,
            self.destination_input,
            self.attacker_input,
        ):
            node_input.setMinimumWidth(110)
            node_input.setMaximumWidth(200)
        self.packet_size_input = QSpinBox()
        self.packet_size_input.setRange(0, 2_147_483_647)
        self.packet_size_input.setValue(4000)
        self.packet_size_input.setMinimumWidth(110)
        self.packet_size_input.setMaximumWidth(150)
        self.ttl_input = QSpinBox()
        self.ttl_input.setRange(1, 2_147_483_647)
        self.ttl_input.setValue(50)
        self.ttl_input.setMinimumWidth(110)
        self.ttl_input.setMaximumWidth(150)
        self.attacker_input.currentTextChanged.connect(self._refresh_attacker)
        self.scenario_input.currentTextChanged.connect(self._update_attacker_enabled)

        form.addRow("Scenario", self.scenario_input)
        form.addRow("Source", self.source_input)
        form.addRow("Destination", self.destination_input)
        form.addRow("Attacker node", self.attacker_input)
        form.addRow("Packet size (bits)", self.packet_size_input)
        form.addRow("TTL", self.ttl_input)
        controls_layout.addLayout(form)

        self.run_button = QPushButton("Run Simulation")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self._run_simulation)
        controls_layout.addWidget(self.run_button)

        playback = QHBoxLayout()
        playback.setSpacing(8)
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start_animation)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self._pause_animation)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset_animation)
        playback.addWidget(self.start_button)
        playback.addWidget(self.pause_button)
        playback.addWidget(self.reset_button)
        controls_layout.addLayout(playback)

        control_separator = QFrame()
        control_separator.setFrameShape(QFrame.HLine)
        control_separator.setObjectName("separator")
        controls_layout.addWidget(control_separator)

        secondary_actions = QHBoxLayout()
        secondary_actions.setSpacing(8)
        self.experiment_button = QPushButton("Run Experiment")
        self.experiment_button.setObjectName("secondaryButton")
        self.experiment_button.clicked.connect(self._run_experiment)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._export_csv)
        secondary_actions.addWidget(self.experiment_button)
        secondary_actions.addWidget(self.export_button)
        controls_layout.addLayout(secondary_actions)
        controls_layout.addStretch(1)

        network_panel = QFrame()
        network_panel.setObjectName("networkPanel")
        self._add_panel_shadow(network_panel)
        network_layout = QVBoxLayout(network_panel)
        network_layout.setContentsMargins(16, 14, 16, 14)
        network_layout.setSpacing(8)
        network_header = QHBoxLayout()
        network_heading = QLabel("Network topology")
        network_heading.setObjectName("sectionHeading")
        network_header.addWidget(network_heading)
        network_header.addStretch(1)
        self.packet_label = QLabel("Packet: idle")
        self.packet_label.setObjectName("packetStatus")
        network_header.addWidget(self.packet_label)
        network_layout.addLayout(network_header)
        self.network_view = LiveNetworkView(self.simulator.network)
        self.network_view.setMinimumHeight(330)
        network_layout.addWidget(self.network_view, 1)
        self.route_label = QLabel("Route: waiting for a simulation")
        self.route_label.setObjectName("routeLabel")
        self.route_label.setWordWrap(True)
        network_layout.addWidget(self.route_label)
        content.addWidget(controls_panel)
        content.addWidget(network_panel)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)
        content.setSizes([315, 810])
        root_layout.addWidget(content, 1)

        results_panel = QFrame()
        results_panel.setObjectName("resultsPanel")
        self._add_panel_shadow(results_panel)
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(16, 12, 16, 12)
        results_layout.setSpacing(8)
        results_header = QHBoxLayout()
        results_heading = QLabel("Results")
        results_heading.setObjectName("sectionHeading")
        results_header.addWidget(results_heading)
        results_header.addStretch(1)
        results_layout.addLayout(results_header)

        metrics = QHBoxLayout()
        metrics.setSpacing(0)
        self.metric_status = self._add_metric(metrics, "Packet status", "—")
        self.metric_hops = self._add_metric(metrics, "Hops", "—")
        self.metric_energy = self._add_metric(metrics, "Energy consumed", "—")
        self.metric_alive = self._add_metric(metrics, "Alive nodes", "—")
        self.metric_ttl = self._add_metric(metrics, "TTL remaining", "—")
        results_layout.addLayout(metrics)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Scenario", "Status", "Hops", "Energy consumed (J)", "Alive nodes"]
        )
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setShowGrid(False)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setMinimumHeight(130)
        self.results_table.setMaximumHeight(185)
        results_layout.addWidget(self.results_table)
        root_layout.addWidget(results_panel)

        self.setStyleSheet(self._application_stylesheet())
        self._refresh_attacker()
        self._update_attacker_enabled()
        self._refresh_results()

    def _update_attacker_enabled(self, _scenario: str | None = None) -> None:
        del _scenario
        enabled = self.scenario_input.currentText() != "Normal"
        self.attacker_input.setEnabled(enabled)
        self.attacker_input.setToolTip(
            "Select the attacker sensor node"
            if enabled
            else "Attacker selection is not used in Normal mode"
        )
        self._refresh_attacker()

    def _set_status(self, text: str, state: str = "idle") -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_metric_packet_status(self, value: str) -> None:
        self.metric_status.setText(value)
        state = value.casefold()
        self.metric_status.setProperty(
            "state",
            state if state in {"delivered", "expired", "dropped"} else "",
        )
        self.metric_status.style().unpolish(self.metric_status)
        self.metric_status.style().polish(self.metric_status)

    @staticmethod
    def _add_metric(layout: QHBoxLayout, label: str, value: str) -> QLabel:
        container = QFrame()
        container.setObjectName("metric")
        metric_layout = QVBoxLayout(container)
        metric_layout.setContentsMargins(10, 7, 10, 7)
        metric_layout.setSpacing(1)
        name_label = QLabel(label)
        name_label.setObjectName("metricLabel")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        metric_layout.addWidget(name_label)
        metric_layout.addWidget(value_label)
        layout.addWidget(container, 1)
        return value_label

    @staticmethod
    def _add_panel_shadow(panel: QFrame) -> None:
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow_color = QColor("#292524")
        shadow_color.setAlpha(22)
        shadow.setColor(shadow_color)
        panel.setGraphicsEffect(shadow)

    @staticmethod
    def _application_stylesheet() -> str:
        return """
            QWidget#application {
                background: #F8F6F0;
                color: #292524;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QFrame#controlsPanel, QFrame#networkPanel, QFrame#resultsPanel {
                background: #FFFFFF;
                border: 1px solid #F8F6F0;
                border-radius: 4px;
            }
            QFrame#controlsPanel {
                background: #FFFFFF;
            }
            QFrame#resultsPanel {
                background: #FFFFFF;
                border-top: 3px solid #16A34A;
            }
            QLabel#title {
                color: #292524;
                font-size: 19pt;
                font-weight: 600;
                border-bottom: 2px solid #16A34A;
                padding-bottom: 3px;
            }
            QLabel#subtitle, QLabel#metricLabel {
                color: #292524;
                font-size: 9pt;
            }
            QLabel#statusIndicator {
                background: #F8F6F0;
                color: #292524;
                border: 1px solid #F8F6F0;
                border-radius: 10px;
                padding: 4px 11px;
                font-size: 9pt;
            }
            QLabel#statusIndicator[state="running"] {
                background: #F8F6F0;
                color: #292524;
                border-color: #16A34A;
            }
            QLabel#statusIndicator[state="delivered"] {
                background: #16A34A;
                color: #FFFFFF;
                border-color: #16A34A;
            }
            QLabel#statusIndicator[state="expired"] {
                background: #EA580C;
                color: #FFFFFF;
                border-color: #EA580C;
            }
            QLabel#statusIndicator[state="error"] {
                background: #EA580C;
                color: #FFFFFF;
                border-color: #EA580C;
            }
            QLabel#sectionHeading {
                color: #292524;
                font-size: 11pt;
                font-weight: 600;
                border-left: 3px solid #16A34A;
                padding-left: 7px;
            }
            QLabel#packetStatus {
                color: #292524;
                font-size: 9pt;
            }
            QLabel#routeLabel {
                color: #16A34A;
                font-size: 9pt;
                padding-top: 3px;
            }
            QLabel#metricValue {
                color: #292524;
                font-size: 12pt;
                font-weight: 600;
            }
            QLabel#metricValue[state="delivered"] {
                color: #16A34A;
                padding: 2px 6px;
            }
            QLabel#metricValue[state="expired"],
            QLabel#metricValue[state="dropped"] {
                color: #FFFFFF;
                background: #EA580C;
                padding: 2px 6px;
            }
            QFrame#metric {
                background: transparent;
                border: none;
                border-right: 1px solid #F8F6F0;
                border-radius: 0;
            }
            QFrame#separator {
                color: #F8F6F0;
                max-height: 1px;
            }
            QSpinBox {
                background: #FFFFFF;
                color: #292524;
                border: 1px solid #F8F6F0;
                border-radius: 3px;
                min-height: 27px;
                padding: 2px 7px;
                selection-background-color: #16A34A;
            }
            QSpinBox:focus {
                border: 2px solid #16A34A;
            }
            QPushButton {
                background: #FFFFFF;
                color: #292524;
                border: 1px solid #F8F6F0;
                border-radius: 3px;
                min-height: 30px;
                padding: 3px 9px;
            }
            QPushButton:hover:enabled {
                background: #F8F6F0;
                border-color: #16A34A;
            }
            QPushButton:pressed:enabled {
                background: #292524;
                color: #FFFFFF;
                border-color: #292524;
            }
            QPushButton:disabled {
                color: #292524;
                background: #F8F6F0;
            }
            QPushButton#primaryButton {
                background: #16A34A;
                color: #FFFFFF;
                border-color: #16A34A;
                font-weight: 600;
                min-height: 34px;
            }
            QPushButton#primaryButton:hover:enabled {
                background: #F8F6F0;
                color: #16A34A;
                border-color: #16A34A;
            }
            QPushButton#primaryButton:pressed:enabled {
                background: #292524;
                color: #FFFFFF;
                border-color: #292524;
            }
            QPushButton#secondaryButton {
                background: #FFFFFF;
                color: #292524;
                border-color: #F8F6F0;
            }
            QPushButton#secondaryButton:hover:enabled {
                background: #F8F6F0;
                border-color: #16A34A;
            }
            QPushButton#secondaryButton:pressed:enabled {
                background: #292524;
                color: #FFFFFF;
                border-color: #292524;
            }
            QComboBox {
                background: #FFFFFF;
                color: #292524;
                border: 1px solid #F8F6F0;
                border-radius: 3px;
                min-height: 27px;
                padding: 2px 7px;
                selection-background-color: #16A34A;
            }
            QComboBox:focus {
                border: 2px solid #16A34A;
            }
            QComboBox#attackerInput {
                border: 2px solid #EA580C;
            }
            QComboBox#attackerInput:focus {
                border: 2px solid #EA580C;
            }
            QComboBox:disabled {
                color: #292524;
                background: #F8F6F0;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #F8F6F0;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #16A34A;
            }
            QComboBox QAbstractItemView {
                background: #FFFFFF;
                color: #292524;
                border: 1px solid #F8F6F0;
                selection-background-color: #16A34A;
                selection-color: #FFFFFF;
                outline: 0;
            }
            QTableWidget {
                background: #FFFFFF;
                alternate-background-color: #F8F6F0;
                color: #292524;
                border: 1px solid #F8F6F0;
                gridline-color: #F8F6F0;
                selection-background-color: #F8F6F0;
                selection-color: #292524;
            }
            QHeaderView::section {
                background: #F8F6F0;
                color: #292524;
                border: none;
                border-bottom: 1px solid #F8F6F0;
                padding: 6px 8px;
                font-weight: 600;
            }
            QSplitter::handle {
                background: transparent;
            }
        """

    def _preferred_node_id(
        self,
        preferred: str,
        available: list[str],
    ) -> str:
        if preferred in available:
            return preferred
        return available[0] if available else ""

    def _refresh_attacker(self, _text: str | None = None) -> None:
        del _text
        attacker_id = self.attacker_input.currentText().strip()
        sink = self.simulator.network.sink
        self.network_view.set_attacker(
            attacker_id
            if (
                self.scenario_input.currentText() != "Normal"
                and attacker_id in self.simulator.network.nodes
                and (sink is None or attacker_id != sink.id)
            )
            else None
        )

    def _selected_attack(self) -> StretchAttack | CarouselAttack | None:
        attacker_id = self.attacker_input.currentText().strip()
        scenario = self.scenario_input.currentText()
        if scenario == "Normal":
            return None
        if not attacker_id:
            raise ValueError("Enter an attacker node ID for attack scenarios.")
        if attacker_id not in self.simulator.network.nodes:
            raise ValueError(f"Attacker node {attacker_id!r} is not in the network.")
        sink = self.simulator.network.sink
        if sink is not None and attacker_id == sink.id:
            raise ValueError("The sink cannot be selected as an attacker.")
        if scenario == "Stretch":
            return StretchAttack(attacker_id)
        return CarouselAttack(attacker_id)

    def _packet_options(self) -> dict[str, str | int]:
        source = self.source_input.currentText().strip()
        destination = self.destination_input.currentText().strip()
        if not source or not destination:
            raise ValueError("Source and destination must both be provided.")
        return {
            "source": source,
            "destination": destination,
            "packet_size": self.packet_size_input.value(),
            "ttl": self.ttl_input.value(),
        }

    def _run_simulation(self) -> None:
        if self._thread is not None:
            return
        try:
            options = self._packet_options()
            attack = self._selected_attack()
            scenario = self.scenario_input.currentText()
            self._run_energy_start = sum(
                node.energy for node in self.simulator.network.nodes.values()
            )
            result_index = len(self.simulator.get_results())
            self._result_start_index = result_index
            self._scenario_labels[result_index] = scenario
            self._launch_worker(
                "simulation",
                options,
                attack=attack,
                description=f"Running {scenario.lower()} simulation",
            )
        except (KeyError, TypeError, ValueError) as error:
            self._show_message("Simulation error", str(error))

    def _run_experiment(self) -> None:
        if self._thread is not None:
            return
        try:
            options = self._packet_options()
            attacker_id = self.attacker_input.currentText().strip()
            if not attacker_id:
                raise ValueError("Enter an attacker node ID for the experiment.")
            if attacker_id not in self.simulator.network.nodes:
                raise ValueError(f"Attacker node {attacker_id!r} is not in the network.")
            sink = self.simulator.network.sink
            if sink is not None and attacker_id == sink.id:
                raise ValueError("The sink cannot be selected as an attacker.")
            self._run_energy_start = sum(
                node.energy for node in self.simulator.network.nodes.values()
            )
            self._result_start_index = len(self.simulator.get_results())
            self._launch_worker(
                "experiment",
                {**options, "attacker_node_id": attacker_id},
                description="Running normal, Stretch, and Carousel scenarios",
            )
        except (KeyError, TypeError, ValueError) as error:
            self._show_message("Experiment error", str(error))

    def _launch_worker(
        self,
        operation: str,
        options: dict[str, str | int],
        *,
        description: str,
        attack: StretchAttack | CarouselAttack | None = None,
    ) -> None:
        self._delivery_popup_shown = False
        self.network_view.reset_animation()
        self.packet_label.setText("Packet: waiting for first transmission")
        self.route_label.setText("Route: waiting for first transmission")
        self._set_metric_packet_status("—")
        self.metric_hops.setText("—")
        self.metric_energy.setText("—")
        self.metric_alive.setText("—")
        self.metric_ttl.setText("—")
        self._set_status(description, "running")
        self._set_running(True)

        thread = QThread(self)
        worker = SimulationWorker(self.simulator, operation, options, attack)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.completed.connect(self._show_completion)
        worker.failed.connect(self._show_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._worker_finished)
        self._thread = thread
        self._worker = worker
        thread.start()

    def _show_progress(self, event: object, gate: object) -> None:
        if not isinstance(event, dict) or not isinstance(gate, Event):
            return
        self._current_gate = gate
        self._packet_progress = 0.0
        self.network_view.show_progress(event)
        sender = str(event["sender"])
        receiver = str(event["receiver"])
        route = event.get("route", [])
        if isinstance(route, list):
            self.route_label.setText(f"Route taken: {'  →  '.join(map(str, route))}")
        scenario = event.get("scenario")
        scenario_prefix = f"{str(scenario).title()} | " if scenario else ""
        self.packet_label.setText(
            f"{scenario_prefix}Packet: {event['status']} | "
            f"{event['hops']} hops | {sender} -> {receiver}"
        )
        self._set_status(
            f"{scenario_prefix}{str(event.get('route_kind', 'normal')).title()} route",
            "running",
        )
        self._set_metric_packet_status(str(event.get("status", "—")).title())
        self.metric_hops.setText(str(event.get("hops", "—")))
        energy = event.get("node_energy")
        if isinstance(energy, dict):
            self.metric_energy.setText(
                self._format_energy(
                    self._run_energy_start
                    - sum(
                        value
                        for value in energy.values()
                        if isinstance(value, (int, float))
                    )
                )
            )
            if event.get("scenario") is None:
                self.metric_alive.setText(
                    str(sum(node.alive for node in self.simulator.network.nodes.values()))
                )
        hops = event.get("hops")
        if isinstance(hops, int):
            self.metric_ttl.setText(str(max(0, self.ttl_input.value() - hops)))
        if not self._paused:
            self._animation_timer.start()

    def _advance_animation(self) -> None:
        self._packet_progress = min(1.0, self._packet_progress + 0.016 / 0.65)
        self.network_view.set_packet_progress(self._packet_progress)
        if self._packet_progress >= 1.0:
            self._animation_timer.stop()
            gate = self._current_gate
            self._current_gate = None
            if gate is not None:
                gate.set()

    def _start_animation(self) -> None:
        if self._thread is None:
            self._run_simulation()
        else:
            self._paused = False
            if self._current_gate is not None and not self._animation_timer.isActive():
                self._animation_timer.start()
                self._set_status("Animation resumed", "running")

    def _pause_animation(self) -> None:
        self._paused = True
        self._animation_timer.stop()
        if self._thread is not None:
            self._set_status("Animation paused", "running")

    def _reset_animation(self) -> None:
        if self._thread is not None:
            return
        self._animation_timer.stop()
        self.network_view.reset_animation()
        self.packet_label.setText("Packet: idle")
        self._set_status("Animation reset; simulation state is unchanged")

    def _show_completion(self, operation: str, result: object) -> None:
        show_delivery_popup = False
        if operation == "simulation":
            status = getattr(result, "status", None)
            hops = getattr(result, "hops", 0)
            status_name = getattr(status, "name", "unknown")
            self._set_status(
                f"Simulation complete · {status_name.title()} · {hops} hops",
                status_name.lower(),
            )
            route = getattr(result, "route", [])
            if isinstance(route, list):
                self.route_label.setText(f"Route taken: {'  →  '.join(route)}")
            self._set_metric_packet_status(status_name.title())
            self.metric_hops.setText(str(hops))
            self.metric_ttl.setText(str(getattr(result, "ttl", "—")))
            self.packet_label.setText(
                f"Packet: {status_name.title()} | {hops} hops | "
                f"TTL {getattr(result, 'ttl', '—')} remaining"
            )
            results = self.simulator.get_results()
            if self._result_start_index < len(results):
                self._set_metrics_from_result(results[self._result_start_index])
                recorded_status = str(
                    results[self._result_start_index].get("packet_status", "")
                ).upper()
                sink = self.simulator.network.sink
                destination = getattr(result, "destination", None)
                show_delivery_popup = (
                    status_name.upper() == "DELIVERED"
                    and recorded_status == "DELIVERED"
                    and sink is not None
                    and destination == sink.id
                )
        else:
            count = len(result) if isinstance(result, list) else 0
            latest_status = (
                str(result[-1].get("packet_status", ""))
                if isinstance(result, list) and result
                and isinstance(result[-1], Mapping)
                else ""
            )
            self._set_status(
                f"Experiment complete · {count} scenarios",
                latest_status.lower(),
            )
            results = self.simulator.get_results()
            if results:
                self._set_metrics_from_result(results[-1])
            self.metric_ttl.setText("—")
        self._refresh_results()
        if show_delivery_popup and not self._delivery_popup_shown:
            self._delivery_popup_shown = True
            result_row = self.simulator.get_results()[self._result_start_index]
            scenario = self._scenario_labels.get(
                self._result_start_index,
                self.scenario_input.currentText(),
            )
            energy = self._format_energy(
                result_row.get("total_energy_consumed")
            )
            ttl = getattr(result, "ttl", "—")
            dialog = PacketDeliveredDialog(
                scenario=scenario,
                hops=getattr(result, "hops", "—"),
                energy=energy,
                ttl=ttl,
                parent=self,
            )
            dialog.exec_()

    def _set_metrics_from_result(self, result: Mapping[str, ResultValue]) -> None:
        self._set_metric_packet_status(
            str(result.get("packet_status", "—")).title()
        )
        self.metric_hops.setText(str(result.get("hops", "—")))
        self.metric_energy.setText(
            self._format_energy(result.get("total_energy_consumed"))
        )
        self.metric_alive.setText(str(result.get("alive_nodes", "—")))

    def _show_error(self, message: str) -> None:
        self._set_status(f"Simulation failed: {message}", "error")
        self._show_message("Simulation error", message)

    def _show_message(self, title: str, message: str) -> None:
        StatusMessageDialog(title, message, self).exec_()

    def _worker_finished(self) -> None:
        thread = self._thread
        self._thread = None
        self._worker = None
        self._current_gate = None
        if thread is not None:
            thread.deleteLater()
        self._paused = False
        self._set_running(False)

    def closeEvent(self, event) -> None:
        self._animation_timer.stop()
        if self._worker is not None:
            self._worker.stop_event.set()
        if self._current_gate is not None:
            self._current_gate.set()
        if self._thread is not None:
            self._thread.wait()
        event.accept()

    def _set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.experiment_button.setEnabled(not running)
        self.export_button.setEnabled(not running)
        self.start_button.setEnabled(True)
        self.start_button.setText("Resume" if running else "Start")
        self.pause_button.setEnabled(running)
        self.reset_button.setEnabled(not running)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export simulation results",
            "simulation_results.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            self.simulator.export_results_csv(path)
            self.status_label.setText(f"Results exported to {path}")
        except OSError as error:
            self._show_message("Export error", str(error))

    def _refresh_results(self) -> None:
        results = self.simulator.get_results()
        self.results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            values = (
                self._scenario_labels.get(row, self._scenario_name(result)),
                str(result.get("packet_status", "")),
                str(result.get("hops", "")),
                self._format_energy(result.get("total_energy_consumed")),
                str(result.get("alive_nodes", "")),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1:
                    status = value.upper()
                    if status == "DELIVERED":
                        item.setForeground(QColor("#16A34A"))
                    elif status in {"EXPIRED", "DROPPED", "FAILED"}:
                        item.setBackground(QColor("#EA580C"))
                        item.setForeground(QColor("#FFFFFF"))
                self.results_table.setItem(row, column, item)

    @staticmethod
    def _format_energy(value: object) -> str:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return str(value) if value is not None else ""
        return f"{value:.6g}"

    @staticmethod
    def _scenario_name(result: Mapping[str, ResultValue]) -> str:
        scenario = result.get("scenario")
        if isinstance(scenario, str):
            return scenario.title()
        return "Attack" if result.get("attack_used") is True else "Normal"

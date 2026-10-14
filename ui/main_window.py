from __future__ import annotations

from collections.abc import Mapping
from threading import Event
from time import perf_counter

from PyQt5.QtCore import QObject, QPoint, QSize, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
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
    QProgressBar,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygon

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from simulator import Simulator
from visualization.live_network_view import LiveNetworkView


ResultValue = str | int | float | bool
ENERGY_PERCENT_SCALE = 1


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
                background: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
            }
            QLabel#successIcon {
                background: #4B8845;
                color: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
                font-size: 24pt;
                font-weight: 900;
            }
            QLabel#successTitle {
                color: #34251E;
                font-family: "Courier New";
                font-size: 13pt;
                font-weight: 900;
            }
            QLabel#successMessage {
                color: #34251E;
                font-size: 9pt;
                padding-bottom: 2px;
            }
            QLabel#detailLabel {
                color: #795D4A;
                font-size: 9pt;
            }
            QLabel#detailValue {
                color: #34251E;
                font-size: 9pt;
                font-weight: 900;
            }
            QPushButton#continueButton {
                background: #4B8845;
                color: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
                min-height: 30px;
                padding: 3px 14px;
                font-size: 9pt;
                font-weight: 900;
            }
            QPushButton#continueButton:hover {
                background: #5D9B55;
                color: #FFF7E9;
            }
            QPushButton#continueButton:pressed {
                background: #795D4A;
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
                background: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
            }
            QLabel#messageIcon {
                background: #D95735;
                color: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
                font-size: 14pt;
                font-weight: 900;
            }
            QLabel#messageTitle {
                color: #34251E;
                font-family: "Courier New";
                font-size: 10pt;
                font-weight: 900;
            }
            QLabel#messageBody {
                color: #34251E;
                font-size: 9pt;
            }
            QPushButton#messageButton {
                background: #4B8845;
                color: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
                min-height: 28px;
                padding: 2px 12px;
                font-size: 9pt;
                font-weight: 900;
            }
            QPushButton#messageButton:hover {
                background: #5D9B55;
                color: #FFF7E9;
            }
            QPushButton#messageButton:pressed {
                background: #795D4A;
                color: #FFF7E9;
                border-color: #34251E;
            }
            QFrame#controlsPanel, QFrame#detailsPanel {
                border-top-color: #C4936B;
                border-left-color: #C4936B;
            }
            """
        )


class SimulationWorker(QObject):
    progress = pyqtSignal(int, object, object)
    completed = pyqtSignal(int, str, object)
    failed = pyqtSignal(int, str)
    finished = pyqtSignal()

    def __init__(
        self,
        simulator: Simulator,
        operation: str,
        options: dict[str, str | int],
        generation: int,
        attack: StretchAttack | CarouselAttack | None = None,
    ) -> None:
        super().__init__()
        self.simulator = simulator
        self.operation = operation
        self.options = options
        self.generation = generation
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
                    on_transmission_start=self._report_progress,
                    on_reception=self._report_progress,
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
                    on_transmission_start=self._report_progress,
                    on_reception=self._report_progress,
                )
            if not self.stop_event.is_set():
                self.completed.emit(self.generation, self.operation, result)
        except SimulationCancelled:
            pass
        except Exception as error:
            if not self.stop_event.is_set():
                self.failed.emit(self.generation, str(error))
        finally:
            self.simulator.attack = original_attack
            self.finished.emit()

    def _report_progress(self, event: dict[str, object]) -> None:
        if self.stop_event.is_set():
            raise SimulationCancelled
        gate = Event()
        self.progress.emit(self.generation, event, gate)
        while not gate.wait(0.1):
            if self.stop_event.is_set():
                raise SimulationCancelled
        if self.stop_event.is_set():
            raise SimulationCancelled


class SimulationCancelled(Exception):
    """Stop a worker before it can record a partial packet as a result."""


class SimulatorMainWindow(QMainWindow):
    """Retro strategy-game interface for the vampire attack simulator."""

    worker_thread_finished = pyqtSignal(int)

    def __init__(self, simulator: Simulator) -> None:
        super().__init__()
        self.simulator = simulator
        self._original_attack = simulator.attack
        self._scenario_labels: dict[int, str] = {}
        self._scenario = "Normal"
        self._run_generation = 0
        self._result_start_index = 0
        self._run_energy_start = 0.0
        self._displayed_energy: dict[str, object] | None = None
        self._reported_dead_nodes: set[str] = set()
        self._run_alive_start: dict[str, bool] = {}
        self._progress_scenario: str | None = None
        self._delivery_popup_shown = False
        self._active_packet = False
        self._thread: QThread | None = None
        self._worker: SimulationWorker | None = None
        self._current_gate: Event | None = None
        self._packet_progress = 0.0
        self._pending_hop_event: dict[str, object] | None = None
        self._paused = False
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._advance_animation)
        self.worker_thread_finished.connect(self._worker_finished)

        self._run_started_at = 0.0
        self.setWindowTitle("Vampire Attack Simulator")
        self.resize(1360, 900)
        self.setMinimumSize(980, 700)

        central_widget = QWidget(self)
        central_widget.setObjectName("application")
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title = QLabel("VAMPIRE ATTACK SIMULATOR")
        title.setObjectName("title")
        subtitle = QLabel("WIRELESS SENSOR NETWORK // STRATEGY SIMULATOR")
        subtitle.setObjectName("subtitle")
        shield = QLabel()
        shield.setObjectName("gameShield")
        shield.setPixmap(self._pixel_icon_pixmap("shield", 36))
        header.addWidget(shield, 0, Qt.AlignVCenter)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addLayout(title_block)
        header.addStretch(1)
        self.status_label = QLabel("READY")
        self.status_label.setObjectName("statusIndicator")
        header.addWidget(self.status_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        root_layout.addLayout(header)

        hud = QHBoxLayout()
        hud.setSpacing(8)
        self.hud_packets = self._add_hud_stat(hud, "PACKETS", "0")
        self.hud_ttl = self._add_hud_stat(hud, "TTL LEFT", "50")
        energy_card = QFrame()
        energy_card.setObjectName("hudCard")
        energy_layout = QVBoxLayout(energy_card)
        energy_layout.setContentsMargins(10, 6, 10, 6)
        energy_layout.setSpacing(3)
        energy_layout.addWidget(self._hud_caption("NETWORK ENERGY"))
        self.hud_energy = QLabel("—")
        self.hud_energy.setObjectName("hudValue")
        energy_layout.addWidget(self.hud_energy)
        self.hud_energy_bar = QProgressBar()
        self.hud_energy_bar.setObjectName("energyBar")
        self.hud_energy_bar.setRange(0, 100 * ENERGY_PERCENT_SCALE)
        self.hud_energy_bar.setTextVisible(False)
        self.hud_energy_bar.setFixedHeight(9)
        energy_layout.addWidget(self.hud_energy_bar)
        hud.addWidget(energy_card, 2)
        self.hud_state = self._add_hud_stat(hud, "SIMULATION", "READY")
        self.hud_mode = self._add_hud_stat(hud, "MODE", "NORMAL")
        hud.setStretch(0, 1)
        hud.setStretch(1, 1)
        hud.setStretch(2, 2)
        hud.setStretch(3, 1)
        root_layout.addLayout(hud)

        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.setHandleWidth(6)

        controls_panel = QScrollArea()
        controls_panel.setObjectName("controlsPanel")
        controls_panel.setWidgetResizable(True)
        controls_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        controls_panel.setMinimumWidth(215)
        controls_panel.setMaximumWidth(290)
        controls_content = QWidget()
        controls_content.setObjectName("controlsContent")
        controls_layout = QVBoxLayout(controls_content)
        controls_layout.setContentsMargins(8, 12, 8, 12)
        controls_layout.setSpacing(9)

        controls_heading = QLabel("MISSION SETUP")
        controls_heading.setObjectName("sectionHeading")
        controls_layout.addWidget(controls_heading)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(7)
        node_ids = list(self.simulator.network.nodes)
        sink = self.simulator.network.sink
        sink_id = sink.id if sink is not None else None
        sensor_ids = [node_id for node_id in node_ids if node_id != sink_id]

        self.source_input = QComboBox()
        self.source_input.addItems(node_ids)
        self._default_source_id = self._preferred_node_id("N1", node_ids)
        self.source_input.setCurrentText(self._default_source_id)
        self.destination_input = QComboBox()
        self.destination_input.addItems(node_ids)
        self._default_destination_id = self._preferred_node_id(
            sink_id or "SINK", node_ids
        )
        self.destination_input.setCurrentText(self._default_destination_id)
        self.attacker_input = QComboBox()
        self.attacker_input.setObjectName("attackerInput")
        self.attacker_input.addItems(sensor_ids)
        attacker_default = "N2"
        if attacker_default not in sensor_ids and self.simulator.attack is not None:
            attacker_default = self.simulator.attack.attacker_node_id
        self._default_attacker_id = self._preferred_node_id(
            attacker_default, sensor_ids
        )
        self.attacker_input.setCurrentText(self._default_attacker_id)
        for node_input in (
            self.source_input,
            self.destination_input,
            self.attacker_input,
        ):
            node_input.setMinimumWidth(65)
        self.packet_size_input = QComboBox()
        for packet_size in range(1000, 10_001, 500):
            self.packet_size_input.addItem(str(packet_size), packet_size)
        self.packet_size_input.setCurrentText("4000")
        self.ttl_input = QComboBox()
        for ttl in range(10, 101, 10):
            self.ttl_input.addItem(str(ttl), ttl)
        self.ttl_input.setCurrentText("50")
        self.attacker_input.currentTextChanged.connect(self._refresh_attacker)
        self.ttl_input.currentTextChanged.connect(self._update_ttl_controls)

        form.addRow("SOURCE", self.source_input)
        form.addRow("DESTINATION", self.destination_input)
        form.addRow("ATTACKER", self.attacker_input)
        form.addRow("PACKET BITS", self.packet_size_input)
        form.addRow("START TTL", self.ttl_input)
        controls_layout.addLayout(form)

        self.run_button = QPushButton("RUN SIMULATION")
        self.run_button.setObjectName("primaryButton")
        self.run_button.setIcon(self._pixel_icon("play", "#FFF7E9"))
        self.run_button.setIconSize(self._icon_size(18))
        self.run_button.setText("RUN NORMAL")
        self.run_button.setCheckable(True)
        self.run_button.clicked.connect(self._run_normal_simulation)
        controls_layout.addWidget(self.run_button)
        self.stretch_button = QPushButton("STRETCH ATTACK")
        self.stretch_button.setObjectName("attackButton")
        self.stretch_button.setIcon(self._pixel_icon("bolt", "#FFF7E9"))
        self.stretch_button.setIconSize(self._icon_size(18))
        self.stretch_button.setCheckable(True)
        self.stretch_button.clicked.connect(self._run_stretch_simulation)
        controls_layout.addWidget(self.stretch_button)
        self.carousel_button = QPushButton("CAROUSEL ATTACK")
        self.carousel_button.setObjectName("attackButton")
        self.carousel_button.setIcon(self._pixel_icon("bolt", "#FFF7E9"))
        self.carousel_button.setIconSize(self._icon_size(18))
        self.carousel_button.setCheckable(True)
        self.carousel_button.clicked.connect(self._run_carousel_simulation)
        controls_layout.addWidget(self.carousel_button)
        self.scenario_buttons = QButtonGroup(self)
        self.scenario_buttons.setExclusive(True)
        for scenario_button in (
            self.run_button,
            self.stretch_button,
            self.carousel_button,
        ):
            self.scenario_buttons.addButton(scenario_button)
        self.run_button.setChecked(True)

        playback = QHBoxLayout()
        playback.setContentsMargins(0, 0, 0, 0)
        playback.setSpacing(3)
        self.start_button = QPushButton("START")
        self.start_button.setIcon(self._pixel_icon("play", "#4B8845"))
        self.start_button.setIconSize(self._icon_size(12))
        self.start_button.clicked.connect(self._start_animation)
        self.pause_button = QPushButton("PAUSE")
        self.pause_button.setIcon(self._pixel_icon("pause", "#34251E"))
        self.pause_button.setIconSize(self._icon_size(12))
        self.pause_button.clicked.connect(self._pause_animation)
        self.reset_button = QPushButton("RESET")
        self.reset_button.setObjectName("resetButton")
        self.reset_button.setIcon(self._pixel_icon("reset", "#FFF7E9"))
        self.reset_button.setIconSize(self._icon_size(12))
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
        secondary_actions.setContentsMargins(0, 0, 0, 0)
        secondary_actions.setSpacing(6)
        self.experiment_button = QPushButton("COMPARE")
        self.experiment_button.setObjectName("secondaryButton")
        self.experiment_button.setIcon(self._pixel_icon("chart", "#34251E"))
        self.experiment_button.setIconSize(self._icon_size(14))
        self.experiment_button.clicked.connect(self._run_experiment)
        self.export_button = QPushButton("EXPORT CSV")
        self.export_button.setIcon(self._pixel_icon("file", "#34251E"))
        self.export_button.setIconSize(self._icon_size(14))
        self.export_button.clicked.connect(self._export_csv)
        secondary_actions.addWidget(self.experiment_button)
        secondary_actions.addWidget(self.export_button)
        controls_layout.addLayout(secondary_actions)
        controls_layout.addStretch(1)
        controls_panel.setWidget(controls_content)

        network_panel = QFrame()
        network_panel.setObjectName("networkPanel")
        network_panel.setMinimumWidth(360)
        network_layout = QVBoxLayout(network_panel)
        network_layout.setContentsMargins(12, 12, 12, 12)
        network_layout.setSpacing(8)
        network_header = QHBoxLayout()
        network_heading = QLabel("NETWORK MAP")
        network_heading.setObjectName("sectionHeading")
        network_header.addWidget(network_heading)
        network_header.addStretch(1)
        self.packet_label = QLabel("PACKET // IDLE")
        self.packet_label.setObjectName("packetStatus")
        network_header.addWidget(self.packet_label)
        network_layout.addLayout(network_header)
        self.network_view = LiveNetworkView(self.simulator.network)
        self.network_view.setMinimumHeight(300)
        self.network_view.setMinimumWidth(330)
        network_layout.addWidget(self.network_view, 1)

        detail_panel = QFrame()
        detail_panel.setObjectName("detailsPanel")
        detail_panel.setMinimumWidth(205)
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(9)
        detail_heading = QLabel("PACKET READOUT")
        detail_heading.setObjectName("sectionHeading")
        detail_layout.addWidget(detail_heading)

        character_card = QFrame()
        character_card.setObjectName("characterCard")
        character_layout = QHBoxLayout(character_card)
        character_layout.setContentsMargins(8, 6, 8, 6)
        character_layout.setSpacing(10)
        self.character_preview = QLabel()
        self.character_preview.setObjectName("characterPreview")
        self.character_preview.setPixmap(self._pixel_character_pixmap(1.0, 4))
        self.character_preview.setFixedSize(64, 64)
        self.character_preview.setAlignment(Qt.AlignCenter)
        character_layout.addWidget(self.character_preview)
        character_metrics = QVBoxLayout()
        character_metrics.setSpacing(4)
        character_metrics.addWidget(self._hud_caption("TTL"))
        self.readout_ttl_value = QLabel(self.ttl_input.currentText())
        self.readout_ttl_value.setObjectName("readoutValue")
        character_metrics.addWidget(self.readout_ttl_value)
        self.readout_ttl_bar = QProgressBar()
        self.readout_ttl_bar.setObjectName("ttlBar")
        self.readout_ttl_bar.setRange(0, int(self.ttl_input.currentText()))
        self.readout_ttl_bar.setValue(int(self.ttl_input.currentText()))
        self.readout_ttl_bar.setTextVisible(False)
        self.readout_ttl_bar.setFixedHeight(9)
        character_metrics.addWidget(self.readout_ttl_bar)
        character_layout.addLayout(character_metrics, 1)
        detail_layout.addWidget(character_card)

        route_caption = self._hud_caption("ACTIVE ROUTE")
        detail_layout.addWidget(route_caption)
        self.route_label = QLabel("Awaiting transmission")
        self.route_label.setObjectName("routeLabel")
        self.route_label.setWordWrap(True)
        detail_layout.addWidget(self.route_label)
        readout_form = QFormLayout()
        readout_form.setContentsMargins(0, 4, 0, 0)
        readout_form.setHorizontalSpacing(8)
        readout_form.setVerticalSpacing(10)
        self.metric_status = self._add_readout_value(readout_form, "PACKET")
        self.metric_hops = self._add_readout_value(readout_form, "HOPS")
        self.metric_ttl = self._add_readout_value(readout_form, "TTL LEFT")
        self.metric_energy = self._add_readout_value(readout_form, "ENERGY USED")
        self.metric_alive = self._add_readout_value(readout_form, "NODES ALIVE")
        self.attacker_status_label = self._add_readout_value(
            readout_form, "VAMPIRE"
        )
        detail_layout.addLayout(readout_form)
        energy_caption = self._hud_caption("NETWORK ENERGY")
        detail_layout.addWidget(energy_caption)
        self.readout_energy_bar = QProgressBar()
        self.readout_energy_bar.setObjectName("energyBar")
        self.readout_energy_bar.setRange(0, 100 * ENERGY_PERCENT_SCALE)
        self.readout_energy_bar.setTextVisible(False)
        self.readout_energy_bar.setFixedHeight(10)
        detail_layout.addWidget(self.readout_energy_bar)
        detail_layout.addStretch(1)

        content.addWidget(controls_panel)
        content.addWidget(network_panel)
        content.addWidget(detail_panel)
        content.setStretchFactor(0, 0)
        content.setStretchFactor(1, 1)
        content.setStretchFactor(2, 0)
        content.setSizes([245, 720, 245])
        root_layout.addWidget(content, 5)

        results_panel = QFrame()
        results_panel.setObjectName("resultsPanel")
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(10, 8, 10, 8)
        results_layout.setSpacing(4)
        self.results_tabs = QTabWidget()
        self.results_tabs.setObjectName("logTabs")
        self.event_table = QTableWidget(0, 5)
        self.event_table.setHorizontalHeaderLabels(
            ["TIME", "NODE", "EVENT", "DETAILS", "STATUS"]
        )
        event_header = self.event_table.horizontalHeader()
        event_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        event_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        event_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        event_header.setSectionResizeMode(3, QHeaderView.Stretch)
        event_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._prepare_table(self.event_table)
        self.event_table.setMinimumHeight(130)
        self.results_tabs.addTab(self.event_table, "EVENT LOG")

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["SCENARIO", "STATUS", "HOPS", "ENERGY USED (J)", "NODES ALIVE"]
        )
        result_header = self.results_table.horizontalHeader()
        result_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        result_header.setStretchLastSection(True)
        self._prepare_table(self.results_table)
        self.results_tabs.addTab(self.results_table, "RUN RESULTS")
        results_layout.addWidget(self.results_tabs)
        root_layout.addWidget(results_panel, 2)

        self.setStyleSheet(self._application_stylesheet())
        self._refresh_attacker()
        self._refresh_results()
        self._refresh_hud()

    def _select_scenario(self, scenario: str) -> None:
        self._scenario = scenario
        self.hud_mode.setText(scenario.upper())
        button = {
            "Normal": self.run_button,
            "Stretch": self.stretch_button,
            "Carousel": self.carousel_button,
        }[scenario]
        button.setChecked(True)
        self._refresh_attacker()

    def _set_status(self, text: str, state: str = "idle") -> None:
        display_text = {
            "running": "SIMULATION RUNNING...",
            "delivered": "PACKET DELIVERED",
            "expired": "PACKET LOST · TTL",
            "dropped": "PACKET DROPPED",
            "failed": "PACKET FAILED · NO ROUTE",
            "error": "SIMULATION FAILED",
        }.get(state, text.upper())
        self.status_label.setText(display_text)
        if hasattr(self, "hud_state"):
            short_status = {
                "running": "RUNNING",
                "delivered": "DELIVERED",
                "expired": "TTL EXPIRED",
                "dropped": "DROPPED",
                "failed": "FAILED",
                "error": "FAILED",
            }
            self.hud_state.setText(short_status.get(state, text.upper()[:18]))
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_metric_packet_status(self, value: str) -> None:
        self.metric_status.setText(value)
        state = value.casefold()
        self.metric_status.setProperty(
            "state",
            state if state in {"delivered", "expired", "dropped", "failed"} else "",
        )
        self.metric_status.style().unpolish(self.metric_status)
        self.metric_status.style().polish(self.metric_status)

    def _refresh_hud(
        self,
        *,
        ttl: object | None = None,
        energy: Mapping[str, object] | None = None,
    ) -> None:
        completed_packets = len(self.simulator.get_results())
        self.hud_packets.setText(
            str(completed_packets + int(self._active_packet))
        )
        if ttl is None:
            ttl = int(self.ttl_input.currentText())
        self.hud_ttl.setText(str(ttl))
        try:
            ttl_value = max(0, int(ttl))
        except (TypeError, ValueError):
            ttl_value = 0
        ttl_maximum = max(1, int(self.ttl_input.currentText()))
        self.readout_ttl_value.setText(str(ttl))
        self.readout_ttl_bar.setMaximum(ttl_maximum)
        self.readout_ttl_bar.setValue(min(ttl_value, ttl_maximum))
        ttl_state = (
            "danger"
            if ttl_value / ttl_maximum <= 0.3
            else "warning"
            if ttl_value / ttl_maximum <= 0.6
            else ""
        )
        self.readout_ttl_bar.setProperty("state", ttl_state)
        self.readout_ttl_bar.style().unpolish(self.readout_ttl_bar)
        self.readout_ttl_bar.style().polish(self.readout_ttl_bar)
        self.character_preview.setPixmap(
            self._pixel_character_pixmap(ttl_value / ttl_maximum, 4)
        )

        if energy is not None:
            self._displayed_energy = dict(energy)
        energy_state = self._displayed_energy
        remaining_energy = (
            sum(
                value
                for value in energy_state.values()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            )
            if energy_state is not None
            else sum(node.energy for node in self.simulator.network.nodes.values())
        )
        total_energy = sum(
            node.initial_energy for node in self.simulator.network.nodes.values()
        )
        energy_percent = (
            max(0.0, min(100.0, 100 * remaining_energy / total_energy))
            if total_energy > 0
            else 0.0
        )
        self.hud_energy.setText(f"{energy_percent:.0f}%")
        energy_bar_value = round(energy_percent * ENERGY_PERCENT_SCALE)
        self.hud_energy_bar.setValue(energy_bar_value)
        self.readout_energy_bar.setValue(self.hud_energy_bar.value())

    def _update_ttl_controls(self, value: str) -> None:
        ttl = int(value)
        self.hud_ttl.setText(str(ttl))
        self.readout_ttl_value.setText(str(ttl))
        self.readout_ttl_bar.setMaximum(max(1, ttl))
        self.readout_ttl_bar.setValue(ttl)
        self.readout_ttl_bar.setProperty("state", "")
        self.readout_ttl_bar.style().unpolish(self.readout_ttl_bar)
        self.readout_ttl_bar.style().polish(self.readout_ttl_bar)
        self.character_preview.setPixmap(self._pixel_character_pixmap(1.0, 4))

    def _append_event(
        self,
        node: str,
        event_name: str,
        details: str,
        status: str,
        *,
        alarm: bool = False,
    ) -> None:
        elapsed = max(0.0, perf_counter() - self._run_started_at)
        minutes, remaining_seconds = divmod(elapsed, 60)
        timestamp = f"{int(minutes):02}:{remaining_seconds:06.3f}"
        row = self.event_table.rowCount()
        self.event_table.insertRow(row)
        values = (timestamp, node, event_name, details, status.upper())
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 4:
                normalized_status = status.upper()
                if normalized_status in {"DELIVERED", "COMPLETE", "RUNNING"}:
                    item.setForeground(QColor("#4B8845"))
                elif normalized_status in {"IN_TRANSIT", "IN PROGRESS"}:
                    item.setForeground(QColor("#A16B2D"))
                elif normalized_status == "ATTACKER":
                    item.setForeground(QColor("#D95735"))
                elif normalized_status in {"EXPIRED", "DROPPED", "FAILED"}:
                    item.setForeground(QColor("#D95735"))
            if alarm:
                item.setForeground(QColor("#D95735"))
            self.event_table.setItem(row, column, item)
        self.event_table.scrollToBottom()

    def _run_stretch_simulation(self) -> None:
        if self._thread is not None:
            return
        self._select_scenario("Stretch")
        self._run_simulation()

    def _run_normal_simulation(self) -> None:
        if self._thread is not None:
            return
        self._select_scenario("Normal")
        self._run_simulation()

    def _run_carousel_simulation(self) -> None:
        if self._thread is not None:
            return
        self._select_scenario("Carousel")
        self._run_simulation()

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
    def _hud_caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hudCaption")
        return label

    @staticmethod
    def _icon_size(size: int) -> QSize:
        return QSize(size, size)

    @staticmethod
    def _pixel_icon_pixmap(kind: str, size: int = 16) -> QPixmap:
        image = QPixmap(size, size)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.scale(size / 16, size / 16)
        dark = QColor("#34251E")
        fill = QColor("#4B8845")
        painter.setPen(Qt.NoPen)
        if kind == "shield":
            painter.setBrush(dark)
            for x, y, width, height in (
                (3, 1, 10, 3), (1, 3, 14, 7), (2, 9, 12, 3),
                (4, 12, 8, 2), (6, 14, 4, 1),
            ):
                painter.drawRect(x, y, width, height)
            painter.setBrush(fill)
            for x, y, width, height in (
                (4, 2, 8, 2), (3, 4, 10, 5), (4, 9, 8, 2),
                (6, 11, 4, 2),
            ):
                painter.drawRect(x, y, width, height)
            painter.setBrush(QColor("#F0C84B"))
            painter.drawRect(7, 5, 2, 5)
            painter.drawRect(5, 7, 6, 2)
        elif kind == "play":
            painter.setBrush(fill)
            painter.drawPolygon(QPolygon([QPoint(4, 2), QPoint(13, 8), QPoint(4, 14)]))
        elif kind == "bolt":
            painter.setBrush(fill)
            painter.drawPolygon(
                QPolygon(
                    [
                        QPoint(9, 1), QPoint(3, 9), QPoint(7, 9),
                        QPoint(6, 15), QPoint(13, 6), QPoint(9, 6),
                    ]
                )
            )
        elif kind == "pause":
            painter.setBrush(fill)
            painter.drawRect(3, 3, 4, 10)
            painter.drawRect(9, 3, 4, 10)
        elif kind == "reset":
            painter.setBrush(fill)
            painter.drawRect(3, 3, 9, 3)
            painter.drawRect(2, 5, 3, 6)
            painter.drawRect(4, 10, 8, 3)
            painter.drawRect(10, 7, 3, 4)
            painter.setBrush(QColor("#FFF7E9"))
            painter.drawRect(6, 6, 4, 3)
        elif kind == "chart":
            painter.setBrush(fill)
            painter.drawRect(2, 8, 3, 6)
            painter.drawRect(7, 4, 3, 10)
            painter.drawRect(12, 1, 3, 13)
        elif kind == "file":
            painter.setBrush(dark)
            painter.drawRect(3, 1, 10, 14)
            painter.setBrush(QColor("#FFF7E9"))
            painter.drawRect(5, 3, 6, 2)
            painter.drawRect(5, 7, 6, 1)
            painter.drawRect(5, 10, 6, 1)
        painter.end()
        return image

    @classmethod
    def _pixel_icon(cls, kind: str, color: str) -> QIcon:
        image = cls._pixel_icon_pixmap(kind)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(image.rect(), QColor(color))
        painter.end()
        return QIcon(image)

    @staticmethod
    def _pixel_character_pixmap(ttl_ratio: float, pixel_size: int = 3) -> QPixmap:
        ratio = max(0.0, min(1.0, ttl_ratio))
        body_color = (
            "#4B8845" if ratio > 0.6
            else "#C79B35" if ratio > 0.3
            else "#D95735"
        )
        rows = (
            "....DDDD....",
            "...DGGGGD...",
            "..DGGWWGGD..",
            "..DGGWWGGD..",
            "...DDSSDD...",
            "....SSSS....",
            "...DDDDDD...",
            "..DDCCCCDD..",
            "..DDCCCCDD..",
            "...DCCCCD...",
            "....DCCD....",
            "....D..D....",
            "...DD..DD...",
            "..DDD..DDD..",
        )
        colors = {
            "D": "#34251E",
            "G": "#299C73",
            "W": "#FFF7E9",
            "S": "#E4AA6D",
            "C": body_color,
        }
        image = QPixmap(12 * pixel_size, 14 * pixel_size)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, False)
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                if cell != ".":
                    painter.fillRect(
                        x * pixel_size,
                        y * pixel_size,
                        pixel_size,
                        pixel_size,
                        QColor(colors[cell]),
                    )
        painter.end()
        return image

    @classmethod
    def _add_hud_stat(
        cls,
        layout: QHBoxLayout,
        caption: str,
        value: str,
    ) -> QLabel:
        card = QFrame()
        card.setObjectName("hudCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 7, 10, 7)
        card_layout.setSpacing(2)
        card_layout.addWidget(cls._hud_caption(caption))
        value_label = QLabel(value)
        value_label.setObjectName("hudValue")
        card_layout.addWidget(value_label)
        layout.addWidget(card, 1)
        return value_label

    @staticmethod
    def _add_readout_value(form: QFormLayout, caption: str) -> QLabel:
        label = QLabel(caption)
        label.setObjectName("readoutCaption")
        value = QLabel("—")
        value.setObjectName("readoutValue")
        value.setWordWrap(True)
        form.addRow(label, value)
        return value

    @staticmethod
    def _prepare_table(table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(False)

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
            QLabel#metricValue[state="dropped"],
            QLabel#metricValue[state="failed"] {
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
            QWidget#application {
                background: #F1CDB5;
                color: #34251E;
                font-family: "Courier New";
                font-size: 9pt;
            }
            QFrame#controlsPanel, QFrame#networkPanel,
            QFrame#detailsPanel, QFrame#resultsPanel {
                background: #FFF7E9;
                border: 2px solid #34251E;
                border-radius: 0;
            }
            QScrollArea#controlsPanel {
                background: #FFF7E9;
                border: 2px solid #34251E;
            }
            QWidget#controlsContent {
                background: #FFF7E9;
            }
            QScrollBar:vertical {
                background: #F1CDB5;
                width: 10px;
                margin: 0;
                border: 1px solid #34251E;
            }
            QScrollBar::handle:vertical {
                background: #795D4A;
                min-height: 24px;
                border: 1px solid #34251E;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QFrame#hudCard {
                background: #FFE8D4;
                border: 2px solid #34251E;
                border-radius: 0;
            }
            QFrame#resultsPanel {
                border-top: 2px solid #34251E;
            }
            QLabel#title {
                color: #34251E;
                font-family: "Courier New";
                font-size: 19pt;
                font-weight: 900;
                border-bottom: 3px solid #4B8845;
                padding-bottom: 3px;
            }
            QLabel#subtitle, QLabel#hudCaption, QLabel#readoutCaption {
                color: #795D4A;
                font-family: "Courier New";
                font-size: 8pt;
                font-weight: 700;
            }
            QLabel#hudValue {
                color: #34251E;
                font-family: "Courier New";
                font-size: 12pt;
                font-weight: 900;
            }
            QLabel#statusIndicator {
                background: #FFF7E9;
                color: #34251E;
                border: 2px solid #34251E;
                border-radius: 0;
                padding: 6px 10px;
                font-family: "Courier New";
                font-size: 9pt;
                font-weight: 900;
            }
            QLabel#statusIndicator[state="running"],
            QLabel#statusIndicator[state="delivered"] {
                background: #4B8845;
                color: #FFF7E9;
                border-color: #34251E;
            }
            QLabel#statusIndicator[state="expired"],
            QLabel#statusIndicator[state="dropped"],
            QLabel#statusIndicator[state="failed"],
            QLabel#statusIndicator[state="error"] {
                background: #D95735;
                color: #FFF7E9;
                border-color: #34251E;
            }
            QLabel#sectionHeading {
                color: #34251E;
                font-family: "Courier New";
                font-size: 10pt;
                font-weight: 900;
                border-left: 5px solid #4B8845;
                padding-left: 7px;
            }
            QLabel#packetStatus, QLabel#routeLabel, QLabel#readoutValue {
                color: #34251E;
                font-family: "Courier New";
                font-size: 9pt;
                font-weight: 700;
            }
            QLabel#routeLabel {
                color: #4B8845;
            }
            QLabel#readoutValue[state="delivered"] {
                color: #4B8845;
            }
            QLabel#readoutValue[state="expired"],
            QLabel#readoutValue[state="dropped"],
            QLabel#readoutValue[state="failed"] {
                color: #D95735;
            }
            QLabel#readoutValue[state="selected"],
            QLabel#readoutValue[state="active"] {
                color: #D95735;
                font-weight: 900;
            }
            QSpinBox, QComboBox {
                background: #FFFDF7;
                color: #34251E;
                border: 2px solid #795D4A;
                border-radius: 0;
                min-height: 27px;
                padding: 2px 6px;
                selection-background-color: #4B8845;
            }
            QComboBox#attackerInput {
                border: 2px solid #D95735;
            }
            QSpinBox:focus, QComboBox:focus {
                border: 2px solid #4B8845;
            }
            QComboBox#attackerInput:focus {
                border-color: #D95735;
            }
            QComboBox::drop-down {
                width: 22px;
                border-left: 2px solid #795D4A;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #34251E;
            }
            QComboBox QAbstractItemView {
                background: #FFF7E9;
                color: #34251E;
                border: 2px solid #34251E;
                selection-background-color: #4B8845;
                selection-color: #FFF7E9;
            }
            QComboBox:disabled, QSpinBox:disabled {
                background: #EAD9C8;
                color: #A58C78;
                border-color: #A58C78;
            }
            QPushButton {
                background: #FFF7E9;
                color: #34251E;
                border: 2px solid #34251E;
                border-radius: 0;
                min-height: 29px;
                padding: 3px 7px;
                font-family: "Courier New";
                font-size: 8pt;
                font-weight: 900;
            }
            QPushButton:hover:enabled {
                background: #E9D3BB;
            }
            QPushButton:pressed:enabled {
                background: #795D4A;
                color: #FFF7E9;
                padding-top: 6px;
                padding-left: 10px;
            }
            QPushButton:disabled {
                color: #A58C78;
                background: #EAD9C8;
                border-color: #A58C78;
            }
            QPushButton#primaryButton {
                background: #4B8845;
                color: #FFF7E9;
                border: 3px solid #34251E;
                border-top-color: #83B66D;
                border-left-color: #83B66D;
                min-height: 37px;
                font-size: 9pt;
            }
            QPushButton#primaryButton:hover:enabled {
                background: #5D9B55;
                color: #FFF7E9;
            }
            QPushButton#attackButton {
                background: #E89A36;
                color: #FFF7E9;
                border: 3px solid #34251E;
                border-top-color: #F6C66E;
                border-left-color: #F6C66E;
                min-height: 35px;
            }
            QPushButton#attackButton:hover:enabled {
                background: #F0AD4A;
            }
            QPushButton#attackButton:checked {
                background: #D95735;
                color: #FFF7E9;
            }
            QPushButton#resetButton {
                background: #C83F32;
                color: #FFF7E9;
                border: 2px solid #34251E;
                border-top-color: #ED8068;
                border-left-color: #ED8068;
            }
            QPushButton#resetButton:hover:enabled {
                background: #DE5141;
            }
            QPushButton#resetButton:pressed:enabled {
                background: #9E3028;
                color: #FFF7E9;
            }
            QPushButton#secondaryButton {
                background: #E9B27F;
                color: #34251E;
            }
            QProgressBar#energyBar {
                background: #F1CDB5;
                border: 1px solid #34251E;
                border-radius: 0;
                text-align: center;
            }
            QProgressBar#energyBar::chunk {
                background: #4B8845;
            }
            QProgressBar#ttlBar {
                background: #EAD9C8;
                border: 1px solid #34251E;
                border-radius: 0;
                text-align: center;
            }
            QProgressBar#ttlBar::chunk {
                background: #4B8845;
            }
            QProgressBar#ttlBar[state="warning"]::chunk {
                background: #D8B646;
            }
            QProgressBar#ttlBar[state="danger"]::chunk {
                background: #D95735;
            }
            QFrame#characterCard {
                background: #FFE8D4;
                border: 2px solid #795D4A;
            }
            QLabel#characterPreview {
                background: #FFF7E9;
                border: 2px solid #34251E;
            }
            QLabel#gameShield {
                background: #FFE8D4;
                border: 2px solid #34251E;
                padding: 2px;
            }
            QLabel#title {
                font-size: 16pt;
            }
            QTabWidget#logTabs::pane {
                background: #FFF7E9;
                border: 2px solid #34251E;
                top: -1px;
            }
            QTabBar::tab {
                background: #E9D3BB;
                color: #34251E;
                border: 2px solid #34251E;
                border-bottom: none;
                padding: 4px 6px;
                font-family: "Courier New";
                font-size: 8pt;
                font-weight: 900;
            }
            QTabBar::tab:selected {
                background: #FFF7E9;
                color: #4B8845;
            }
            QTableWidget {
                background: #FFFDF7;
                alternate-background-color: #F9EBDD;
                color: #34251E;
                border: 1px solid #795D4A;
                gridline-color: #E5C9B0;
                selection-background-color: #DDE8D6;
                selection-color: #34251E;
                font-family: "Courier New";
                font-size: 8pt;
            }
            QHeaderView::section {
                background: #E9B27F;
                color: #34251E;
                border: none;
                border-bottom: 2px solid #34251E;
                padding: 5px 7px;
                font-family: "Courier New";
                font-weight: 900;
            }
            QSplitter::handle {
                background: #C99A78;
            }
            QFrame#separator {
                background: #D6B291;
                color: #D6B291;
                max-height: 2px;
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
        valid_attacker = (
            bool(attacker_id)
            and attacker_id in self.simulator.network.nodes
            and (sink is None or attacker_id != sink.id)
        )
        self.network_view.set_attacker(attacker_id if valid_attacker else None)
        attack_selected = valid_attacker and self._scenario != "Normal"
        if hasattr(self, "attacker_status_label"):
            self._set_attacker_status(
                f"SELECTED · {attacker_id}" if attack_selected else "OFF",
                "selected" if attack_selected else "",
            )

    def _set_attacker_status(self, text: str, state: str) -> None:
        self.attacker_status_label.setText(text)
        self.attacker_status_label.setProperty("state", state)
        self.attacker_status_label.style().unpolish(self.attacker_status_label)
        self.attacker_status_label.style().polish(self.attacker_status_label)

    def _selected_attack(self) -> StretchAttack | CarouselAttack | None:
        attacker_id = self.attacker_input.currentText().strip()
        scenario = self._scenario
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
            "packet_size": int(self.packet_size_input.currentText()),
            "ttl": int(self.ttl_input.currentText()),
        }

    def _run_simulation(self) -> None:
        if self._thread is not None:
            return
        try:
            options = self._packet_options()
            attack = self._selected_attack()
            scenario = self._scenario
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
        self.simulator.reset_nodes()
        self._run_energy_start = sum(
            node.energy for node in self.simulator.network.nodes.values()
        )
        self._delivery_popup_shown = False
        self._run_started_at = perf_counter()
        self._active_packet = True
        self._pending_hop_event = None
        self._packet_progress = 0.0
        self._current_gate = None
        self._displayed_energy = None
        self._progress_scenario = None
        self._run_alive_start = {
            node.id: node.alive for node in self.simulator.network.nodes.values()
        }
        self._reported_dead_nodes = {
            node_id for node_id, is_alive in self._run_alive_start.items() if not is_alive
        }
        self.event_table.setRowCount(0)
        self.network_view.reset_animation(clear_traversed=True)
        self.network_view.node_energy = {
            node.id: node.energy for node in self.simulator.network.nodes.values()
        }
        self.network_view.node_alive = {
            node.id: node.alive for node in self.simulator.network.nodes.values()
        }
        self.network_view.update()
        self.packet_label.setText("PACKET // WAITING FOR TRANSMISSION")
        self.route_label.setText("Awaiting first hop")
        self._set_metric_packet_status("—")
        self.metric_hops.setText("—")
        self.metric_energy.setText("—")
        self.metric_alive.setText("—")
        self.metric_ttl.setText("—")
        self._set_attacker_status(
            f"ACTIVE · {self.attacker_input.currentText()}"
            if self._scenario != "Normal"
            else "OFF",
            "active" if self._scenario != "Normal" else "",
        )
        self._refresh_hud(ttl=int(self.ttl_input.currentText()))
        self._append_event(
            str(options["source"]),
            "SIMULATION START",
            f"{self._scenario} · "
            f"{options['source']} → {options['destination']}",
            "RUNNING",
        )
        self._set_status(description, "running")
        self._set_running(True)

        thread = QThread(self)
        self._run_generation += 1
        generation = self._run_generation
        worker = SimulationWorker(
            self.simulator,
            operation,
            options,
            generation,
            attack,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._show_progress)
        worker.completed.connect(self._show_completion)
        worker.failed.connect(self._show_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(
            lambda generation=generation: self.worker_thread_finished.emit(
                generation
            )
        )
        self._thread = thread
        self._worker = worker
        thread.start()

    def _update_energy_display(
        self,
        event: dict[str, object],
        *,
        remaining_ttl: int | None = None,
    ) -> None:
        energy = event.get("node_energy")
        alive = event.get("node_alive")
        if isinstance(energy, dict):
            self._refresh_hud(energy=energy, ttl=remaining_ttl)
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
            if isinstance(alive, dict):
                self.metric_alive.setText(
                    str(sum(value is True for value in alive.values()))
                )
            elif event.get("scenario") is None:
                self.metric_alive.setText(
                    str(sum(node.alive for node in self.simulator.network.nodes.values()))
                )
        if isinstance(alive, dict):
            for node_id, is_alive in alive.items():
                if is_alive is False and node_id not in self._reported_dead_nodes:
                    self._reported_dead_nodes.add(str(node_id))
                    node_energy = energy.get(node_id) if isinstance(energy, dict) else 0
                    self._append_event(
                        str(node_id),
                        "NODE DEATH",
                        f"Energy depleted · {self._format_energy(node_energy)} J",
                        "DEAD",
                        alarm=True,
                    )
            self.network_view.node_energy = {
                str(node_id): int(value)
                for node_id, value in energy.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
        if isinstance(alive, dict):
            self.network_view.node_alive = {
                str(node_id): is_alive
                for node_id, is_alive in alive.items()
                if isinstance(is_alive, bool)
            }
        self.network_view.update()

    def _show_progress(
        self,
        generation: int,
        event: object,
        gate: object,
    ) -> None:
        if generation != self._run_generation:
            if isinstance(gate, Event):
                gate.set()
            return
        if not isinstance(event, dict) or not isinstance(gate, Event):
            return
        self._current_gate = gate
        if event.get("phase") == "reception":
            remaining_ttl = max(
                0,
                int(self.ttl_input.currentText()) - int(event.get("hops", 0)),
            )
            self._update_energy_display(event, remaining_ttl=remaining_ttl)
            self.metric_ttl.setText(str(remaining_ttl))
            gate.set()
            return

        self._packet_progress = 0.0
        remaining_ttl = max(
            0,
            int(self.ttl_input.currentText()) - int(event.get("hops", 0)),
        )
        self.network_view.show_progress(
            {
                **event,
                "ttl_remaining": remaining_ttl,
                "ttl_max": int(self.ttl_input.currentText()),
            }
        )
        self._pending_hop_event = event
        sender = str(event["sender"])
        receiver = str(event["receiver"])
        route = event.get("route", [])
        if isinstance(route, list):
            self.route_label.setText(" → ".join(map(str, route)))
        scenario = event.get("scenario")
        scenario_prefix = f"{str(scenario).title()} | " if scenario else ""
        self.packet_label.setText(
            f"{scenario_prefix}PACKET // {event['status']} | "
            f"HOP {event['hops']} | {sender} → {receiver}"
        )
        route_kind = str(event.get("route_kind", "normal")).upper()
        self._set_status(f"{scenario_prefix}{route_kind} ROUTE", "running")
        status = str(event.get("status", "—"))
        self._set_metric_packet_status(status.title())
        self.metric_hops.setText(str(event.get("hops", "—")))
        scenario_key = str(scenario) if scenario is not None else None
        if (
            scenario_key is not None
            and self._progress_scenario is not None
            and scenario_key != self._progress_scenario
        ):
            self.network_view.clear_traversed_edges()
            self._reported_dead_nodes = {
                node_id
                for node_id, was_alive in self._run_alive_start.items()
                if not was_alive
            }
        self._progress_scenario = scenario_key
        self._update_energy_display(event, remaining_ttl=remaining_ttl)
        hops = event.get("hops")
        if isinstance(hops, int):
            self.metric_ttl.setText(
                str(max(0, int(self.ttl_input.currentText()) - hops))
            )
        attacker_id = self.attacker_input.currentText()
        if route_kind == "ATTACKED":
            self._set_attacker_status(f"ACTIVE · {attacker_id}", "active")
        event_name = "ATTACK ROUTE HOP" if route_kind == "ATTACKED" else "PACKET HOP"
        self._append_event(
            f"{sender} → {receiver}",
            event_name,
            f"Hop {event.get('hops', '—')} · TTL {self.metric_ttl.text()}",
            status,
            alarm=(receiver == attacker_id and route_kind == "ATTACKED"),
        )
        if not self._paused:
            self._animation_timer.start()

    def _advance_animation(self) -> None:
        self._packet_progress = min(1.0, self._packet_progress + 0.016 / 0.65)
        self.network_view.set_packet_progress(self._packet_progress)
        if self._packet_progress >= 1.0:
            self._animation_timer.stop()
            event = self._pending_hop_event
            self._pending_hop_event = None
            if (
                event is not None
                and str(event.get("receiver")) == self.attacker_input.currentText()
                and str(event.get("route_kind", "")).casefold() == "attacked"
            ):
                attacker_id = self.attacker_input.currentText()
                status = str(event.get("status", "IN_TRANSIT"))
                self._append_event(
                    attacker_id,
                    "ATTACKER ENCOUNTER",
                    f"Attacker reached on hop {event.get('hops', '—')} · "
                    f"packet {status.lower()}",
                    "ATTACKER",
                    alarm=True,
                )
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
        self._animation_timer.stop()
        self._run_generation += 1
        thread = self._thread
        if self._worker is not None:
            self._worker.stop_event.set()
        if self._current_gate is not None:
            self._current_gate.set()
        if thread is not None:
            thread.quit()
            thread.wait()
            thread.deleteLater()
        self._thread = None
        self._worker = None
        self._current_gate = None
        self._pending_hop_event = None
        self._packet_progress = 0.0
        self._paused = False
        self._active_packet = False
        self._delivery_popup_shown = False

        self.simulator.reset()
        self._displayed_energy = None
        self._reported_dead_nodes.clear()
        self._progress_scenario = None
        self.simulator.attack = self._original_attack
        self._scenario_labels.clear()
        self._result_start_index = 0
        self.source_input.setCurrentText(self._default_source_id)
        self.destination_input.setCurrentText(self._default_destination_id)
        self.attacker_input.setCurrentText(self._default_attacker_id)
        self.packet_size_input.setCurrentText("4000")
        self.ttl_input.setCurrentText("50")
        self._select_scenario("Normal")

        self.network_view.reset_animation()
        self.event_table.setRowCount(0)
        self.results_table.setRowCount(0)
        self.packet_label.setText("PACKET // IDLE")
        self.route_label.setText("Awaiting transmission")
        self._set_metric_packet_status("—")
        self.metric_hops.setText("—")
        self.metric_ttl.setText("—")
        self.metric_energy.setText("0 J")
        self.metric_alive.setText(
            str(sum(node.alive for node in self.simulator.network.nodes.values()))
        )
        self._refresh_hud(ttl=int(self.ttl_input.currentText()))
        self._set_status("Ready")
        self._set_running(False)

    def _show_completion(
        self,
        generation: int,
        operation: str,
        result: object,
    ) -> None:
        if generation != self._run_generation:
            return
        self._animation_timer.stop()
        self.network_view.clear_traversed_edges()
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
                self.route_label.setText(" → ".join(route))
            self._set_metric_packet_status(status_name.title())
            self.metric_hops.setText(str(hops))
            self.metric_ttl.setText(str(getattr(result, "ttl", "—")))
            self.packet_label.setText(
                f"PACKET // {status_name.upper()} | {hops} HOPS | "
                f"TTL {getattr(result, 'ttl', '—')}"
            )
            self.network_view.set_outcome(
                status_name,
                getattr(result, "ttl", "—"),
            )
            if status_name.upper() == "FAILED":
                failure_reason = getattr(result, "failure_reason", None)
                details = (
                    str(failure_reason)
                    if failure_reason
                    else "No valid live route to destination"
                )
            else:
                details = (
                    f"{hops} hops · TTL {getattr(result, 'ttl', '—')} remaining"
                )
            self._append_event(
                f"{getattr(result, 'source', '—')} → "
                f"{getattr(result, 'destination', '—')}",
                (
                    "SIMULATION FAILED"
                    if status_name.upper() == "FAILED"
                    else "SIMULATION COMPLETE"
                ),
                details,
                status_name,
                alarm=status_name.upper() in {"EXPIRED", "DROPPED", "FAILED"},
            )
            self._displayed_energy = None
            self.network_view.node_energy = {
                node.id: node.energy
                for node in self.simulator.network.nodes.values()
            }
            self.network_view.node_alive = {
                node.id: node.alive
                for node in self.simulator.network.nodes.values()
            }
            self.network_view.update()
            self._refresh_hud(ttl=getattr(result, "ttl", "—"))
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
            if isinstance(result, list):
                for scenario_result in result:
                    if (
                        not isinstance(scenario_result, Mapping)
                        or str(scenario_result.get("packet_status", "")).upper()
                        != "FAILED"
                    ):
                        continue
                    scenario = str(scenario_result.get("scenario", "Scenario"))
                    reason = scenario_result.get(
                        "failure_reason",
                        "No valid live route to destination",
                    )
                    self._append_event(
                        f"{scenario} scenario",
                        "SIMULATION FAILED",
                        str(reason),
                        "FAILED",
                        alarm=True,
                    )
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
            self._append_event(
                self.attacker_input.currentText(),
                "EXPERIMENT COMPLETE",
                f"{count} scenarios · latest status {latest_status or '—'}",
                latest_status or "COMPLETE",
                alarm=latest_status.upper() in {"EXPIRED", "DROPPED", "FAILED"},
            )
            results = self.simulator.get_results()
            if results:
                self._set_metrics_from_result(results[-1])
            self.metric_ttl.setText("—")
            self.network_view.set_outcome(
                latest_status or "COMPLETE",
                self.metric_ttl.text(),
            )
            self._refresh_hud(ttl="—")
        self._active_packet = False
        self._refresh_hud(ttl=self.hud_ttl.text())
        self._refresh_results()
        if show_delivery_popup and not self._delivery_popup_shown:
            self._delivery_popup_shown = True
            result_row = self.simulator.get_results()[self._result_start_index]
            scenario = self._scenario_labels.get(
                self._result_start_index,
                self._scenario,
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

    def _show_error(self, generation: int, message: str) -> None:
        if generation != self._run_generation:
            return
        self._animation_timer.stop()
        self.network_view.clear_traversed_edges()
        self._active_packet = False
        self._append_event("—", "SIMULATION ERROR", message, "FAILED", alarm=True)
        self._refresh_hud()
        self._set_status(f"Simulation failed: {message}", "error")
        self._show_message("Simulation error", message)

    def _show_message(self, title: str, message: str) -> None:
        StatusMessageDialog(title, message, self).exec_()

    def _worker_finished(self, generation: int) -> None:
        if generation != self._run_generation:
            return
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
        self.network_view.stop_feedback()
        if self._worker is not None:
            self._worker.stop_event.set()
        if self._current_gate is not None:
            self._current_gate.set()
        if self._thread is not None:
            self._thread.wait()
        event.accept()

    def _set_running(self, running: bool) -> None:
        self.run_button.setEnabled(not running)
        self.stretch_button.setEnabled(not running)
        self.carousel_button.setEnabled(not running)
        self.experiment_button.setEnabled(not running)
        self.export_button.setEnabled(not running)
        self.start_button.setEnabled(True)
        self.start_button.setText("Resume" if running else "Start")
        self.pause_button.setEnabled(running)
        self.reset_button.setEnabled(True)

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
        return f"{value:.0f}"

    @staticmethod
    def _scenario_name(result: Mapping[str, ResultValue]) -> str:
        scenario = result.get("scenario")
        if isinstance(scenario, str):
            return scenario.title()
        return "Attack" if result.get("attack_used") is True else "Normal"

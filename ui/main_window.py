from __future__ import annotations

from collections.abc import Mapping

from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from simulator import Simulator


ResultValue = str | int | float | bool


class SimulatorMainWindow(QMainWindow):
    """Simple dashboard for running packets and comparing attack scenarios."""

    def __init__(self, simulator: Simulator) -> None:
        super().__init__()
        self.simulator = simulator
        self._original_attack = simulator.attack
        self._scenario_labels: dict[int, str] = {}

        self.setWindowTitle("Vampires Attack Simulator")
        self.resize(760, 480)
        self.setMinimumWidth(700)

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        root_layout = QVBoxLayout(central_widget)

        form = QFormLayout()
        self.scenario_input = QComboBox()
        self.scenario_input.addItems(["Normal", "Stretch", "Carousel"])
        self.source_input = QLineEdit(self._default_source())
        self.destination_input = QLineEdit(self._default_destination())
        self.attacker_input = QLineEdit(self._default_attacker())
        self.packet_size_input = QSpinBox()
        self.packet_size_input.setRange(0, 2_147_483_647)
        self.packet_size_input.setValue(4000)
        self.ttl_input = QSpinBox()
        self.ttl_input.setRange(1, 2_147_483_647)
        self.ttl_input.setValue(50)

        form.addRow("Scenario", self.scenario_input)
        form.addRow("Source", self.source_input)
        form.addRow("Destination", self.destination_input)
        form.addRow("Attacker node", self.attacker_input)
        form.addRow("Packet size (bits)", self.packet_size_input)
        form.addRow("TTL", self.ttl_input)
        root_layout.addLayout(form)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run Simulation")
        self.run_button.clicked.connect(self._run_simulation)
        self.experiment_button = QPushButton("Run Experiment")
        self.experiment_button.clicked.connect(self._run_experiment)
        self.export_button = QPushButton("Export CSV")
        self.export_button.clicked.connect(self._export_csv)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.experiment_button)
        buttons.addWidget(self.export_button)
        root_layout.addLayout(buttons)

        self.status_label = QLabel("Ready")
        root_layout.addWidget(self.status_label)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Scenario", "Status", "Hops", "Energy consumed (J)", "Alive nodes"]
        )
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for column, width in enumerate((100, 110, 65, 180, 105)):
            self.results_table.setColumnWidth(column, width)
        header.setStretchLastSection(True)
        self.results_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root_layout.addWidget(self.results_table)
        self._refresh_results()

    def _default_source(self) -> str:
        node_ids = list(self.simulator.network.nodes)
        return node_ids[0] if node_ids else ""

    def _default_destination(self) -> str:
        sink = self.simulator.network.sink
        return sink.id if sink is not None else ""

    def _default_attacker(self) -> str:
        if self.simulator.attack is not None:
            return self.simulator.attack.attacker_node_id
        return ""

    def _selected_attack(self) -> StretchAttack | CarouselAttack | None:
        attacker_id = self.attacker_input.text().strip()
        scenario = self.scenario_input.currentText()
        if scenario == "Normal":
            return None
        if not attacker_id:
            raise ValueError("Enter an attacker node ID for attack scenarios.")
        if attacker_id not in self.simulator.network.nodes:
            raise ValueError(f"Attacker node {attacker_id!r} is not in the network.")
        if scenario == "Stretch":
            return StretchAttack(attacker_id)
        return CarouselAttack(attacker_id)

    def _packet_options(self) -> dict[str, str | int]:
        source = self.source_input.text().strip()
        destination = self.destination_input.text().strip()
        if not source or not destination:
            raise ValueError("Source and destination must both be provided.")
        return {
            "source": source,
            "destination": destination,
            "packet_size": self.packet_size_input.value(),
            "ttl": self.ttl_input.value(),
        }

    def _run_simulation(self) -> None:
        try:
            options = self._packet_options()
            attack = self._selected_attack()
            scenario = self.scenario_input.currentText()
            result_index = len(self.simulator.get_results())
            self.simulator.attack = attack
            result = self.simulator.run_packet(**options)
            self._scenario_labels[result_index] = scenario
            self.status_label.setText(
                f"{scenario} simulation complete: "
                f"{result.status.name}, {result.hops} hops"
            )
            self._refresh_results()
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, "Simulation error", str(error))
        finally:
            self.simulator.attack = self._original_attack

    def _run_experiment(self) -> None:
        try:
            options = self._packet_options()
            attacker_id = self.attacker_input.text().strip()
            if not attacker_id:
                raise ValueError("Enter an attacker node ID for the experiment.")
            if attacker_id not in self.simulator.network.nodes:
                raise ValueError(f"Attacker node {attacker_id!r} is not in the network.")

            results = self.simulator.run_experiment(
                source=str(options["source"]),
                destination=str(options["destination"]),
                packet_size=int(options["packet_size"]),
                ttl=int(options["ttl"]),
                stretch_attack=StretchAttack(attacker_id),
                carousel_attack=CarouselAttack(attacker_id),
            )
            self.status_label.setText(
                f"Experiment complete: {len(results)} scenarios"
            )
            self._refresh_results()
        except (KeyError, TypeError, ValueError) as error:
            QMessageBox.warning(self, "Experiment error", str(error))

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
            QMessageBox.critical(self, "Export error", str(error))

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
                self.results_table.setItem(row, column, QTableWidgetItem(value))

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

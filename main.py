import sys

from PyQt5.QtWidgets import QApplication

from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from energy.energy_model import EnergyModel
from routing.router import Router
from simulator import Simulator
from ui.main_window import SimulatorMainWindow


def main() -> int:
    """Build the sample WSN and launch its simulation dashboard."""
    network = Network(communication_range=35.0)
    nodes = (
        Node("N1", 0.0, 0.0, 100.0),
        Node("N2", 25.0, 0.0, 100.0),
        Node("N3", 50.0, 0.0, 100.0),
        Node("N4", 75.0, 0.0, 100.0),
        Node("N5", 48.0, 24.0, 100.0),
        Node("N6", 72.0, 22.0, 100.0),
        Node("SINK", 100.0, 0.0, 500.0),
    )
    for node in nodes:
        network.add_node(node)

    network.set_sink("SINK")
    network.update_neighbors()

    energy_model = EnergyModel()
    router = Router(network, energy_model)
    simulator = Simulator(
        network=network,
        router=router,
        energy_model=energy_model,
        attack=StretchAttack("N2"),
    )

    app = QApplication(sys.argv)
    window = SimulatorMainWindow(simulator)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from core.network import Network
from core.node import Node
from energy.energy_model import EnergyModel
from routing.router import Router
from simulator import Simulator


def test_reset_restores_nodes_topology_and_clears_results() -> None:
    network = Network(communication_range=35.0)
    network.add_node(Node("N1", 0.0, 0.0, 10.0))
    network.add_node(Node("N2", 30.0, 0.0, 10.0))
    network.add_node(Node("SINK", 60.0, 0.0, 100.0))
    network.set_sink("SINK")
    network.update_neighbors()
    energy_model = EnergyModel()
    simulator = Simulator(network, Router(network, energy_model), energy_model)

    simulator.router.get_next_hop("N1", "SINK")
    simulator.run_packet("N1", "SINK", packet_size=1000, ttl=10)
    assert simulator.get_results()
    assert len(simulator.router.routing_table) > 0
    assert network.nodes["N1"].sent == 1
    assert network.nodes["N1"].energy < network.nodes["N1"].initial_energy

    simulator.reset()

    assert simulator.get_results() == []
    assert len(simulator.router.routing_table) == 0
    for node in network.nodes.values():
        assert node.energy == node.initial_energy
        assert node.sent == 0
        assert node.received == 0
        assert node.forwarded == 0
    assert network.nodes["N1"].neighbors == {"N2"}
    assert network.nodes["N2"].neighbors == {"N1", "SINK"}
    assert network.nodes["SINK"].neighbors == {"N2"}

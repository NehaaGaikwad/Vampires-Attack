from collections.abc import Iterable
import csv
from pathlib import Path

from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack
from core.network import Network
from core.node import Node
from core.packet import Packet
from energy.energy_model import EnergyModel, NodeDeadError
from routing.router import Router


Result = dict[str, str | int | float | bool]


class Simulator:
    """Coordinate packet creation and routing through the project components."""

    def __init__(
        self,
        network: Network,
        router: Router,
        energy_model: EnergyModel,
        attack: StretchAttack | CarouselAttack | None = None,
    ) -> None:
        self.network = network
        self.router = router
        self.energy_model = energy_model
        self.attack = attack
        self._results: list[Result] = []

    def run_packet(
        self,
        source: str,
        destination: str,
        packet_size: int = 1,
        ttl: int | None = None,
    ) -> Packet:
        """Create and route one packet, returning its completed state."""
        packet_kwargs: dict[str, int] = {"packet_size": packet_size}
        if ttl is not None:
            packet_kwargs["ttl"] = ttl

        packet = Packet(source, destination, **packet_kwargs)
        if self.attack is None:
            energy_before = self._total_remaining_energy()
            result = self.router.route_packet(packet)
            self._record_result(result, energy_before, attack_used=False)
            return result

        energy_before = self._total_remaining_energy()
        route = self.router.find_route(source, destination)
        if route is None:
            packet.mark_dropped()
            self._record_result(packet, energy_before, attack_used=False)
            return packet

        attacked_route = self.attack.apply(
            route,
            network=self.network,
            ttl=packet.ttl,
        )
        result = self._execute_route(packet, attacked_route)
        self._record_result(result, energy_before, attack_used=True)
        return result

    def run_packets(self, packets: Iterable[Packet]) -> list[Packet]:
        """Route existing packets in order and return their resulting states."""
        results: list[Packet] = []
        for packet in packets:
            energy_before = self._total_remaining_energy()
            result = self.router.route_packet(packet)
            self._record_result(result, energy_before, attack_used=False)
            results.append(result)
        return results

    def run_experiment(
        self,
        source: str,
        destination: str,
        stretch_attack: StretchAttack,
        carousel_attack: CarouselAttack,
        packet_size: int = 1,
        ttl: int | None = None,
    ) -> list[Result]:
        """Compare normal routing, Stretch, and Carousel with isolated network copies."""
        scenarios: list[tuple[str, StretchAttack | CarouselAttack | None]] = [
            ("normal", None),
            ("stretch", stretch_attack),
            ("carousel", carousel_attack),
        ]
        experiment_results: list[Result] = []

        for scenario, attack in scenarios:
            network = self._copy_network()
            energy_model = EnergyModel(
                e_elec=self.energy_model.e_elec,
                e_amp=self.energy_model.e_amp,
            )
            simulator = Simulator(
                network=network,
                router=Router(network, energy_model),
                energy_model=energy_model,
                attack=attack,
            )
            simulator.run_packet(
                source=source,
                destination=destination,
                packet_size=packet_size,
                ttl=ttl,
            )
            result = simulator.get_results()[0]
            result["scenario"] = scenario
            self._results.append(result)
            experiment_results.append(result.copy())

        return experiment_results

    def export_results_csv(self, path: str | Path) -> None:
        """Write all recorded packet metrics to a CSV file."""
        fieldnames = [
            "scenario",
            "packet_status",
            "hops",
            "source",
            "destination",
            "total_energy_consumed",
            "alive_nodes",
            "attack_used",
        ]
        with Path(path).open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self._results)

    def get_results(self) -> list[Result]:
        """Return a copy of the metrics recorded for completed packet runs."""
        return [result.copy() for result in self._results]

    def _copy_network(self) -> Network:
        """Copy current network topology and node state for one experiment scenario."""
        network = Network(self.network.communication_range)
        for node in self.network.nodes.values():
            copied_node = Node(
                node_id=node.id,
                x=node.x,
                y=node.y,
                initial_energy=node.initial_energy,
            )
            copied_node.consume_energy(node.initial_energy - node.energy)
            for neighbor_id in node.neighbors:
                copied_node.add_neighbor(neighbor_id)
            network.add_node(copied_node)

        if self.network.sink is not None:
            network.set_sink(self.network.sink.id)
        return network

    def _total_remaining_energy(self) -> float:
        return sum(node.energy for node in self.network.nodes.values())

    def _record_result(
        self,
        packet: Packet,
        energy_before: float,
        attack_used: bool,
    ) -> None:
        self._results.append(
            {
                "packet_status": packet.status.name,
                "hops": packet.hops,
                "source": packet.source,
                "destination": packet.destination,
                "total_energy_consumed": (
                    energy_before - self._total_remaining_energy()
                ),
                "alive_nodes": sum(
                    node.alive for node in self.network.nodes.values()
                ),
                "attack_used": attack_used,
            }
        )

    def _execute_route(self, packet: Packet, route: list[str]) -> Packet:
        """Forward a packet along a precomputed route."""
        if len(route) == 1 and route[0] == packet.destination:
            packet.mark_delivered()
            return packet

        for sender_id, receiver_id in zip(route, route[1:]):
            if not packet.in_transit or packet.current_node != sender_id:
                packet.mark_dropped()
                return packet

            if packet.ttl <= 0:
                packet.mark_expired()
                return packet
            if receiver_id in packet.visited:
                packet.mark_dropped()
                return packet

            sender_node = self.network.get_node(sender_id)
            receiver_node = self.network.get_node(receiver_id)
            if (
                sender_node is None
                or not sender_node.alive
                or receiver_node is None
                or not receiver_node.alive
            ):
                packet.mark_dropped()
                return packet

            alive_neighbor_ids = {
                neighbor.id for neighbor in self.network.get_neighbors(sender_id)
            }
            if receiver_id not in alive_neighbor_ids:
                packet.mark_dropped()
                return packet

            distance = self.network.distance(sender_id, receiver_id)
            try:
                self.energy_model.transmit(
                    sender=sender_node,
                    receiver=receiver_node,
                    packet_size=packet.packet_size,
                    distance=distance,
                )
            except NodeDeadError:
                packet.mark_dropped()
                return packet

            packet.advance(receiver_id)
            if sender_id != packet.source:
                sender_node.forwarded += 1

            if not packet.in_transit:
                return packet

        if packet.in_transit:
            packet.mark_dropped()
        return packet

from collections.abc import Sequence

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from core.network import Network


def plot_network(
    network: Network,
    attacker_node_id: str | None = None,
    packet_route: Sequence[str] | None = None,
    ax: Axes | None = None,
) -> tuple[Figure, Axes]:
    """Plot network nodes and links, optionally highlighting an attacker and route."""
    if attacker_node_id is not None and attacker_node_id not in network.nodes:
        raise ValueError(f"Attacker node {attacker_node_id!r} is not in the network.")

    route = list(packet_route) if packet_route is not None else []
    missing_route_nodes = [node_id for node_id in route if node_id not in network.nodes]
    if missing_route_nodes:
        raise ValueError(
            f"Packet route contains unknown node IDs: {missing_route_nodes!r}"
        )

    if ax is None:
        figure, ax = plt.subplots()
    else:
        figure = ax.figure

    for node in network.nodes.values():
        for neighbor_id in node.neighbors:
            neighbor = network.nodes.get(neighbor_id)
            if neighbor is not None and node.id < neighbor_id:
                ax.plot(
                    [node.x, neighbor.x],
                    [node.y, neighbor.y],
                    color="0.75",
                    linewidth=1,
                    zorder=1,
                )

    if route:
        route_nodes = [network.nodes[node_id] for node_id in route]
        ax.plot(
            [node.x for node in route_nodes],
            [node.y for node in route_nodes],
            color="tab:orange",
            marker="o",
            linewidth=2.5,
            label="Packet route",
            zorder=2,
        )

    labels: set[str] = set()
    for node in network.nodes.values():
        if node.id == attacker_node_id and node is network.sink:
            color, label = "purple", "Sink / attacker"
        elif node is network.sink:
            color, label = "tab:red", "Sink"
        elif node.id == attacker_node_id:
            color, label = "tab:orange", "Attacker"
        elif node.alive:
            color, label = "tab:blue", "Node"
        else:
            color, label = "0.5", "Dead node"

        ax.scatter(
            node.x,
            node.y,
            color=color,
            marker="o" if node.alive else "x",
            s=100,
            label=label if label not in labels else None,
            zorder=3,
        )
        labels.add(label)
        ax.annotate(node.id, (node.x, node.y), xytext=(5, 5), textcoords="offset points")

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Network topology")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle=":", alpha=0.4)
    if labels or route:
        ax.legend()
    return figure, ax

# Vampires Attack

A Wireless Sensor Network (WSN) simulator for studying Vampire Attacks and their impact on network energy consumption.

Sensor nodes are battery-powered and communicate wirelessly with nearby nodes, eventually forwarding data toward a central Sink / Base Station. Because node batteries cannot be recharged, energy exhaustion is a critical threat. Vampire Attacks exploit routing protocols to deliberately drain victim node batteries, causing nodes to die and fragmenting the network.

---

## Current Status

| Part | Owner | Status |
|------|-------|--------|
| **Part 1 — Network & Energy** | Member 1 | ✅ Complete |
| Part 2 — Packet & Routing | Member 2 | 🔜 Next |
| Part 3 — Vampire Attack & Security | Member 3 | 🔜 Planned |
| Part 4 — Simulation, GUI & Analytics | Member 4 | 🔜 Planned |

---

## Repository Structure

```
Vampires-Attack/
│
├── core/
│   ├── __init__.py
│   ├── node.py              ✅ Implemented — sensor node
│   └── network.py           ✅ Implemented — topology manager
│
├── energy/
│   ├── __init__.py
│   └── energy_model.py      ✅ Implemented — radio energy model
│
├── tests/
│   ├── __init__.py
│   └── test_network_energy.py  ✅ 96 tests, all passing
│
├── requirements.txt
└── README.md
```

**Not yet created** (planned by future members):

```
core/packet.py               Part 2 — Packet definition
routing/router.py            Part 2 — Routing logic
routing/dijkstra.py          Part 2 — Path computation
attacks/stretch.py           Part 3 — Stretch Attack
attacks/carousel.py          Part 3 — Carousel Attack
security/detector.py         Part 3 — Anomaly detection
security/mitigation.py       Part 3 — Mitigation logic
simulation/simulator.py      Part 4 — Simulation engine
gui/                         Part 4 — Visualisation
metrics/                     Part 4 — Analytics & CSV export
```

---

## Architecture

```
 Node  ←  owns battery energy and position
   │
 Network  ←  manages nodes, topology, distance, neighbors, sink
   │
 EnergyModel  ←  calculates and applies energy consumption
   │
 [Part 2]  Router / Packet  ←  uses Network + EnergyModel
   │
 [Part 3]  Attack / Security  ←  manipulates routing
   │
 [Part 4]  Simulation / GUI / Metrics  ←  orchestrates everything
```

---

# Part 1: Network & Energy

Part 1 provides the foundation that every other module builds on.
It has no dependencies on routing, packets, attacks, detection, or GUI.

---

## `core/node.py` — Node

A `Node` represents one battery-powered sensor node in the network.

### Constructor

```python
from core.node import Node

node = Node(node_id, x, y, initial_energy)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | `str` | Unique identifier, e.g. `"N1"` or `"SINK"` |
| `x` | `float` | X-coordinate |
| `y` | `float` | Y-coordinate |
| `initial_energy` | `float` | Starting battery in Joules — must be `> 0` |

Raises `ValueError` if `initial_energy <= 0`.

### Properties

| Property | Type | Notes |
|----------|------|-------|
| `node.id` | `str` | Unique identifier — read-only |
| `node.x` | `float` | X-coordinate — read-only |
| `node.y` | `float` | Y-coordinate — read-only |
| `node.position` | `tuple[float, float]` | `(x, y)` — read-only |
| `node.initial_energy` | `float` | Original battery — never changes |
| `node.energy` | `float` | Current remaining energy — always `>= 0` |
| `node.alive` | `bool` | `True` if `energy > 0`; `False` when dead — derived, never manually set |
| `node.neighbors` | `set[str]` | Set of neighboring node IDs — managed by `Network` |
| `node.sent` | `int` | Packets sent — incremented by `EnergyModel.transmit()` |
| `node.received` | `int` | Packets received — incremented by `EnergyModel.transmit()` |
| `node.forwarded` | `int` | Packets forwarded — **set by the routing layer (Part 2)** |

`sent`, `received`, and `forwarded` have both getters and setters so external layers can increment them directly (`node.forwarded += 1`).

### Methods

#### `consume_energy(amount: float) -> None`

Deducts `amount` Joules from the node's battery.

- `amount <= 0` → silently ignored, no state change
- `amount > 0` → `energy = max(0.0, energy - amount)`
- Energy can never go below `0.0`
- When energy reaches `0.0`, `alive` becomes `False` automatically

#### `add_neighbor(node_id: str) -> None`

Adds a node ID to the neighbor set. Duplicate additions are ignored (set semantics).

#### `remove_neighbor(node_id: str) -> None`

Removes a node ID from the neighbor set. If the ID is not present, the call is silently ignored.

#### `reset() -> None`

Restores the node to its creation state:
- `energy` → `initial_energy`
- `sent`, `received`, `forwarded` → `0`
- `neighbors` → empty set

After calling `reset()` on any node, call `network.update_neighbors()` to restore the topology.

### Example

```python
from core.node import Node

n = Node("N1", 0.0, 0.0, 100.0)

print(n.id)             # "N1"
print(n.position)       # (0.0, 0.0)
print(n.energy)         # 100.0
print(n.alive)          # True

n.consume_energy(60)
print(n.energy)         # 40.0
print(n.alive)          # True

n.consume_energy(9999)  # clamps to 0
print(n.energy)         # 0.0
print(n.alive)          # False

n.reset()
print(n.energy)         # 100.0
print(n.alive)          # True
```

---

## `core/network.py` — Network

`Network` manages all nodes, the communication topology, distances, neighbor discovery, and the Sink.

### Constructor

```python
from core.network import Network

net = Network(communication_range=50.0)
```

Raises `ValueError` if `communication_range <= 0`.

### Properties

| Property | Type | Notes |
|----------|------|-------|
| `net.communication_range` | `float` | Max direct-link distance |
| `net.nodes` | `dict[str, Node]` | All nodes keyed by ID — alive **and** dead |
| `net.sink` | `Node \| None` | Sink / Base Station, or `None` if not set |

### Methods

#### `add_node(node: Node) -> None`

Adds a node to the network, keyed by `node.id`. Replaces silently if the same ID is added twice.

#### `get_node(node_id: str) -> Node | None`

Returns the node with that ID, or **`None`** if not found. Does not raise an exception.

```python
node = net.get_node("N1")
if node is None:
    print("not found")
```

#### `set_sink(node_id: str) -> None`

Designates an existing node as the Sink / Base Station.
Raises `KeyError` if the node does not exist in the network.

```python
net.set_sink("SINK")
print(net.sink.id)   # "SINK"
```

#### `distance(node_a, node_b) -> float`

Returns the Euclidean distance between two nodes using `math.hypot`.

Both arguments accept either a `Node` object or a node ID string.

```
distance = sqrt((x1 - x2)² + (y1 - y2)²)
```

Raises `KeyError` if a string ID doesn't exist. Raises `TypeError` for any other type.

#### `update_neighbors() -> None`

Rebuilds all bidirectional neighbor relationships from scratch.

Algorithm:
1. Clear every node's neighbor set (removes stale data from previous topology).
2. For every unique pair `(A, B)`, compute Euclidean distance.
3. If `distance <= communication_range`: add `B` to `A.neighbors` and `A` to `B.neighbors`.

Call this after adding nodes or changing positions.

#### `get_neighbors(node_id: str) -> list[Node]`

Returns the **alive** direct neighbors of the given node.

Dead nodes (`node.alive == False`) are **excluded** from the returned list even though they remain in `net.nodes`. This is intentional — the routing layer must never attempt to forward packets through a dead node.

Raises `KeyError` if `node_id` does not exist.

### Dead-Node Behaviour in Network

Dead nodes are **never removed** from `net.nodes`. This allows future modules to:
- Render dead nodes greyed-out in the GUI
- Count how many nodes have died in metrics
- Trace which nodes were killed in an attack

They are only excluded from `get_neighbors()` so routing code never treats them as active links.

### Example

```python
from core.node import Node
from core.network import Network

net = Network(communication_range=50.0)

n1   = Node("N1",   0,  0, 100.0)
n2   = Node("N2",  30,  0, 100.0)
n3   = Node("N3", 100,  0, 100.0)
sink = Node("SINK", 15,  0, 500.0)

for node in (n1, n2, n3, sink):
    net.add_node(node)

net.set_sink("SINK")
net.update_neighbors()

print(net.distance("N1", "N2"))              # 30.0
print([n.id for n in net.get_neighbors("N1")])  # ["N2", "SINK"]

# Kill N2
n2.consume_energy(n2.energy)
print(n2.alive)                              # False
print("N2" in net.nodes)                    # True  (still stored)
print([n.id for n in net.get_neighbors("N1")])  # ["SINK"] (N2 excluded)
```

---

## `energy/energy_model.py` — EnergyModel

Implements the **first-order radio energy model** (Heinzelman et al., 2000).

Three public names are exported from this module:

- `EnergyModel` — the main class
- `NodeDeadError` — raised when a dead node tries to communicate
- `TransmissionResult` — dataclass returned by `transmit()`

### Radio Energy Formulas

**Transmission energy:**
```
E_tx = E_elec × packet_size  +  E_amp × packet_size × distance²
```

**Reception energy:**
```
E_rx = E_elec × packet_size
```

| Constant | Default | Value |
|----------|---------|-------|
| `E_elec` | `50e-9` | 50 nJ/bit — electronics energy per bit |
| `E_amp` | `100e-12` | 100 pJ/bit/m² — amplifier energy per bit per metre² |

Both constants are configurable via the constructor. Units: Joules, bits, metres.

### Constructor

```python
from energy.energy_model import EnergyModel

em = EnergyModel()                          # use defaults
em = EnergyModel(e_elec=50e-9, e_amp=100e-12)  # explicit
```

Raises `ValueError` if either constant is `<= 0`.

### Methods

#### `transmission_energy(packet_size, distance) -> float`

Returns the Joules required to transmit `packet_size` bits over `distance` metres.
Raises `ValueError` for negative arguments.

#### `reception_energy(packet_size) -> float`

Returns the Joules required to receive `packet_size` bits.
Raises `ValueError` for negative `packet_size`.

#### `transmit(sender, receiver, packet_size, distance) -> TransmissionResult`

Performs a complete single-hop transmission. Steps in order:

1. Raise `NodeDeadError(role="sender")` if `sender.alive` is `False`
2. Raise `NodeDeadError(role="receiver")` if `receiver.alive` is `False`
3. Calculate `E_tx = transmission_energy(packet_size, distance)`
4. Calculate `E_rx = reception_energy(packet_size)`
5. Call `sender.consume_energy(E_tx)`
6. Call `receiver.consume_energy(E_rx)`
7. Increment `sender.sent`
8. Increment `receiver.received`
9. Return `TransmissionResult`

**`sender.forwarded` is NOT incremented here.** Deciding whether a transmission counts as a forward is a routing-layer responsibility. The routing module (Part 2) must increment `node.forwarded` itself.

### `NodeDeadError`

```python
from energy.energy_model import NodeDeadError

try:
    em.transmit(dead_node, receiver, 4000, 30.0)
except NodeDeadError as e:
    print(e.node_id)   # ID of the dead node
    print(e.role)      # "sender" or "receiver"
```

### `TransmissionResult`

```python
@dataclass
class TransmissionResult:
    tx_energy: float       # Joules consumed by sender
    rx_energy: float       # Joules consumed by receiver
    sender_alive: bool     # whether sender survived this transmission
    receiver_alive: bool   # whether receiver survived this transmission
```

### Example

```python
from core.node import Node
from energy.energy_model import EnergyModel, NodeDeadError

em = EnergyModel()

sender   = Node("N1", 0, 0, 1.0)
receiver = Node("N2", 30, 0, 1.0)

result = em.transmit(sender, receiver, packet_size=4000, distance=30.0)

print(f"Tx consumed : {result.tx_energy * 1e6:.3f} µJ")
print(f"Rx consumed : {result.rx_energy * 1e6:.3f} µJ")
print(f"Sender alive: {result.sender_alive}")
print(f"sender.sent : {sender.sent}")        # 1
print(f"receiver.received: {receiver.received}")  # 1
```

---

# How Part 2 Uses Part 1

> **This section is written for Member 2 (Packet & Routing).**

Do not re-implement `Node`, `Network`, distance calculation, or energy consumption.
Import and use the Part 1 interfaces directly.

### What Part 2 owns

- `Packet` — define the packet structure (source, destination, payload, path, etc.)
- `Router` — implement the routing protocol (e.g. greedy geographic, GPSR, or DSR)
- Path computation — shortest path, minimum energy path, or as required

### What Part 2 must NOT duplicate

- `Node` — already in `core/node.py`
- `Network` — already in `core/network.py`
- Distance calculation — use `network.distance()`
- Energy consumption — use `energy_model.transmit()`
- Battery state — read `node.energy` and `node.alive`

### Routing flow

```
Packet arrives at node X
        │
Router asks: who are my alive neighbors?
        │
  network.get_neighbors("X")   →  list[Node], dead nodes excluded
        │
Router picks next hop Y (e.g. closest to destination)
        │
  network.distance(X, Y)       →  float
        │
  energy_model.transmit(X, Y, packet_size, distance)
        │
  node X: energy ↓,  sent ↑
  node Y: energy ↓,  received ↑
        │
Router sets:  node_X.forwarded += 1   ← routing layer responsibility
        │
Repeat at Y
```

### Concrete example

```python
from core.node import Node
from core.network import Network
from energy.energy_model import EnergyModel, NodeDeadError

net = Network(communication_range=50.0)
em  = EnergyModel()

# -- setup (done by Part 1 / simulation init) --
n1   = Node("N1",   0,  0, 0.5)
n2   = Node("N2",  30,  0, 0.5)
sink = Node("SINK", 60,  0, 1.0)
for node in (n1, n2, sink):
    net.add_node(node)
net.set_sink("SINK")
net.update_neighbors()

# -- Part 2 routing code --
def forward_one_hop(network, energy_model, sender_id, receiver_id, packet_size):
    sender   = network.get_node(sender_id)
    receiver = network.get_node(receiver_id)

    if sender is None or receiver is None:
        raise ValueError("Unknown node ID")

    distance = network.distance(sender, receiver)

    try:
        result = energy_model.transmit(sender, receiver, packet_size, distance)
    except NodeDeadError as e:
        print(f"Transmission failed: {e}")
        return None

    sender.forwarded += 1   # routing layer sets this
    return result

# route: N1 → N2 → SINK
forward_one_hop(net, em, "N1", "N2",   packet_size=4000)
forward_one_hop(net, em, "N2", "SINK", packet_size=4000)

print(net.get_node("N1").sent)       # 1
print(net.get_node("N1").forwarded)  # 1
print(net.get_node("N2").received)   # 1
print(net.get_node("N2").sent)       # 1
print(net.get_node("N2").forwarded)  # 1
```

### Key interfaces summary

| Need | Use |
|------|-----|
| Find a node | `network.get_node(node_id)` → `Node \| None` |
| Get alive next-hop candidates | `network.get_neighbors(node_id)` → `list[Node]` |
| Compute link distance | `network.distance(a, b)` → `float` |
| Transmit and drain energy | `energy_model.transmit(sender, receiver, size, dist)` |
| Check if node can forward | `node.alive` |
| Record a forwarded packet | `node.forwarded += 1` |
| Inspect remaining battery | `node.energy`, `node.initial_energy` |
| Handle dead node during route | `except NodeDeadError` |

---

# Testing

Tests live in `tests/test_network_energy.py` and cover Part 1 only.

```bash
# Install dependencies
pip install -r requirements.txt

# Run all Part 1 tests
python -m pytest tests/test_network_energy.py -v
```

**Result: 96 passed**

| Test class | Tests | What is covered |
|------------|-------|----------------|
| `TestNodeCreation` | 15 | id, x, y, position, energy, alive, counters, neighbors, invalid energy |
| `TestNodeEnergyConsumption` | 4 | Partial drain, alive, initial_energy unchanged |
| `TestNodeExactDepletion` | 2 | energy → 0, alive → False |
| `TestNodeExcessiveConsumption` | 4 | Clamp to 0, never negative |
| `TestNodeInvalidConsumption` | 3 | Negative and zero amount ignored |
| `TestNodeNeighborManagement` | 5 | Add, deduplicate, remove, missing remove |
| `TestNodeReset` | 4 | Energy, alive, counters, neighbors restored |
| `TestNetworkAddNode` | 3 | Single, multiple, stored by ID |
| `TestNetworkGetNode` | 2 | Returns correct node |
| `TestNetworkGetNodeInvalid` | 2 | Returns None for missing ID |
| `TestNetworkDistance` | 7 | 3-4-5 triangle, by ID, by Node, symmetric, mixed, invalid |
| `TestNetworkCommunicationRange` | 4 | Within range, outside, exact boundary, just outside |
| `TestNetworkBidirectionalNeighbors` | 3 | N1↔N2, N2↔N1, 3-node chain |
| `TestNetworkNeighborRebuilding` | 2 | Stale removed, new node picked up |
| `TestNetworkDeadNeighborExclusion` | 3 | Dead excluded from get_neighbors, still in nodes |
| `TestNetworkSink` | 4 | Valid sink, initially None, invalid raises, same object |
| `TestTransmissionEnergyCalculation` | 6 | Formula correctness, zero distance, zero packet, negatives raise |
| `TestReceptionEnergyCalculation` | 4 | Formula correctness, zero packet, negative raises |
| `TestTransmitOperation` | 8 | Energy decreases, sent++, received++, forwarded untouched, result type |
| `TestTransmissionCausesDeath` | 2 | Sender dies after transmit |
| `TestDeadSender` | 2 | NodeDeadError raised, receiver untouched |
| `TestDeadReceiver` | 2 | NodeDeadError raised, sender untouched |
| `TestEnergyNeverNegative` | 4 | Clamping in consume, transmit, receive |
| `TestIntegration` | 1 | Full end-to-end workflow |
| **Total** | **96** | **All pass ✅** |

---

## Installation

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

`requirements.txt` contains only `pytest`. The entire implementation uses the Python standard library (`math`, `dataclasses`).
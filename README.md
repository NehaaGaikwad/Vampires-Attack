# Vampires Attack

A Wireless Sensor Network (WSN) simulator for studying **Vampire Attacks**, their effect on network energy consumption, and behavior-based detection and mitigation techniques.

The system models battery-powered sensor nodes that communicate with neighboring nodes and forward packets toward a central **Sink/Base Station**.

## Project Overview

In a Wireless Sensor Network, sensor nodes have limited battery energy. Nodes communicate with one another and forward packets through the network until they reach the Sink.

A Vampire Attack manipulates packet routing so that packets travel through unnecessarily long or repeated paths. This causes additional packet forwarding and increased energy consumption, eventually exhausting node batteries and reducing the lifetime of the network.

The project currently has **Parts 1, 2, and 3 implemented**.

Part 3 provides the Vampire Attack and Security layer, including:
- Attack foundation (`BaseAttack`, `AttackType`, `AttackIntensity`, lifecycle management)
- Stretch Attack (route elongation detour routing)
- Carousel Attack (routing cycle / loop injection)
- Behavior-based attack detection (`AttackDetector`, multi-signal analysis)
- Suspicious node isolation (`MitigationManager`, blacklist tracking)
- Route recalculation (`recalculate_route` using Dijkstra)
- Recovery from isolation (`clear_isolation`, `clear_all`)

Part 4 (Simulation Engine, GUI & Analytics) remains under development.

## Current Status

| Part | Module | Status |
|---|---|---|
| Part 1 | Network & Energy | Completed |
| Part 2 | Packet & Routing | Completed |
| Part 3 | Vampire Attack & Security | Completed |
| Part 4 | Simulation, GUI & Analytics | Planned |

```text
Part 1: Network & Energy (COMPLETED)
        ↓
Part 2: Packet & Routing (COMPLETED)
        ↓
Part 3: Vampire Attack & Security (COMPLETED)
        ↓
Part 4: Simulation, GUI & Analytics (PLANNED)
```

## How to Run and Check

### 1. Development & Branch Workflow
Do not commit directly to main. Create a feature branch for new work unless the team workflow explicitly requires otherwise.

### 2. Verify Imports
```bash
python -c "from core.node import Node; from core.network import Network; from energy.energy_model import EnergyModel; from core.packet import Packet, PacketStatus; from routing.dijkstra import shortest_path; from routing.router import Router; from routing.routing_table import RoutingTable; from attacks.base import BaseAttack, AttackType, AttackIntensity; from attacks.stretch import StretchAttack; from attacks.carousel import CarouselAttack; from security.detector import AttackDetector, DetectionResult; from security.mitigation import MitigationManager, IsolatedNetworkView; print('All imports OK')"
```

### 3. Run the Test Suites

Run individual module test suites:
```bash
# Part 1: Network & Energy (96 tests)
python -m pytest tests/test_network_energy.py -v

# Part 2: Packet & Routing (153 tests)
python -m pytest tests/test_packet_routing.py -v

# Part 3: Attack Foundation (82 tests)
python -m pytest tests/test_attack_base.py -v

# Part 3: Stretch Attack (21 tests)
python -m pytest tests/test_stretch_attack.py -v

# Part 3: Carousel Attack (23 tests)
python -m pytest tests/test_carousel_attack.py -v

# Part 3: Behavior-Based Detection (40 tests)
python -m pytest tests/test_detector.py -v

# Part 3: Mitigation & Isolation (29 tests)
python -m pytest tests/test_mitigation.py -v
```

Run the complete test suite:
```bash
python -m pytest tests/ -v
```

Expected result:
```text
444 passed
```

Test suite breakdown:
- **Part 1 - Network & Energy**: 96 tests
- **Part 2 - Packet & Routing**: 153 tests
- **Attack Foundation**: 82 tests
- **Stretch Attack**: 21 tests
- **Carousel Attack**: 23 tests
- **Detection**: 40 tests
- **Mitigation**: 29 tests
- **Total**: **444 tests**

---

## Repository Structure

```text
Vampires-Attack/
│
├── core/
│   ├── node.py
│   ├── network.py
│   └── packet.py
│
├── energy/
│   └── energy_model.py
│
├── routing/
│   ├── dijkstra.py
│   ├── router.py
│   └── routing_table.py
│
├── attacks/
│   ├── __init__.py
│   ├── base.py
│   ├── stretch.py
│   └── carousel.py
│
├── security/
│   ├── __init__.py
│   ├── detector.py
│   └── mitigation.py
│
├── simulation/
│   └── simulator.py       # Part 4 - planned
│
├── gui/                   # Part 4 - planned
│
├── metrics/               # Part 4 - planned
│
├── tests/
│   ├── test_network_energy.py
│   ├── test_packet_routing.py
│   ├── test_attack_base.py
│   ├── test_stretch_attack.py
│   ├── test_carousel_attack.py
│   ├── test_detector.py
│   └── test_mitigation.py
│
├── .gitignore
└── README.md
```

---

# Part 1 Architecture

Part 1 provides the foundational WSN infrastructure modeling sensor nodes, network topology, and radio energy dissipation.

```text
                  ┌──────────────┐
                  │    Network   │
                  └──────┬───────┘
                         │
                   manages topology
                         │
          ┌──────────────┴──────────────┐
          │                             │
    ┌─────▼───────┐               ┌─────▼───────┐
    │    Nodes    │               │    Sink     │
    └─────┬───────┘               └─────────────┘
          │
          │ battery state
          ▼
    ┌──────────────┐
    │ EnergyModel  │
    └──────────────┘
```

### Responsibility Separation
| Component | Responsibility |
|---|---|
| `Node` | Identity, position, energy, neighbors, packet counters |
| `Network` | Nodes, topology, distance, neighbors, Sink designation |
| `EnergyModel` | First-order radio model, transmission/reception energy, battery consumption |

Part 1 intentionally does **not** contain packet routing, attack logic, detection, mitigation, simulation, GUI, or metrics.

## 1. Node
File: `core/node.py`

The `Node` class represents a single battery-powered sensor node.

### Creating a Node
```python
from core.node import Node

node = Node(
    node_id="N1",
    x=10,
    y=20,
    initial_energy=100.0,
)
```

The constructor accepts:
| Parameter | Description |
|---|---|
| `node_id` | Unique node identifier (string) |
| `x` | X-coordinate (numeric) |
| `y` | Y-coordinate (numeric) |
| `initial_energy` | Initial battery energy (must be > 0) |

### Node Properties
- **Identity**: `node.id` returns the node's unique identifier.
- **Position**: `node.x`, `node.y`, and `node.position` return coordinates (e.g. `(10.0, 20.0)`).
- **Energy**: `node.initial_energy` stores starting battery level; `node.energy` tracks remaining battery energy.

### Consuming Energy
```python
node.consume_energy(amount)
```
Energy cannot become negative. If consumption exceeds remaining energy, energy becomes 0.0 and `node.alive` becomes `False`.

### Alive / Dead State
```python
node.alive
```
Derived directly from remaining energy:
- `energy > 0` → alive (`True`)
- `energy == 0` → dead (`False`)

Dead nodes are strictly excluded from forwarding.

### Neighbors & Packet Counters
- `node.neighbors`: Set of neighboring node IDs.
- `node.sent`, `node.received`, `node.forwarded`: Integers tracking traffic statistics.
- `node.reset()`: Restores `energy` to `initial_energy`, clears counters to 0, and clears `neighbors`.

---

## 2. Network
File: `core/network.py`

The `Network` class manages the WSN topology:
- Storing and retrieving nodes (`add_node`, `get_node`)
- Distance calculation using Euclidean distance:
  $$\text{distance} = \sqrt{(x_1 - x_2)^2 + (y_1 - y_2)^2}$$
- Neighbor discovery based on communication range: two nodes are neighbors if $\text{distance} \le \text{communication\_range}$.
- Bidirectional neighbor relationships via `network.update_neighbors()`.
- Retrieving alive neighbors via `network.get_neighbors(node_id)`.
- Sink designation via `network.set_sink(node_id)` and retrieval via `network.sink`.

### Dead Nodes in Network
Dead nodes remain registered in `network.nodes` for telemetry, analytics, and inspection, but are automatically excluded from `network.get_neighbors(node_id)`.

---

## 3. Energy Model
File: `energy/energy_model.py`

Implements the first-order radio model:

### Transmission Energy
$$E_{tx} = E_{elec} \times \text{packet\_size} + E_{amp} \times \text{packet\_size} \times \text{distance}^2$$

### Reception Energy
$$E_{rx} = E_{elec} \times \text{packet\_size}$$

### Default Constants
- $E_{elec} = 50 \text{ nJ/bit} = 50 \times 10^{-9} \text{ J/bit}$
- $E_{amp} = 100 \text{ pJ/bit/m}^2 = 100 \times 10^{-12} \text{ J/bit/m}^2$

### Performing a Transmission
```python
result = energy_model.transmit(
    sender=sender,
    receiver=receiver,
    packet_size=4000,
    distance=distance,
)
```
The operation:
1. Verifies both sender and receiver are alive (raises `NodeDeadError` if either is dead).
2. Calculates $E_{tx}$ and $E_{rx}$.
3. Deducts energy from sender and receiver batteries.
4. Increments `sender.sent` and `receiver.received`.
5. Returns a `TransmissionResult` with consumed energy and alive flags.

---

## Complete Part 1 Example
```python
from core.node import Node
from core.network import Network
from energy.energy_model import EnergyModel

network = Network(communication_range=50)
n1 = Node("N1", 0, 0, 100)
n2 = Node("N2", 30, 40, 100)
sink = Node("SINK", 60, 40, 1000)

network.add_node(n1)
network.add_node(n2)
network.add_node(sink)
network.set_sink("SINK")
network.update_neighbors()

energy_model = EnergyModel()
sender = network.get_node("N1")
receiver = network.get_node("N2")
distance = network.distance(sender, receiver)

result = energy_model.transmit(
    sender=sender,
    receiver=receiver,
    packet_size=4000,
    distance=distance,
)

print(f"Tx Energy: {result.tx_energy} J, Rx Energy: {result.rx_energy} J")
print(f"N1 Energy: {sender.energy} J, N2 Energy: {receiver.energy} J")
```

---

# Part 2 Architecture

Part 2 implements packet representation, Dijkstra shortest-path computation, routing tables, and end-to-end hop-by-hop forwarding.

## How Part 2 Uses Part 1
Part 2 builds directly upon Part 1 without duplicating nodes, topology, or energy calculations:

```text
                  Packet
                    │
                    ▼
                  Router
                    │
                    ▼
          Network.get_neighbors()
                    │
                    ▼
             Select Next Hop
                    │
                    ▼
            Network.distance()
                    │
                    ▼
          EnergyModel.transmit()
                    │
                    ▼
               Node Energy
```

## Part 2 API Reference

### 1. Packet (`core/packet.py`)
```python
from core.packet import Packet, PacketStatus

packet = Packet(
    source="N1",
    destination="SINK",
    ttl=10,            # max hops (default: 50)
    packet_size=4000,  # bits (default: 4000)
)

packet.source          # "N1"
packet.destination     # "SINK"
packet.route           # ("N1",) (grows as packet advances)
packet.current_node    # "N1"
packet.hops            # 0
packet.ttl             # 10
packet.visited         # {"N1"}
packet.status          # PacketStatus.IN_TRANSIT
packet.advance("N2")   # Move to next hop, increments hops, decrements ttl
packet.mark_dropped()  # Explicitly drop
packet.mark_expired()  # Explicitly expire when TTL reaches 0
```

Packet lifecycle states: `IN_TRANSIT`, `DELIVERED`, `EXPIRED`, `DROPPED`.

### 2. Dijkstra (`routing/dijkstra.py`)
```python
from routing.dijkstra import shortest_path

path = shortest_path(network, "N1", "SINK")
# => ("N1", "N2", "N3", "SINK") or None
```
Uses `network.distance()` for edge weights and filters dead nodes via `network.get_neighbors()`.

### 3. RoutingTable (`routing/routing_table.py`)
```python
from routing.routing_table import RoutingTable

table = RoutingTable()
table.set_next_hop("SINK", "N2")
next_hop = table.get_next_hop("SINK")  # "N2"
has_route = table.has_route("SINK")    # True
table.remove_route("SINK")
table.clear()
```

### 4. Router (`routing/router.py`)
```python
from routing.router import Router

router = Router(network, energy_model)
route = router.find_route("N1", "SINK")
next_hop = router.get_next_hop("N1", "SINK")

packet = Packet("N1", "SINK", ttl=10)
router.route_packet(packet)
assert packet.delivered  # True
```

### Forwarding Counters
For a route `N1 → N2 → N3 → SINK`:
| Node | `sent` | `received` | `forwarded` |
|---|---|---|---|
| N1 | 1 | 0 | 0 |
| N2 | 1 | 1 | 1 |
| N3 | 1 | 1 | 1 |
| SINK | 0 | 1 | 0 |

`sent` and `received` are incremented by `EnergyModel.transmit()`. `forwarded` is incremented by `Router` on intermediate relay nodes.

---

# Part 3 Architecture: Vampire Attack & Security

Part 3 implements the complete Vampire Attack generation, behavior-based detection, and mitigation isolation layer.

## End-to-End Security Flow

```text
Normal Dijkstra Route
        ↓
Vampire Attack
        ↓
Abnormal Route Behavior
        ↓
Behavior-Based Detection
        ↓
Suspicious Node Identified
        ↓
Node Isolation
        ↓
Dijkstra Route Recalculation
        ↓
Safe Route
```

### Security Flow Explanation
1. **Normal Routing**: Under benign conditions, packets follow optimal shortest paths determined by Dijkstra's algorithm.
2. **Vampire Attack**: A malicious node intercepts or manipulates routes, injecting detours (Stretch Attack) or cycles (Carousel Attack) to exhaust network batteries.
3. **Abnormal Route Behavior**: Manipulated routes manifest observable anomalies: inflated hop counts, packet forwarding spikes, repeated node traversals, and accelerated battery depletion.
4. **Behavior-Based Detection**: `AttackDetector` analyzes telemetry metrics against anomaly thresholds and computes a composite suspicion score without needing knowledge of attack classes.
5. **Suspicious Node Identified**: Nodes exceeding the detection threshold are flagged with transparent diagnostic evidence in a `DetectionResult`.
6. **Node Isolation**: `MitigationManager` blacklists identified malicious nodes, preserving physical nodes intact for logging and analytics.
7. **Dijkstra Route Recalculation**: `recalculate_route` utilizes `IsolatedNetworkView` to re-run Dijkstra routing, routing packets safely around isolated nodes.
8. **Safe Route**: Subsequent traffic travels across verified healthy nodes with battery depletion halted.

---

## 1. Attack Foundation
File: `attacks/base.py`

`attacks/base.py` provides the core abstractions, taxonomies, parameter validation, and lifecycle management for all Vampire Attacks.

### Core Types & Enums
- **`AttackType` (Enum)**:
  - `AttackType.STRETCH`: Stretch Vampire Attack.
  - `AttackType.CAROUSEL`: Carousel Vampire Attack.
- **`AttackIntensity` (Enum)**:
  - `AttackIntensity.LOW`: Conservative attack intensity.
  - `AttackIntensity.MEDIUM`: Moderate attack intensity.
  - `AttackIntensity.HIGH`: Aggressive attack intensity.

### `BaseAttack` Class
The foundational base class for concrete attack implementations.

Parameters:
- `attacker_node_id` (str): Unique identifier of the malicious node (must be non-empty string).
- `attack_type` (`AttackType` | str): Attack classification.
- `intensity` (`AttackIntensity` | str): Attack intensity level.
- `start_time` (float): Simulation timestamp when attack becomes active (must be $\ge 0$).
- `duration` (float): Active simulation duration (must be $\ge 0$).

Properties:
- `attacker_node_id`: Node ID of the malicious sensor node.
- `attack_type`: `AttackType` enum value.
- `intensity`: `AttackIntensity` enum value.
- `start_time`: Numeric start timestamp.
- `duration`: Active duration window.
- `end_time`: Derived simulation end timestamp (`start_time + duration`).

### Attack Lifecycle & Validation
- **Configuration Validation**: Strict type checking and value validation; raises `TypeError` or `ValueError` on empty IDs, invalid enum names, or negative timestamps.
- **Active Interval Handling**:
  - `is_active(current_time)` returns `True` if and only if:
    $$\text{start\_time} \le \text{current\_time} < \text{end\_time}$$
  - Returns `False` if `current_time < start_time` or `current_time >= end_time`.
  - **Special Case**: When `duration == 0`, the attack is inactive and `is_active(current_time)` returns `False` for all timestamps.

```python
from attacks.base import BaseAttack, AttackType, AttackIntensity

attack = BaseAttack(
    attacker_node_id="N7",
    attack_type=AttackType.STRETCH,
    intensity=AttackIntensity.MEDIUM,
    start_time=10.0,
    duration=50.0,
)

assert attack.end_time == 60.0
assert not attack.is_active(5.0)   # Before start
assert attack.is_active(25.0)      # Active interval
assert not attack.is_active(60.0)  # After end
```

---

## 2. Stretch Attack
File: `attacks/stretch.py`

Implements the **Stretch Vampire Attack** (Vasserman & Hopper, 2013).

### Attack Mechanism
- Artificially manipulates a valid packet route so that packets take an unnecessarily elongated path.
- Routes packets through extra innocent relay nodes, draining their batteries via redundant transmissions and receptions.
- Uses real nodes and valid wireless links from the network topology (`Network`).
- Strictly preserves source node as the first hop and destination node as the final hop.
- Avoids invalid, non-existent, or dead node IDs.
- Respects Time-To-Live (TTL) and hop budget constraints.
- Safely falls back to the original route if the attack is inactive, if the attacker is the destination, if network information is missing, or if no valid detour within TTL exists.

### Intensity Scaling
- **`LOW`**: Minimal inflation; selects the shortest valid detour strictly longer than the optimal route.
- **`MEDIUM`**: Moderate inflation; selects a median-length valid detour path.
- **`HIGH`**: Maximum inflation; selects the longest available simple path within the TTL budget.

### Available Interface
```python
from attacks.stretch import StretchAttack
from attacks.base import AttackIntensity

stretch = StretchAttack(
    attacker_node_id="N2",
    intensity=AttackIntensity.MEDIUM,
    start_time=0.0,
    duration=100.0,
)

# Apply to a route list
stretched_route = stretch.manipulate_route(
    route=["N1", "N2", "N3", "SINK"],
    network=network,
    current_time=10.0,
    ttl=20,
)

# Apply to either a route list or a Packet instance
manipulated = stretch.apply(
    target=packet_or_route,
    network=network,
    current_time=10.0,
    ttl=20,
)
```

---

## 3. Carousel Attack
File: `attacks/carousel.py`

Implements the **Carousel Vampire Attack** (Vasserman & Hopper, 2013).

### Attack Mechanism
- Deliberately introduces repeated routing cycles (loops) involving the attacker node and valid adjacent neighboring nodes.
- Packets repeatedly traverse back and forth across neighboring nodes (`attacker → partner → attacker`), multiplying energy depletion in localized clusters.
- Strictly bounds repetitions by the packet's remaining TTL budget to prevent infinite loops.
- Preserves packet integrity: source remains first hop, destination remains final hop.
- Reverts safely to the unmanipulated route when inactive, when attacker is the destination, when TTL is insufficient for a 2-hop loop, or when no alive neighbor partner is available.

### Intensity Scaling
- Each loop repetition (`partner → attacker`) adds exactly 2 hops.
- **`LOW`**: Minimal cycle inflation; injects 1 extra cycle repetition (2 additional hops).
- **`MEDIUM`**: Moderate cycle inflation; consumes approximately half of the remaining TTL budget.
- **`HIGH`**: Maximum cycle inflation; consumes the maximum allowable loop repetitions within the TTL budget.

### Available Interface
```python
from attacks.carousel import CarouselAttack
from attacks.base import AttackIntensity

carousel = CarouselAttack(
    attacker_node_id="N2",
    intensity=AttackIntensity.HIGH,
    start_time=0.0,
    duration=100.0,
)

# Manipulate route
looped_route = carousel.manipulate_route(
    route=["N1", "N2", "N3", "SINK"],
    network=network,
    current_time=5.0,
    ttl=15,
)
# Result: ['N1', 'N2', 'N3', 'N2', 'N3', 'N2', ..., 'N3', 'SINK']

# Apply to route or Packet
manipulated = carousel.apply(
    target=packet_or_route,
    network=network,
    current_time=5.0,
    ttl=15,
)
```

---

## 4. Attack Detection
File: `security/detector.py`

Implements **behavior-based anomaly detection** for Vampire Attacks. It does **not** inspect attack classes directly, but rather observes runtime telemetry anomalies across the network.

### Detection Signals
`AttackDetector` evaluates four distinct behavioral signals:
1. **Abnormal Forwarding Count**: Detects relay flooding when `node.forwarded` exceeds `forwarding_threshold`.
2. **Hop Inflation**: Compares observed route hop count against the optimal Dijkstra shortest path. Flagged when $\text{observed\_hops} / \text{optimal\_hops} \ge \text{hop\_inflation\_threshold}$.
3. **Route Repetition / Cycles**: Detects carousel loops when a node appears multiple times in a route (`route.count(node_id) > 1`).
4. **Abnormal Energy Depletion**: Detects anomalous battery drain when $(\text{initial\_energy} - \text{energy}) / \text{initial\_energy} \ge \text{energy\_threshold}$.

### Suspicion Score & DetectionResult
Individual signal scores are normalized to $[0.0, 1.0]$ and combined into a weighted composite suspicion score:
$$\text{suspicion\_score} = (w_f \cdot S_f) + (w_h \cdot S_h) + (w_c \cdot S_c) + (w_e \cdot S_e)$$
The score is strictly normalized between 0.0 and 1.0. If `suspicion_score >= detection_threshold`, the node is flagged as suspicious.

`DetectionResult` fields:
- `node_id` (str): Identifier of inspected node.
- `suspicious` (bool): Whether suspicion score meets or exceeds threshold.
- `suspicion_score` (float): Normalized score in $[0.0, 1.0]$.
- `reasons` (list[str]): Breached anomaly signals (`abnormal_forwarding`, `hop_inflation`, `route_cycle`, `abnormal_energy`).
- `signals` (dict[str, float]): Normalized sub-scores for each metric.
- `details` (dict[str, Any]): Raw diagnostic measurements (e.g. hop counts, ratios, cycle counts).

### Detector APIs
```python
from security.detector import AttackDetector

detector = AttackDetector(
    forwarding_threshold=10,
    hop_inflation_threshold=1.5,
    energy_threshold=0.4,
    detection_threshold=0.5,
)

# 1. Analyze single node
result = detector.analyze_node(
    node_id="N2",
    network=network,
    route=observed_route,
)

# 2. Inspect all nodes appearing in a route
route_results = detector.detect_from_route(
    route=observed_route,
    network=network,
)

# 3. Network-wide batch detection across all nodes
all_results = detector.detect(
    network=network,
    routes=[observed_route],
)
```

---

## 5. Attack Mitigation
File: `security/mitigation.py`

`MitigationManager` provides automated quarantine, blacklisting, and route recalculation to neutralize Vampire Attacks without compromising physical network state.

### Mitigation Principles
- **Consumes `DetectionResult`**: Directly ingests detection outcomes via `apply_detection()` and `apply_detections()`.
- **Node Isolation & Blacklisting**: Maintains an independent blacklist set (`_isolated_nodes`).
- **Non-Destructive**: Does **not** delete node objects and does **not** alter node battery levels. Nodes remain intact for logging, topology metrics, and visualization.
- **Routing Exclusion**: Completely excludes isolated nodes from participating in routing.
- **Dijkstra Route Recalculation**: Reroutes packets around isolated nodes using the existing Dijkstra implementation.
- **Multi-Node & Idempotent**: Supports isolating multiple suspicious nodes simultaneously; redundant isolation calls are idempotent.
- **Recovery & De-isolation**: Supports restoring nodes back to active routing via `clear_isolation(node_id)` and `clear_all()`.

### IsolatedNetworkView
`IsolatedNetworkView` is a lightweight read-only proxy that wraps an existing `Network` instance:
- `get_node(node_id)`: Returns `None` if `node_id` is isolated.
- `get_neighbors(node_id)`: Returns only alive, non-isolated neighbors.
- `distance(a, b)`: Delegates distance calculation to the underlying network.

This allows Dijkstra shortest path calculation to compute bypass routes strictly avoiding isolated nodes without duplicating Dijkstra or mutating the physical network.

### Mitigation Manager APIs
```python
from security.mitigation import MitigationManager

manager = MitigationManager()

# Isolate manually or from detection result
record = manager.isolate_node("N2", reasons=["hop_inflation"])
manager.apply_detection(detection_result)

# Query isolation status
assert manager.is_isolated("N2")
isolated_set = manager.get_isolated_nodes()

# Recalculate safe route bypassing isolated nodes
safe_route = manager.recalculate_route(
    network_or_router=network,
    source="N1",
    destination="SINK",
)

# Recovery / De-isolation
manager.clear_isolation("N2")
manager.clear_all()
```

---

# Testing

Run the complete test suite:
```bash
python -m pytest tests/ -v
```

Current test results:
```text
444 passed
```

### Complete Test Breakdown
| Module | Test File | Tests Passed |
|---|---|---|
| Part 1: Network & Energy | `tests/test_network_energy.py` | 96 |
| Part 2: Packet & Routing | `tests/test_packet_routing.py` | 153 |
| Part 3: Attack Foundation | `tests/test_attack_base.py` | 82 |
| Part 3: Stretch Attack | `tests/test_stretch_attack.py` | 21 |
| Part 3: Carousel Attack | `tests/test_carousel_attack.py` | 23 |
| Part 3: Attack Detection | `tests/test_detector.py` | 40 |
| Part 3: Attack Mitigation | `tests/test_mitigation.py` | 29 |
| **Total** | | **444 passed** |

---

# Development Roadmap

## Part 1 - Network & Energy
**Status: Completed**
Implemented modules:
```text
core/node.py
core/network.py
energy/energy_model.py
```

## Part 2 - Packet & Routing
**Status: Completed**
Implemented modules:
```text
core/packet.py
routing/dijkstra.py
routing/router.py
routing/routing_table.py
```

## Part 3 - Vampire Attack & Security
**Status: Completed**
Implemented modules:
```text
attacks/__init__.py
attacks/base.py
attacks/stretch.py
attacks/carousel.py
security/__init__.py
security/detector.py
security/mitigation.py
```

## Part 4 - Simulation, GUI & Analytics
**Status: Planned**
Planned components for future development:
- **Simulation Engine**: Event-driven or discrete-time simulation driver (`simulation/simulator.py`)
- **GUI Application**: Interactive desktop interface for topology creation and real-time visualization (`gui/`)
- **Network Visualization**: Canvas rendering nodes, communication links, routes, dead nodes, and attack loops
- **Metrics Collection**: System-wide energy metrics, latency, packet delivery ratio, and route inflation ratio (`metrics/`)
- **CSV Output**: Automated telemetry exports for experimental benchmarking
- **Comparative Experiments**: Automated comparison of benign, under-attack, and mitigated network runs

---

# Team Integration

```text
┌─────────────────────────────────────────┐
│       Part 1: Network & Energy          │
│       Node + Network + Energy           │
│              COMPLETED                  │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│       Part 2: Packet & Routing          │
│       Packet + Dijkstra + Router        │
│              COMPLETED                  │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│   Part 3: Vampire Attack & Security     │
│   Attacks + Detection + Mitigation      │
│              COMPLETED                  │
└────────────────────┬────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────┐
│       Part 4: Simulation & GUI          │
│       Simulation + UI + Analytics       │
│               PLANNED                   │
└─────────────────────────────────────────┘
```

---

# Scope Boundary

## Parts 1, 2, and 3 — Completed
The foundation, routing layer, and security suite are fully implemented and verified:
- **Part 1**: `Node`, `Network`, `EnergyModel`
- **Part 2**: `Packet`, `shortest_path` (Dijkstra), `RoutingTable`, `Router`
- **Part 3**: `BaseAttack`, `StretchAttack`, `CarouselAttack`, `AttackDetector`, `MitigationManager`, `IsolatedNetworkView`

## Part 4 — Planned
The following features belong strictly to future work:
- Simulation Engine (`simulation/simulator.py`)
- Graphical User Interface (`gui/`)
- Network Visualization
- System Metrics and CSV Exporters (`metrics/`)
- Comparative Benchmark Experiments
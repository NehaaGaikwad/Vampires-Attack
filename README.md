# Vampires Attack
A Wireless Sensor Network (WSN) simulator for studying **Vampire
Attacks**, their effect on network energy consumption, and possible
detection and mitigation techniques.
The system models battery-powered sensor nodes that communicate with
neighboring nodes and forward packets toward a central **Sink/Base
Station**.
## Project Overview
In a Wireless Sensor Network, sensor nodes have limited battery energy.
Nodes communicate with one another and forward packets through the
network until they reach the Sink.
A Vampire Attack manipulates packet routing so that packets travel
through unnecessarily long or repeated paths. This causes additional
packet forwarding and increased energy consumption, eventually reducing
the lifetime of the network.
The project is being developed in multiple stages:
```text
Network & Energy
       ↓
Packet & Routing
       ↓
Vampire Attack & Security
       ↓
Simulation, GUI & Analytics
```
# Current Status
## Part 1 - Network & Energy
**Status: Completed**
Part 1 provides the basic WSN infrastructure that the remaining parts
will build upon.
### Implemented
* Sensor node creation
* Unique node IDs
* 2-D node positions
* Initial battery energy
* Current battery energy
* Automatic alive/dead state
* Energy consumption
* Communication range
* Euclidean distance calculation
* Neighbor discovery
* Bidirectional neighbor relationships
* Sink/Base Station designation
* First-order radio energy model
* Transmission energy calculation
* Reception energy calculation
* Energy consumption during transmission
* Sent/received packet counters
* Dead-node protection
* Node reset functionality
**##
How to Run and Check
1. Open the Project
cd "C:\Users\Neha\Desktop\Coding\CN\Vampires-Attack"
2. Check the Current Branch
git status
git branch --show-current
Do not work directly on main.
3. Verify the Part 2 Files
core/packet.py
routing/dijkstra.py
routing/router.py
routing/routing_table.py
tests/test_packet_routing.py
4. Check Part 2 Imports
python -c "from core.packet import Packet, PacketStatus; from routing.dijkstra import shortest_path; from routing.router import Router; from routing.routing_table import RoutingTable; print('Part 2 imports OK')"
Expected:
Part 2 imports OK
5. Run Part 1 Tests
python -m pytest tests/test_network_energy.py -v
Expected:
96 passed
6. Run Part 2 Tests
python -m pytest tests/test_packet_routing.py -v
Expected:
153 passed
7. Run the Complete Test Suite
python -m pytest tests/ -v
Expected:
249 passed
This is:
96 Part 1
153 Part 2
-----------
249 total
8. Review Changes
git status
git diff --stat
git diff -- core/packet.py routing/dijkstra.py routing/router.py routing/routing_table.py
git diff -- tests/test_packet_routing.py
git diff -- README.md
Run the complete test suite once more before committing:
python -m pytest tests/ -v
The final expected result is:
249 passed
Testing**
```text
96 tests passed
```
The Part 1 test suite passes completely.
## Part 2 - Packet & Routing
**Status: Completed**
Part 2 implements packet representation and shortest-path routing on top
of the Part 1 foundation.
### Implemented
* Packet class with source, destination, route, hop count, TTL, visited
nodes
* Packet lifecycle states: IN_TRANSIT, DELIVERED, EXPIRED, DROPPED
* TTL enforcement --- packets expire when TTL reaches 0
* Loop prevention --- packets are dropped if they attempt to revisit a
node
* Dijkstra shortest-path algorithm using `network.distance()` for
edge weights
* Only alive nodes are considered (via `network.get_neighbors()`)
* RoutingTable for next-hop storage and cache
* Router integrating Packet, Dijkstra, RoutingTable, Network, and
EnergyModel
* `router.find_route(source, destination)` --- returns ordered path
or None
* `router.get_next_hop(current_node, destination)` --- returns
immediate next hop
* `router.route_packet(packet)` --- forwards packet hop-by-hop to
destination
* Energy integration via `EnergyModel.transmit()` at every hop
* `node.forwarded` counter correctly incremented on intermediate
relay nodes
* Dead-node safety at every forwarding step
* Unreachable destination handling (returns None / drops packet)
### Testing
```text
249 tests passed (96 Part 1 + 153 Part 2)
```
All original Part 1 tests continue to pass.
# Repository Structure
The repository is being developed incrementally.
```text
Vampires-Attack/
│
├── core/
│   ├── node.py                    # Part 1 - implemented
│   ├── network.py                 # Part 1 - implemented
│   └── packet.py                  # Part 2 - implemented
│
├── energy/
│   └── energy_model.py            # Part 1 - implemented
│
├── routing/
│   ├── dijkstra.py                # Part 2 - implemented
│   ├── router.py                  # Part 2 - implemented
│   └── routing_table.py           # Part 2 - implemented
│
├── attacks/
│   ├── stretch.py                 # Part 3 - planned
│   └── carousel.py                # Part 3 - planned
│
├── security/
│   ├── detector.py                # Part 3 - planned
│   └── mitigation.py              # Part 3 - planned
│
├── simulation/
│   └── simulator.py               # Part 4 - planned
│
├── gui/                           # Part 4 - planned
│
├── metrics/                       # Part 4 - planned
│
├── tests/
│   ├── test_network_energy.py     # Part 1 tests (96 tests)
│   └── test_packet_routing.py     # Part 2 tests (141 tests)
│
└── README.md
```
# Part 1 Architecture
Part 1 contains three main components:
```text
                  ┌──────────────┐
                  │    Network   │
                  └──────┬───────┘
                         │
              manages topology
                         │
          ┌──────────────┴──────────────┐
          │                             │
   ┌──────▼──────┐               ┌──────▼──────┐
   │    Nodes    │               │    Sink     │
   └──────┬──────┘               └─────────────┘
          │
          │ battery state
          ▼
   ┌──────────────┐
   │ EnergyModel  │
   └──────────────┘
```
### Responsibility separation
| Component     | Responsibility                                      
 |
| ------------- |
----------------------------------------------------- |
| `Node`        | Identity, position, energy, neighbors, counters  
    |
| `Network`     | Nodes, topology, distance, neighbors, Sink        
   |
| `EnergyModel` | Transmission/reception energy and battery
consumption |
Part 1 intentionally does **not** contain packet routing,
Vampire Attack logic, detection, mitigation, simulation, GUI, or
metrics.
# 1. Node
File:
```text
core/node.py
```
The `Node` class represents a single battery-powered sensor node.
## Creating a Node
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
| Parameter        | Description            |
| ---------------- | ---------------------- |
| `node_id`        | Unique node identifier |
| `x`              | X-coordinate           |
| `y`              | Y-coordinate           |
| `initial_energy` | Initial battery energy |
`initial_energy` must be greater than zero.
## Node Properties
### Identity
```python
node.id
```
Returns the node's unique identifier.
### Position
```python
node.x
node.y
node.position
```
Example:
```python
print(node.position)
```
Output:
```text
(10.0, 20.0)
```
The position is later used by `Network` to calculate distances.
### Energy
```python
node.initial_energy
node.energy
```
`initial_energy` stores the battery level when the node was created.
`energy` stores the currently remaining battery energy.
Example:
```python
print(node.initial_energy)
print(node.energy)
```
## Consuming Energy
Use:
```python
node.consume_energy(amount)
```
Example:
```python
node.consume_energy(20)
```
If the node initially has:
```text
100 J
```
the remaining energy becomes:
```text
80 J
```
Energy can never become negative.
If a node has `20 J` remaining:
```python
node.consume_energy(50)
```
results in:
```text
energy = 0
alive = False
```
## Alive / Dead State
The node's state is determined directly from its remaining energy.
```python
node.alive
```
The behavior is:
```text
energy > 0  → alive
energy = 0  → dead
```
There is no separate alive flag that can become inconsistent with the
battery.
This is important for routing because dead nodes must not be used for
forwarding.
## Neighbors
A node stores its neighboring node IDs:
```python
node.neighbors
```
Example:
```text
{"N2", "N3", "N5"}
```
The `Network` class manages the actual topology.
Normally, routing code should use:
```python
network.get_neighbors(node_id)
```
rather than manually modifying neighbor relationships.
## Packet Counters
Each node maintains three counters:
```python
node.sent
node.received
node.forwarded
```
Initial values:
```text
sent      = 0
received  = 0
forwarded = 0
```
`EnergyModel.transmit()` automatically increments:
```python
sender.sent
receiver.received
```
The `forwarded` counter is intentionally not handled by
`EnergyModel`.
The routing/simulation layer is responsible for deciding when a packet
was actually forwarded.
## Reset
A node can be restored to its initial state:
```python
node.reset()
```
This restores:
```text
energy    → initial_energy
sent      → 0
received  → 0
forwarded → 0
neighbors → empty
```
After resetting nodes, the network should rebuild its neighbor
relationships:
```python
network.update_neighbors()
```
# 2. Network
File:
```text
core/network.py
```
The `Network` class manages the WSN topology.
Its responsibilities are:
* Storing nodes
* Retrieving nodes
* Communication range
* Distance calculation
* Neighbor discovery
* Bidirectional neighbors
* Sink/Base Station
## Creating a Network
```python
from core.network import Network
network = Network(
    communication_range=50
)
```
The communication range determines whether two nodes can directly
communicate.
Two nodes are neighbors when:
```text
distance <= communication_range
```
## Adding Nodes
```python
network.add_node(node)
```
Example:
```python
from core.node import Node
from core.network import Network
network = Network(communication_range=50)
n1 = Node("N1", 0, 0, 100)
n2 = Node("N2", 30, 40, 100)
network.add_node(n1)
network.add_node(n2)
```
Nodes are stored by their IDs.
## Getting a Node
```python
node = network.get_node("N1")
```
If the node exists, the corresponding `Node` object is returned.
If the node does not exist:
```text
None
```
is returned.
## Distance Calculation
Use:
```python
network.distance(node_a, node_b)
```
The method accepts either `Node` objects or node IDs.
Examples:
```python
distance = network.distance(n1, n2)
```
or:
```python
distance = network.distance("N1", "N2")
```
The distance is calculated using Euclidean distance:
```text
distance = √((x1 - x2)² + (y1 - y2)²)
```
For example:
```text
N1 = (0, 0)
N2 = (3, 4)
distance = 5
```
The routing layer should use this existing method rather than
implementing another distance calculation.
# Neighbor Discovery
After adding nodes:
```python
network.update_neighbors()
```
The network checks every pair of nodes and creates bidirectional
neighbor relationships for nodes within communication range.
Example:
```text
N1 <------> N2
```
results in:
```python
N1.neighbors == {"N2"}
N2.neighbors == {"N1"}
```
Calling `update_neighbors()` rebuilds the topology and removes stale
neighbor relationships.
# Getting Neighbors
Use:
```python
neighbors = network.get_neighbors("N1")
```
This returns a list of **alive `Node` objects**.
Example:
```python
for neighbor in network.get_neighbors("N1"):
    print(neighbor.id)
```
The routing layer can directly access:
```python
neighbor.id
neighbor.position
neighbor.energy
neighbor.alive
```
# Dead Nodes
Dead nodes are not removed from the network.
They remain in:
```python
network.nodes
```
This allows future simulation and analytics code to inspect dead nodes.
However, dead nodes are excluded from:
```python
network.get_neighbors(...)
```
For example:
```text
N1 -------- N2 -------- N3
                       DEAD
```
If N3 has zero energy:
```python
network.get_neighbors("N2")
```
will not return N3.
This allows the routing layer to work with currently usable neighbors.
# Sink / Base Station
The Sink is represented using a normal `Node`.
Example:
```python
sink = Node(
    node_id="SINK",
    x=100,
    y=100,
    initial_energy=1000,
)
network.add_node(sink)
network.set_sink("SINK")
```
The Sink can then be accessed using:
```python
network.sink
```
Example:
```python
print(network.sink.id)
```
The Sink does not require a separate Node class.
# 3. Energy Model
File:
```text
energy/energy_model.py
```
The `EnergyModel` implements the first-order radio energy model.
## Transmission Energy
The transmission energy is:
```text
E_tx = E_elec × packet_size
     + E_amp × packet_size × distance²
```
## Reception Energy
The reception energy is:
```text
E_rx = E_elec × packet_size
```
## Default Constants
The current implementation uses:
```text
E_elec = 50e-9 J/bit
E_amp  = 100e-12 J/bit/m²
```
These values can be configured when creating an `EnergyModel`.
## Creating an Energy Model
```python
from energy.energy_model import EnergyModel
energy_model = EnergyModel()
```
Custom values can be provided:
```python
energy_model = EnergyModel(
    e_elec=50e-9,
    e_amp=100e-12,
)
```
# Transmission Energy Calculation
Use:
```python
tx_energy = energy_model.transmission_energy(
    packet_size,
    distance,
)
```
Example:
```python
tx_energy = energy_model.transmission_energy(
    packet_size=4000,
    distance=10,
)
```
# Reception Energy Calculation
Use:
```python
rx_energy = energy_model.reception_energy(
    packet_size
)
```
Example:
```python
rx_energy = energy_model.reception_energy(4000)
```
# Performing a Transmission
The main method that future routing and simulation code should use is:
```python
energy_model.transmit(
    sender,
    receiver,
    packet_size,
    distance,
)
```
Example:
```python
distance = network.distance(
    sender,
    receiver,
)
result = energy_model.transmit(
    sender=sender,
    receiver=receiver,
    packet_size=4000,
    distance=distance,
)
```
The transmission operation:
1. Checks that the sender is alive.
2. Checks that the receiver is alive.
3. Calculates transmission energy.
4. Calculates reception energy.
5. Deducts energy from the sender.
6. Deducts energy from the receiver.
7. Increments `sender.sent`.
8. Increments `receiver.received`.
9. Returns a `TransmissionResult`.
# TransmissionResult
`transmit()` returns a `TransmissionResult`.
Example:
```python
result = energy_model.transmit(
    sender,
    receiver,
    4000,
    distance,
)
```
The result provides:
```python
result.tx_energy
result.rx_energy
result.sender_alive
result.receiver_alive
```
This allows the future simulation layer to determine the energy consumed
and whether either node died as a result of the transmission.
# Dead Node Protection
The EnergyModel prevents transmissions involving dead nodes.
If the sender is dead:
```text
NodeDeadError
```
is raised.
If the receiver is dead:
```text
NodeDeadError
```
is raised.
Example:
```python
from energy.energy_model import NodeDeadError
try:
    result = energy_model.transmit(
        sender,
        receiver,
        4000,
        distance,
    )
except NodeDeadError:
    print("Transmission failed")
```
# How Part 2 Uses Part 1
Part 2 is responsible for packet handling and routing.
The expected Part 2 modules are:
```text
core/packet.py
routing/dijkstra.py
routing/router.py
routing/routing_table.py
```
Part 2 should **build on the existing Part 1 implementation**.
It should not duplicate Node, Network, distance, or energy
functionality.
The intended flow is:
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
# Example Routing Flow
Suppose the routing algorithm determines:
```text
N1 → N3 → N5 → SINK
```
For the first hop:
```python
sender = network.get_node("N1")
receiver = network.get_node("N3")
```
Get the distance from the Network:
```python
distance = network.distance(
    sender,
    receiver,
)
```
Then perform the transmission through the EnergyModel:
```python
result = energy_model.transmit(
    sender=sender,
    receiver=receiver,
    packet_size=4000,
    distance=distance,
)
```
The important separation is:
```text
Router
    → decides WHERE the packet goes
Network
    → provides topology and distance
EnergyModel
    → calculates and consumes energy
Node
    → stores the resulting state
```
The routing layer should decide the receiver. It should not reimplement
the Network or EnergyModel.
# Part 2 Integration Contract
The following interfaces are already available to the routing
implementation.
## Node
```python
node.id
node.x
node.y
node.position
node.initial_energy
node.energy
node.alive
node.neighbors
node.sent
node.received
node.forwarded
node.consume_energy(amount)
node.add_neighbor(node_id)
node.remove_neighbor(node_id)
node.reset()
```
## Network
```python
network.nodes
network.sink
network.communication_range
network.add_node(node)
network.get_node(node_id)
network.set_sink(node_id)
network.distance(
    node_a,
    node_b,
)
network.update_neighbors()
network.get_neighbors(node_id)
```
## EnergyModel
```python
energy_model.e_elec
energy_model.e_amp
energy_model.transmission_energy(
    packet_size,
    distance,
)
energy_model.reception_energy(
    packet_size,
)
energy_model.transmit(
    sender,
    receiver,
    packet_size,
    distance,
)
```
# Integration Rules for Part 2
### 1. Do not create another Node class
Use:
```python
from core.node import Node
```
### 2. Do not create another Network class
Use:
```python
from core.network import Network
```
### 3. Do not implement another distance function
Use:
```python
network.distance(...)
```
### 4. Do not manually calculate transmission energy
Use:
```python
energy_model.transmission_energy(...)
```
or:
```python
energy_model.transmit(...)
```
### 5. Do not manually deduct battery energy
Use:
```python
energy_model.transmit(...)
```
The EnergyModel already handles sender and receiver energy consumption.
### 6. Do not route through dead nodes
Use:
```python
network.get_neighbors(node_id)
```
This returns alive neighboring nodes.
### 7. Do not update `forwarded` inside EnergyModel
`forwarded` belongs to the routing/simulation layer because routing
determines whether a packet was actually forwarded.
### 8. Avoid unnecessary changes to Part 1
Treat the existing Node, Network, and EnergyModel interfaces as the
integration contract.
If Part 2 genuinely requires an interface change, coordinate the change
instead of independently redesigning Part 1.
# Complete Part 1 Example
The following demonstrates how the three Part 1 components work
together:
```python
from core.node import Node
from core.network import Network
from energy.energy_model import EnergyModel
network = Network(communication_range=50)
n1 = Node("N1", 0, 0, 100)
n2 = Node("N2", 30, 40, 100)
sink = Node(
    "SINK",
    60,
    40,
    1000,
)
network.add_node(n1)
network.add_node(n2)
network.add_node(sink)
network.set_sink("SINK")
network.update_neighbors()
energy_model = EnergyModel()
sender = network.get_node("N1")
receiver = network.get_node("N2")
distance = network.distance(
    sender,
    receiver,
)
result = energy_model.transmit(
    sender=sender,
    receiver=receiver,
    packet_size=4000,
    distance=distance,
)
print(result)
print(sender.energy)
print(receiver.energy)
```
In Part 2, the manually selected receiver will be replaced by the next
hop selected by the routing algorithm.
# Testing
Run the complete test suite using:
```bash
python -m pytest tests/ -v
```
Current result:
```text
237 passed  (96 Part 1 + 141 Part 2)
```
Run Part 1 tests only:
```bash
python -m pytest tests/test_network_energy.py -v
```
Run Part 2 tests only:
```bash
python -m pytest tests/test_packet_routing.py -v
```
The test suite covers:
* Node creation
* Node validation
* Node position
* Initial and current energy
* Energy consumption
* Energy depletion
* Energy non-negativity
* Neighbor management
* Node reset
* Network node management
* Distance calculation
* Communication range
* Communication boundary
* Bidirectional neighbors
* Neighbor rebuilding
* Dead-node exclusion
* Sink configuration
* Transmission energy
* Reception energy
* Transmission operation
* Sent/received counters
* Dead-node protection
* Part 1 integration
# Development Roadmap
## Part 1 - Network & Energy
**Status: Completed**
Implemented:
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
Implemented functionality:
* Packet source, destination, route, hop count, TTL, visited nodes
* Packet lifecycle: IN_TRANSIT, DELIVERED, EXPIRED, DROPPED
* Dijkstra shortest-path using `network.distance()` for edge weights
* Dead-node exclusion via `network.get_neighbors()`
* RoutingTable with set/get/remove/has_route/clear
* Router with `find_route`, `get_next_hop`, `route_packet`
* Packet forwarding with `EnergyModel.transmit()` at every hop
* `node.forwarded` counter on intermediate relay nodes
* TTL enforcement and expiry
* Loop prevention via visited set
* Unreachable destination handling (None / DROPPED)
* Dead-node safety at every forwarding step
### Part 2 API Reference
#### Packet
```python
from core.packet import Packet, PacketStatus
packet = Packet(
    source="N1",
    destination="SINK",
    ttl=10,           # max hops (default: 50)
    packet_size=4000, # bits (default: 4000)
)
packet.source          # "N1"
packet.destination     # "SINK"
packet.route           # \("N1"\)  (grows as packet moves)
packet.current_node    # "N1"
packet.hops            # 0
packet.ttl             # 10
packet.visited         # {"N1"}
packet.in_transit      # True
packet.delivered       # False
packet.expired         # False
packet.dropped         # False
packet.status          # PacketStatus.IN_TRANSIT
packet.advance("N2")   # move to next hop
packet.mark_dropped()  # explicitly drop
packet.mark_expired()  # explicitly expire
```
#### Dijkstra
```python
from routing.dijkstra import shortest_path
path = shortest_path(network, "N1", "SINK")
# => \("N1", "N2", "N3", "SINK"\)  or  None
```
Returns `None` if source/destination is nonexistent, dead, or
unreachable.
#### RoutingTable
```python
from routing.routing_table import RoutingTable
table = RoutingTable()
table.set_next_hop("SINK", "N3")   # store route
table.get_next_hop("SINK")         # => "N3"
table.has_route("SINK")            # => True
table.remove_route("SINK")
table.clear()
```
#### Router
```python
from routing.router import Router
router = Router(network, energy_model)
# Find full path
route = router.find_route("N1", "SINK")
# => \("N1", "N2", "N3", "SINK"\)  or  None
# Next hop only
next_hop = router.get_next_hop("N1", "SINK")
# => "N2"
# Route a packet end-to-end
from core.packet import Packet
packet = Packet("N1", "SINK", ttl=10)
router.route_packet(packet)
assert packet.delivered  # True
```
#### Forwarding Counters
For a route N1 → N2 → N3 → SINK:
| Node | `sent` | `received` | `forwarded` |
|------|--------|------------|-------------|
| N1   | 1      | 0          | 0           |
| N2   | 1      | 1          | 1           |
| N3   | 1      | 1          | 1           |
| SINK | 0      | 1          | 0           |
`sent` and `received` are managed by `EnergyModel.transmit()`.
`forwarded` is managed by the Router.
### Testing
```text
249 tests passed (96 Part 1 + 153 Part 2)
```
Run the full test suite:
```bash
python -m pytest tests/ -v
```
## Part 3 - Vampire Attack & Security
**Status: Planned**
Expected functionality:
```text
Stretch Attack
Carousel Attack
Attack Detection
Attack Mitigation
```
The attack layer will build on the packet and routing system.
## Part 4 - Simulation, GUI & Analytics
**Status: Planned**
Expected functionality:
```text
Simulation Engine
GUI
Network Visualization
Metrics
CSV Output
Experiments
```
The final stage will integrate the complete network, routing, attack,
security, and analytics layers.
# Team Integration
The intended integration order is:
```text
┌─────────────────────────────┐
│ Part 1: Network & Energy   │
│ Node + Network + Energy     │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Part 2: Packet & Routing   │
│ Packet + Dijkstra + Router │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Part 3: Security           │
│ Attacks + Detection        │
│ + Mitigation               │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Part 4: Simulation & GUI   │
│ Simulation + UI + Metrics  │
└─────────────────────────────┘
```
Each part should build on the previous part instead of duplicating its
responsibilities.
# Current Part 1 Contract
The most important interfaces for future modules are:
```python
network.get_node(node_id)
network.get_neighbors(node_id)
network.distance(node_a, node_b)
network.sink
node.alive
node.energy
node.consume_energy(amount)
energy_model.transmit(
    sender,
    receiver,
    packet_size,
    distance,
)
```
These interfaces provide the foundation required by the routing, attack,
simulation, and GUI layers.
# Scope Boundary
## Parts 1 and 2 --- Completed
Part 1 and Part 2 together implement the network foundation and routing
layer:
```text
Part 1 (Completed):
  Node, Network, EnergyModel
Part 2 (Completed):
  Packet, Dijkstra, RoutingTable, Router
```
## Parts 3 and 4 --- Planned
The following features are not yet implemented and belong to future
development stages:
```text
Part 3 (Planned):
  Stretch Attack
  Carousel Attack
  Attack detection
  Attack mitigation
Part 4 (Planned):
  Simulation engine
  GUI
  Network visualization
  Metrics
  CSV output
  Experiments
```
Parts 3 and 4 will build on the stable foundation provided by Parts 1
and 2.
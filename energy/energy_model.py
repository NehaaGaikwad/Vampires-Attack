"""
energy/energy_model.py
======================
Energy model for the Wireless Sensor Network (WSN).

Responsibilities
----------------
- Calculate transmission energy using the first-order radio model
- Calculate reception energy
- Apply energy consumption to sender / receiver Node objects
- Update packet counters on Node objects
- Enforce dead-node behaviour (dead nodes cannot transmit or receive)

This module does NOT contain routing, packet definitions, attacks,
detection, mitigation, simulation, or GUI logic.

Radio Energy Model
------------------
The model used is the classic first-order WSN radio model:

    Transmission energy:
        E_tx = E_elec * packet_size + E_amp * packet_size * distance²

    Reception energy:
        E_rx = E_elec * packet_size

Where:
    E_elec — electronics energy consumed per bit for both Tx and Rx
             (default: 50 nJ/bit = 50e-9 J/bit)
    E_amp  — amplifier energy consumed per bit per metre squared
             (default: 100 pJ/bit/m² = 100e-12 J/bit/m²)

These defaults match well-known WSN simulation literature (e.g., Heinzelman
et al., 2000) but are **fully configurable** via the constructor.

Per-operation costs are calculated with the formulas below and rounded
up to whole Joules when charged to a node, so a positive radio cost
cannot disappear through integer truncation.

Dead-Node Policy
----------------
Attempting to transmit from a **dead sender** or to a **dead receiver**
raises :exc:`NodeDeadError`.  This prevents silent corruption of the
network state.

Units
-----
- Energy : Joules (J)
- Distance: same unit as node coordinates (e.g. metres)
- Packet size: bits
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.node import Node


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class NodeDeadError(Exception):
    """Raised when a dead node is asked to transmit or receive.

    Attributes
    ----------
    node_id : str
        ID of the node that has no remaining energy.
    role : str
        Either ``"sender"`` or ``"receiver"``.
    """

    def __init__(self, node_id: str, role: str) -> None:
        self.node_id = node_id
        self.role = role
        super().__init__(
            f"Node {node_id!r} is dead and cannot act as {role}."
        )


# ---------------------------------------------------------------------------
# Transmission result
# ---------------------------------------------------------------------------


@dataclass
class TransmissionResult:
    """Data returned by :meth:`EnergyModel.transmit`.

    Attributes
    ----------
    tx_energy : int
        Whole Joules charged to the sender.
    rx_energy : int
        Whole Joules charged to the receiver.
    sender_alive : bool
        Whether the sender is still alive after the transmission.
    receiver_alive : bool
        Whether the receiver is still alive after the reception.
    """

    tx_energy: int
    rx_energy: int
    sender_alive: bool
    receiver_alive: bool


@dataclass
class PendingTransmission:
    """A started transmission whose receiver has not processed it yet."""

    sender: "Node"
    receiver: "Node"
    tx_energy: int
    rx_energy: int
    reception_processed: bool = False


# ---------------------------------------------------------------------------
# Energy Model
# ---------------------------------------------------------------------------


class EnergyModel:
    """First-order radio energy model for a WSN.

    Parameters
    ----------
    e_elec : float
        Electronics energy per bit for Tx and Rx circuits (Joules/bit).
        Default: ``50e-9`` (50 nJ/bit).
    e_amp : float
        Amplifier energy per bit per metre squared (Joules/bit/m²).
        Default: ``100e-12`` (100 pJ/bit/m²).

    Raises
    ------
    ValueError
        If either energy constant is non-positive.
    """

    # Default constants (first-order radio model, Heinzelman et al. 2000)
    DEFAULT_E_ELEC: float = 50e-9    # 50 nJ/bit
    DEFAULT_E_AMP: float = 100e-12   # 100 pJ/bit/m²

    def __init__(
        self,
        e_elec: float = DEFAULT_E_ELEC,
        e_amp: float = DEFAULT_E_AMP,
    ) -> None:
        if e_elec <= 0:
            raise ValueError(f"e_elec must be positive, got {e_elec!r}")
        if e_amp <= 0:
            raise ValueError(f"e_amp must be positive, got {e_amp!r}")

        self._e_elec: float = e_elec
        self._e_amp: float = e_amp

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def e_elec(self) -> float:
        """Electronics energy per bit (Joules/bit)."""
        return self._e_elec

    @property
    def e_amp(self) -> float:
        """Amplifier energy per bit per metre squared (Joules/bit/m²)."""
        return self._e_amp

    # ------------------------------------------------------------------
    # Energy calculations
    # ------------------------------------------------------------------

    def transmission_energy(self, packet_size: float, distance: float) -> float:
        """Calculate the energy required to **transmit** a packet.

        Formula::

            E_tx = E_elec * packet_size + E_amp * packet_size * distance²

        Parameters
        ----------
        packet_size : float
            Number of bits in the packet.
        distance : float
            Distance between sender and receiver (same unit as node coords).

        Returns
        -------
        float
            Energy in Joules.

        Raises
        ------
        ValueError
            If *packet_size* or *distance* is negative.
        """
        if packet_size < 0:
            raise ValueError(f"packet_size must be >= 0, got {packet_size!r}")
        if distance < 0:
            raise ValueError(f"distance must be >= 0, got {distance!r}")

        return self._e_elec * packet_size + self._e_amp * packet_size * distance ** 2

    def reception_energy(self, packet_size: float) -> float:
        """Calculate the energy required to **receive** a packet.

        Formula::

            E_rx = E_elec * packet_size

        Parameters
        ----------
        packet_size : float
            Number of bits in the packet.

        Returns
        -------
        float
            Energy in Joules.

        Raises
        ------
        ValueError
            If *packet_size* is negative.
        """
        if packet_size < 0:
            raise ValueError(f"packet_size must be >= 0, got {packet_size!r}")

        return self._e_elec * packet_size

    # ------------------------------------------------------------------
    # Transmission operation
    # ------------------------------------------------------------------

    def begin_transmission(
        self,
        sender: "Node",
        receiver: "Node",
        packet_size: float,
        distance: float,
    ) -> PendingTransmission:
        """Charge sender-side transmission energy and return pending reception."""
        if not sender.alive:
            raise NodeDeadError(sender.id, "sender")
        if not receiver.alive:
            raise NodeDeadError(receiver.id, "receiver")

        tx_energy = ceil(self.transmission_energy(packet_size, distance))
        rx_energy = ceil(self.reception_energy(packet_size))
        sender.consume_energy(tx_energy)
        sender.sent += 1
        return PendingTransmission(sender, receiver, tx_energy, rx_energy)

    def complete_reception(
        self,
        transmission: PendingTransmission,
    ) -> TransmissionResult:
        """Charge receiver energy once when the packet reaches that node."""
        if transmission.reception_processed:
            raise ValueError("Reception has already been processed.")
        if not transmission.receiver.alive:
            raise NodeDeadError(transmission.receiver.id, "receiver")

        transmission.reception_processed = True
        transmission.receiver.consume_energy(transmission.rx_energy)
        transmission.receiver.received += 1
        return TransmissionResult(
            tx_energy=transmission.tx_energy,
            rx_energy=transmission.rx_energy,
            sender_alive=transmission.sender.alive,
            receiver_alive=transmission.receiver.alive,
        )

    def transmit(
        self,
        sender: "Node",
        receiver: "Node",
        packet_size: float,
        distance: float,
    ) -> TransmissionResult:
        """Perform a single packet transmission from *sender* to *receiver*.

        Steps
        -----
        1. Raise :exc:`NodeDeadError` if the sender is dead.
        2. Raise :exc:`NodeDeadError` if the receiver is dead.
        3. Calculate transmission energy (``E_tx``) and round it up to
           whole Joules.
        4. Calculate reception energy (``E_rx``) and round it up to
           whole Joules.
        5. Consume ``E_tx`` from the sender's battery.
        6. Consume ``E_rx`` from the receiver's battery.
        7. Increment ``sender.sent``.
        8. Increment ``receiver.received``.
        9. Return a :class:`TransmissionResult`.

        Note: ``sender.forwarded`` is **not** incremented here.
        The routing/simulation layer is responsible for that counter
        because forwarding involves higher-level packet-flow decisions.

        Parameters
        ----------
        sender : Node
            The node transmitting the packet.
        receiver : Node
            The node receiving the packet.
        packet_size : float
            Packet size in bits.
        distance : float
            Distance between sender and receiver (same unit as coordinates).

        Returns
        -------
        TransmissionResult
            Energy consumed and liveness of both nodes after the operation.

        Raises
        ------
        NodeDeadError
            If the sender or receiver is already dead before the operation.
        ValueError
            If *packet_size* or *distance* is invalid.
        """
        transmission = self.begin_transmission(
            sender,
            receiver,
            packet_size,
            distance,
        )
        return self.complete_reception(transmission)

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"EnergyModel(e_elec={self._e_elec!r}, e_amp={self._e_amp!r})"
        )

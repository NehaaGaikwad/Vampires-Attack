"""
attacks/base.py
===============
Base abstraction and configuration for Vampire Attacks in the WSN simulator.

Responsibilities
----------------
- Defining attack taxonomy (AttackType: STRETCH, CAROUSEL)
- Defining attack intensity levels (AttackIntensity: LOW, MEDIUM, HIGH)
- Encapsulating attack parameters (attacker_node_id, attack_type, intensity, start_time, duration)
- Validating attack configuration
- Determining attack activity status over simulation time via lifecycle rules

This module does NOT implement specific attack routing algorithms,
modify network nodes, run simulations, or calculate energy consumption.
"""

from __future__ import annotations

from enum import Enum


class AttackType(Enum):
    """Supported Vampire Attack types in the WSN simulation."""

    STRETCH = "STRETCH"
    CAROUSEL = "CAROUSEL"


class AttackIntensity(Enum):
    """Intensity levels dictating attack aggressiveness."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class BaseAttack:
    """Base class for all Vampire Attacks.

    Parameters
    ----------
    attacker_node_id : str
        Unique identifier of the malicious sensor node (e.g. "N7").
        Must refer to an existing node ID in the network when simulated.
    attack_type : AttackType | str
        The type of Vampire Attack (Stretch or Carousel).
    intensity : AttackIntensity | str
        Aggressiveness level of the attack (LOW, MEDIUM, HIGH).
    start_time : float
        Simulation time at which the attack becomes active (must be >= 0).
    duration : float
        Length of simulation time the attack remains active (must be >= 0).

    Raises
    ------
    TypeError
        If parameter types are invalid (e.g. non-string ID, non-numeric time).
    ValueError
        If any configuration parameter contains an invalid value.
    """

    def __init__(
        self,
        attacker_node_id: str,
        attack_type: AttackType | str,
        intensity: AttackIntensity | str,
        start_time: float,
        duration: float,
    ) -> None:
        # Validate attacker_node_id
        if not isinstance(attacker_node_id, str):
            raise TypeError(
                f"attacker_node_id must be a string, got {type(attacker_node_id).__name__}"
            )
        clean_id = attacker_node_id.strip()
        if not clean_id:
            raise ValueError("attacker_node_id must not be empty or whitespace-only")
        self._attacker_node_id: str = clean_id

        # Validate attack_type
        self._attack_type: AttackType = self._validate_attack_type(attack_type)

        # Validate intensity
        self._intensity: AttackIntensity = self._validate_intensity(intensity)

        # Validate start_time
        if isinstance(start_time, bool) or not isinstance(start_time, (int, float)):
            raise TypeError(
                f"start_time must be numeric, got {type(start_time).__name__}"
            )
        if start_time < 0:
            raise ValueError(
                f"start_time must be non-negative, got {start_time!r}"
            )
        self._start_time: float = float(start_time)

        # Validate duration
        if isinstance(duration, bool) or not isinstance(duration, (int, float)):
            raise TypeError(
                f"duration must be numeric, got {type(duration).__name__}"
            )
        if duration < 0:
            raise ValueError(
                f"duration must be non-negative, got {duration!r}"
            )
        self._duration: float = float(duration)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_attack_type(attack_type: AttackType | str) -> AttackType:
        if isinstance(attack_type, AttackType):
            return attack_type
        if isinstance(attack_type, str):
            upper_name = attack_type.strip().upper()
            try:
                return AttackType[upper_name]
            except KeyError:
                valid_names = [t.name for t in AttackType]
                raise ValueError(
                    f"Invalid attack_type: {attack_type!r}. Must be one of {valid_names}"
                )
        raise ValueError(
            f"Invalid attack_type: {attack_type!r}. Must be an AttackType or str"
        )

    @staticmethod
    def _validate_intensity(intensity: AttackIntensity | str) -> AttackIntensity:
        if isinstance(intensity, AttackIntensity):
            return intensity
        if isinstance(intensity, str):
            upper_name = intensity.strip().upper()
            try:
                return AttackIntensity[upper_name]
            except KeyError:
                valid_names = [i.name for i in AttackIntensity]
                raise ValueError(
                    f"Invalid intensity: {intensity!r}. Must be one of {valid_names}"
                )
        raise ValueError(
            f"Invalid intensity: {intensity!r}. Must be an AttackIntensity or str"
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def attacker_node_id(self) -> str:
        """Node ID of the malicious sensor node."""
        return self._attacker_node_id

    @property
    def attack_type(self) -> AttackType:
        """Type of Vampire Attack."""
        return self._attack_type

    @property
    def intensity(self) -> AttackIntensity:
        """Attack intensity level."""
        return self._intensity

    @property
    def start_time(self) -> float:
        """Simulation time at which the attack becomes active."""
        return self._start_time

    @property
    def duration(self) -> float:
        """Active duration of the attack in simulation time."""
        return self._duration

    @property
    def end_time(self) -> float:
        """Derived simulation end time for the attack (start_time + duration)."""
        return self._start_time + self._duration

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def is_active(self, current_time: float) -> bool:
        """Determine whether the attack is active at the given simulation time.

        Lifecycle Rules
        ---------------
        - If current_time < start_time: returns False
        - If current_time >= start_time + duration: returns False
        - If start_time <= current_time < start_time + duration: returns True
        - When duration == 0: returns False for all times (no active interval).

        Parameters
        ----------
        current_time : float
            Current simulation timestamp.

        Returns
        -------
        bool
            True if the attack is actively executing, False otherwise.

        Raises
        ------
        TypeError
            If current_time is not a numeric value.
        """
        if isinstance(current_time, bool) or not isinstance(current_time, (int, float)):
            raise TypeError(
                f"current_time must be numeric, got {type(current_time).__name__}"
            )
        return self._start_time <= current_time < self.end_time

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"attacker_node_id={self._attacker_node_id!r}, "
            f"attack_type={self._attack_type.name}, "
            f"intensity={self._intensity.name}, "
            f"start_time={self._start_time}, "
            f"duration={self._duration})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseAttack):
            return NotImplemented
        return (
            self._attacker_node_id == other._attacker_node_id
            and self._attack_type == other._attack_type
            and self._intensity == other._intensity
            and self._start_time == other._start_time
            and self._duration == other._duration
        )

    def __hash__(self) -> int:
        return hash((
            self._attacker_node_id,
            self._attack_type,
            self._intensity,
            self._start_time,
            self._duration,
        ))

"""
attacks package
===============
Vampire Attack implementations and configurations for the WSN simulator.
"""

from attacks.base import AttackIntensity, AttackType, BaseAttack
from attacks.carousel import CarouselAttack
from attacks.stretch import StretchAttack

__all__ = [
    "AttackIntensity",
    "AttackType",
    "BaseAttack",
    "CarouselAttack",
    "StretchAttack",
]

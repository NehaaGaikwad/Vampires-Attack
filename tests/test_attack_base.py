"""
tests/test_attack_base.py
=========================
Unit tests for the Vampire Attack base configuration and lifecycle (Phase 1).
"""

import pytest

from attacks.base import AttackIntensity, AttackType, BaseAttack


class TestAttackCreation:
    """Tests for creating BaseAttack instances with valid parameters."""

    def test_valid_creation_with_enums(self):
        attack = BaseAttack(
            attacker_node_id="N7",
            attack_type=AttackType.STRETCH,
            intensity=AttackIntensity.HIGH,
            start_time=10.0,
            duration=30.0,
        )
        assert attack.attacker_node_id == "N7"
        assert attack.attack_type == AttackType.STRETCH
        assert attack.intensity == AttackIntensity.HIGH
        assert attack.start_time == 10.0
        assert attack.duration == 30.0
        assert attack.end_time == 40.0

    def test_valid_creation_with_string_specifiers(self):
        attack = BaseAttack(
            attacker_node_id="N1",
            attack_type="carousel",
            intensity="medium",
            start_time=0,
            duration=15,
        )
        assert attack.attacker_node_id == "N1"
        assert attack.attack_type == AttackType.CAROUSEL
        assert attack.intensity == AttackIntensity.MEDIUM
        assert attack.start_time == 0.0
        assert attack.duration == 15.0

    def test_whitespace_in_node_id_stripped(self):
        attack = BaseAttack(
            attacker_node_id="  N42  ",
            attack_type=AttackType.STRETCH,
            intensity=AttackIntensity.LOW,
            start_time=5,
            duration=10,
        )
        assert attack.attacker_node_id == "N42"


class TestAttackTypes:
    """Tests for AttackType enumeration and validation."""

    def test_enum_members_exist(self):
        assert AttackType.STRETCH.value == "STRETCH"
        assert AttackType.CAROUSEL.value == "CAROUSEL"

    @pytest.mark.parametrize("val,expected", [
        ("stretch", AttackType.STRETCH),
        ("STRETCH", AttackType.STRETCH),
        ("Stretch", AttackType.STRETCH),
        ("carousel", AttackType.CAROUSEL),
        ("CAROUSEL", AttackType.CAROUSEL),
        ("Carousel", AttackType.CAROUSEL),
    ])
    def test_valid_attack_type_strings(self, val, expected):
        attack = BaseAttack("N1", val, AttackIntensity.LOW, 0, 10)
        assert attack.attack_type == expected

    @pytest.mark.parametrize("invalid_val", [
        "INVALID",
        "FLOODING",
        "",
        "   ",
        123,
        None,
        ["STRETCH"],
    ])
    def test_invalid_attack_types_raise_value_error(self, invalid_val):
        with pytest.raises(ValueError, match="Invalid attack_type"):
            BaseAttack("N1", invalid_val, AttackIntensity.LOW, 0, 10)


class TestAttackIntensity:
    """Tests for AttackIntensity enumeration and validation."""

    def test_enum_members_exist(self):
        assert AttackIntensity.LOW.value == "LOW"
        assert AttackIntensity.MEDIUM.value == "MEDIUM"
        assert AttackIntensity.HIGH.value == "HIGH"

    @pytest.mark.parametrize("val,expected", [
        ("low", AttackIntensity.LOW),
        ("LOW", AttackIntensity.LOW),
        ("medium", AttackIntensity.MEDIUM),
        ("MEDIUM", AttackIntensity.MEDIUM),
        ("high", AttackIntensity.HIGH),
        ("HIGH", AttackIntensity.HIGH),
    ])
    def test_valid_intensity_strings(self, val, expected):
        attack = BaseAttack("N1", AttackType.STRETCH, val, 0, 10)
        assert attack.intensity == expected

    @pytest.mark.parametrize("invalid_val", [
        "EXTREME",
        "NONE",
        "",
        "   ",
        99,
        None,
        ("HIGH",),
    ])
    def test_invalid_intensity_raises_value_error(self, invalid_val):
        with pytest.raises(ValueError, match="Invalid intensity"):
            BaseAttack("N1", AttackType.STRETCH, invalid_val, 0, 10)


class TestStartTime:
    """Tests for start_time configuration and validation."""

    def test_zero_start_time_allowed(self):
        attack = BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 0, 10)
        assert attack.start_time == 0.0

    def test_positive_start_time_allowed(self):
        attack = BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 25.5, 10)
        assert attack.start_time == 25.5

    @pytest.mark.parametrize("negative_time", [-0.001, -1, -50.0])
    def test_negative_start_time_raises_value_error(self, negative_time):
        with pytest.raises(ValueError, match="start_time must be non-negative"):
            BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, negative_time, 10)

    @pytest.mark.parametrize("invalid_type", ["10", None, [10], True, False])
    def test_non_numeric_start_time_raises_type_error(self, invalid_type):
        with pytest.raises(TypeError, match="start_time must be numeric"):
            BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, invalid_type, 10)


class TestDuration:
    """Tests for duration configuration and validation."""

    def test_positive_duration_allowed(self):
        attack = BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 10, 20.5)
        assert attack.duration == 20.5

    def test_zero_duration_allowed(self):
        attack = BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 10, 0)
        assert attack.duration == 0.0

    @pytest.mark.parametrize("negative_duration", [-0.001, -1, -25.0])
    def test_negative_duration_raises_value_error(self, negative_duration):
        with pytest.raises(ValueError, match="duration must be non-negative"):
            BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 10, negative_duration)

    @pytest.mark.parametrize("invalid_type", ["20", None, [20], True, False])
    def test_non_numeric_duration_raises_type_error(self, invalid_type):
        with pytest.raises(TypeError, match="duration must be numeric"):
            BaseAttack("N1", AttackType.STRETCH, AttackIntensity.LOW, 10, invalid_type)


class TestEndTime:
    """Tests for derived end_time property."""

    def test_end_time_calculation(self):
        attack = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 10, 20)
        assert attack.end_time == 30.0

    def test_end_time_with_zero_start_time(self):
        attack = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 0, 15.5)
        assert attack.end_time == 15.5

    def test_end_time_with_zero_duration(self):
        attack = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 12.0, 0)
        assert attack.end_time == 12.0


class TestIsActiveLifecycle:
    """Tests for is_active(current_time) lifecycle state transitions."""

    @pytest.fixture
    def sample_attack(self):
        # Active in range [10, 30)
        return BaseAttack(
            attacker_node_id="N7",
            attack_type=AttackType.STRETCH,
            intensity=AttackIntensity.MEDIUM,
            start_time=10,
            duration=20,
        )

    def test_before_start_time(self, sample_attack):
        assert not sample_attack.is_active(0)
        assert not sample_attack.is_active(5)
        assert not sample_attack.is_active(9)
        assert not sample_attack.is_active(9.999)

    def test_exact_start_time_is_active(self, sample_attack):
        assert sample_attack.is_active(10)
        assert sample_attack.is_active(10.0)

    def test_during_active_window(self, sample_attack):
        assert sample_attack.is_active(15)
        assert sample_attack.is_active(20)
        assert sample_attack.is_active(29)
        assert sample_attack.is_active(29.999)

    def test_exact_end_time_is_inactive(self, sample_attack):
        # Interval is half-open [start_time, end_time)
        assert not sample_attack.is_active(30)
        assert not sample_attack.is_active(30.0)

    def test_after_end_time(self, sample_attack):
        assert not sample_attack.is_active(31)
        assert not sample_attack.is_active(100)

    def test_zero_duration_is_never_active(self):
        zero_attack = BaseAttack("N7", AttackType.CAROUSEL, AttackIntensity.LOW, 10, 0)
        assert not zero_attack.is_active(0)
        assert not zero_attack.is_active(10)
        assert not zero_attack.is_active(15)

    @pytest.mark.parametrize("invalid_current_time", ["10", None, True, False, []])
    def test_non_numeric_current_time_raises_type_error(self, sample_attack, invalid_current_time):
        with pytest.raises(TypeError, match="current_time must be numeric"):
            sample_attack.is_active(invalid_current_time)


class TestInvalidAttackerId:
    """Tests for validating attacker_node_id."""

    @pytest.mark.parametrize("empty_id", ["", "   ", "\t\n  "])
    def test_empty_or_whitespace_id_raises_value_error(self, empty_id):
        with pytest.raises(ValueError, match="attacker_node_id must not be empty or whitespace-only"):
            BaseAttack(empty_id, AttackType.STRETCH, AttackIntensity.LOW, 0, 10)

    @pytest.mark.parametrize("invalid_type", [None, 123, True, ["N1"], {"id": "N1"}])
    def test_non_string_id_raises_type_error(self, invalid_type):
        with pytest.raises(TypeError, match="attacker_node_id must be a string"):
            BaseAttack(invalid_type, AttackType.STRETCH, AttackIntensity.LOW, 0, 10)


class TestInheritanceAndExtension:
    """Tests that BaseAttack can be cleanly subclassed."""

    def test_subclassing_base_attack(self):
        class DummyAttack(BaseAttack):
            def custom_behavior(self) -> str:
                return f"attack from {self.attacker_node_id}"

        dummy = DummyAttack("N9", AttackType.CAROUSEL, AttackIntensity.HIGH, 5, 25)
        assert isinstance(dummy, BaseAttack)
        assert dummy.attacker_node_id == "N9"
        assert dummy.custom_behavior() == "attack from N9"
        assert dummy.is_active(10)
        assert not dummy.is_active(30)


class TestDunderHelpersAndImmutability:
    """Tests for __repr__, __eq__, __hash__, and read-only properties."""

    def test_repr_format(self):
        attack = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 10.0, 30.0)
        expected = "BaseAttack(attacker_node_id='N7', attack_type=STRETCH, intensity=HIGH, start_time=10.0, duration=30.0)"
        assert repr(attack) == expected

    def test_equality_and_hash(self):
        a1 = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 10, 30)
        a2 = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 10, 30)
        a3 = BaseAttack("N8", AttackType.STRETCH, AttackIntensity.HIGH, 10, 30)

        assert a1 == a2
        assert a1 != a3
        assert hash(a1) == hash(a2)
        assert a1 != "not an attack"

        attack_set = {a1, a2, a3}
        assert len(attack_set) == 2

    @pytest.mark.parametrize("prop", [
        "attacker_node_id",
        "attack_type",
        "intensity",
        "start_time",
        "duration",
        "end_time",
    ])
    def test_properties_are_read_only(self, prop):
        attack = BaseAttack("N7", AttackType.STRETCH, AttackIntensity.HIGH, 10, 30)
        with pytest.raises(AttributeError):
            setattr(attack, prop, "new_value")

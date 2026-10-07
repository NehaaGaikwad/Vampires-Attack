from collections.abc import Iterable, Mapping
from statistics import fmean

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure


_SCENARIOS = ("normal", "stretch", "carousel")
_SCENARIO_LABELS = ("Normal", "Stretch", "Carousel")


def plot_comparison_results(
    results: Iterable[Mapping[str, object]],
) -> tuple[Figure, tuple[Axes, Axes]]:
    """Plot average hops and energy consumption for all three experiment scenarios."""
    values: dict[str, dict[str, list[float]]] = {
        scenario: {"hops": [], "energy": []} for scenario in _SCENARIOS
    }

    for result in results:
        scenario_value = result.get("scenario")
        if not isinstance(scenario_value, str):
            raise ValueError("Each comparison result must include a scenario name.")
        scenario = scenario_value.strip().lower()
        if scenario not in values:
            continue

        hops = result.get("hops")
        energy = result.get("total_energy_consumed")
        if isinstance(hops, bool) or not isinstance(hops, (int, float)):
            raise ValueError(f"Scenario {scenario!r} has an invalid hops value.")
        if isinstance(energy, bool) or not isinstance(energy, (int, float)):
            raise ValueError(
                f"Scenario {scenario!r} has an invalid total_energy_consumed value."
            )
        values[scenario]["hops"].append(float(hops))
        values[scenario]["energy"].append(float(energy))

    missing_scenarios = [
        scenario for scenario in _SCENARIOS if not values[scenario]["hops"]
    ]
    if missing_scenarios:
        raise ValueError(
            f"Comparison results are missing scenarios: {missing_scenarios!r}"
        )

    average_hops = [
        fmean(values[scenario]["hops"]) for scenario in _SCENARIOS
    ]
    average_energy = [
        fmean(values[scenario]["energy"]) for scenario in _SCENARIOS
    ]

    figure, (hops_ax, energy_ax) = plt.subplots(1, 2, figsize=(10, 4))
    positions = range(len(_SCENARIOS))
    hops_ax.bar(positions, average_hops, color=("tab:blue", "tab:orange", "tab:green"))
    hops_ax.set_xticks(list(positions), _SCENARIO_LABELS)
    hops_ax.set_ylabel("Average hops")
    hops_ax.set_title("Route length")

    energy_ax.bar(
        positions,
        average_energy,
        color=("tab:blue", "tab:orange", "tab:green"),
    )
    energy_ax.set_xticks(list(positions), _SCENARIO_LABELS)
    energy_ax.set_ylabel("Average energy consumed (J)")
    energy_ax.set_title("Energy consumption")

    figure.tight_layout()
    return figure, (hops_ax, energy_ax)

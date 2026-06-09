from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Signal, SignalOutcome

TRACKED_ANALYSIS_TYPES = (
    "bullish_21ma_touch",
    "bullish_60ma_touch",
    "bearish_21ma_touch",
    "bearish_60ma_touch",
)


@dataclass(frozen=True)
class JoinedOutcome:
    signal: Signal
    outcome: SignalOutcome


def build_signal_stats(db: Session) -> dict[str, Any]:
    signals = list(db.query(Signal).all())
    outcomes = (
        db.query(SignalOutcome, Signal)
        .join(Signal, SignalOutcome.signal_id == Signal.id)
        .all()
    )
    joined = [JoinedOutcome(signal=signal, outcome=outcome) for outcome, signal in outcomes]

    return {
        "total_signals": len(signals),
        "long_signals": sum(1 for signal in signals if signal.direction == "LONG"),
        "short_signals": sum(1 for signal in signals if signal.direction == "SHORT"),
        "overall": _summarize_outcomes(joined),
        "by_signal_type": {
            signal_type: _summarize_outcomes(
                [item for item in joined if item.signal.analysis_signal_type == signal_type]
            )
            for signal_type in TRACKED_ANALYSIS_TYPES
        },
    }


def _summarize_outcomes(items: list[JoinedOutcome]) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[int, list[SignalOutcome]] = defaultdict(list)
    for item in items:
        grouped[item.outcome.horizon_hours].append(item.outcome)

    return {
        f"{horizon}h": _summarize_horizon(grouped.get(horizon, []))
        for horizon in (12, 24, 48, 72)
    }


def _summarize_horizon(outcomes: list[SignalOutcome]) -> dict[str, float | int | None]:
    if not outcomes:
        return {
            "count": 0,
            "avg_return_pct": None,
            "win_rate_pct": None,
            "avg_max_favorable_return_pct": None,
            "avg_max_adverse_return_pct": None,
        }

    count = len(outcomes)
    return {
        "count": count,
        "avg_return_pct": _avg([item.return_pct for item in outcomes]),
        "win_rate_pct": sum(1 for item in outcomes if item.return_pct > 0) / count * 100,
        "avg_max_favorable_return_pct": _avg(
            [item.max_favorable_return_pct for item in outcomes]
        ),
        "avg_max_adverse_return_pct": _avg([item.max_adverse_return_pct for item in outcomes]),
    }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values)


def find_best_signal_type(stats: dict[str, Any], horizon_key: str = "24h") -> tuple[str, dict] | None:
    candidates = []
    for signal_type, summary in stats["by_signal_type"].items():
        horizon = summary[horizon_key]
        avg_return = horizon["avg_return_pct"]
        if avg_return is not None:
            candidates.append((signal_type, horizon))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1]["avg_return_pct"])

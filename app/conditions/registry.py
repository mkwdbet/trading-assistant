from typing import Any


MA_TIMEFRAME_OPTIONS = ["1h", "4h", "12h", "1d", "3d", "1w", "1M"]


CONDITION_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "ma_ordering",
        "label": "MA Ordering",
        "category": "MA",
        "recommended": True,
        "description": "Build an expression such as Price > SMA21 > SMA60.",
        "params_schema": {
            "timeframe": {"type": "select", "options": MA_TIMEFRAME_OPTIONS, "default": "4h"},
            "items": {
                "type": "ma_expression",
                "operand_options": ["price", "sma", "ema"],
                "period_options": [7, 21, 60, 120, 200, 224, 365, "custom"],
                "default": [
                    {"source": "ma", "ma_type": "sma", "period": 21},
                    {"source": "ma", "ma_type": "sma", "period": 60},
                ],
            },
        },
    },
    {
        "id": "ma_alignment",
        "label": "MA Alignment",
        "category": "MA",
        "description": "Fast, mid, and slow moving averages are aligned.",
        "params_schema": {
            "direction": {"type": "select", "options": ["bullish", "bearish"], "default": "bullish"},
            "timeframe": {"type": "select", "options": MA_TIMEFRAME_OPTIONS, "default": "4h"},
            "ma_type": {"type": "select", "options": ["sma"], "default": "sma"},
            "fast": {"type": "number", "default": 7, "min": 1, "step": 1},
            "mid": {"type": "number", "default": 21, "min": 1, "step": 1},
            "slow": {"type": "number", "default": 60, "min": 1, "step": 1},
        },
    },
    {
        "id": "ma_touch",
        "label": "MA Touch",
        "category": "MA",
        "description": "Close is within tolerance of a moving average.",
        "params_schema": {
            "timeframe": {"type": "select", "options": MA_TIMEFRAME_OPTIONS, "default": "4h"},
            "ma_type": {"type": "select", "options": ["sma"], "default": "sma"},
            "period": {"type": "number", "default": 21, "min": 1, "step": 1},
            "tolerance_pct": {"type": "number", "default": 0.001, "min": 0, "step": 0.0001},
        },
    },
    {
        "id": "rsi_threshold",
        "label": "RSI Threshold",
        "category": "RSI",
        "description": "RSI is above or below a selected value.",
        "params_schema": {
            "timeframe": {"type": "select", "options": ["4h"], "default": "4h"},
            "period": {"type": "number", "default": 14, "min": 1, "step": 1},
            "operator": {"type": "select", "options": [">=", "<="], "default": ">="},
            "value": {"type": "number", "default": 50, "min": 0, "max": 100, "step": 1},
        },
    },
    {
        "id": "volume_ratio",
        "label": "Volume Ratio",
        "category": "Volume",
        "description": "Volume is a multiplier of average volume.",
        "params_schema": {
            "timeframe": {"type": "select", "options": ["4h"], "default": "4h"},
            "period": {"type": "number", "default": 20, "min": 1, "step": 1},
            "operator": {"type": "select", "options": [">=", "<="], "default": ">="},
            "ratio": {"type": "number", "default": 1.0, "min": 0, "step": 0.1},
        },
    },
    {
        "id": "atr_rising",
        "label": "ATR Rising",
        "category": "ATR",
        "description": "ATR is higher than the previous candle",
        "params_schema": {
            "timeframe": {"type": "select", "options": ["4h"], "default": "4h"},
            "period": {"type": "number", "default": 14, "min": 1, "step": 1},
        },
    },
)

LEGACY_CONDITION_MAP: dict[str, dict[str, Any]] = {
    "ma_bullish_4h": {
        "type": "ma_alignment",
        "params": {"direction": "bullish", "timeframe": "4h", "ma_type": "sma", "fast": 7, "mid": 21, "slow": 60},
    },
    "ma_bearish_4h": {
        "type": "ma_alignment",
        "params": {"direction": "bearish", "timeframe": "4h", "ma_type": "sma", "fast": 7, "mid": 21, "slow": 60},
    },
    "touch_ma21": {
        "type": "ma_touch",
        "params": {"timeframe": "4h", "ma_type": "sma", "period": 21, "tolerance_pct": 0.001},
    },
    "touch_ma60": {
        "type": "ma_touch",
        "params": {"timeframe": "4h", "ma_type": "sma", "period": 60, "tolerance_pct": 0.001},
    },
    "rsi_gte_30": {
        "type": "rsi_threshold",
        "params": {"timeframe": "4h", "period": 14, "operator": ">=", "value": 30},
    },
    "rsi_lte_70": {
        "type": "rsi_threshold",
        "params": {"timeframe": "4h", "period": 14, "operator": "<=", "value": 70},
    },
    "volume_above_average": {
        "type": "volume_ratio",
        "params": {"timeframe": "4h", "period": 20, "operator": ">=", "ratio": 1.0},
    },
    "atr_rising": {
        "type": "atr_rising",
        "params": {"timeframe": "4h", "period": 14},
    },
}


def get_condition_registry() -> list[dict[str, Any]]:
    return [dict(condition) for condition in CONDITION_REGISTRY]


def normalize_entry_conditions(conditions: list[str | dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [_normalize_condition(condition) for condition in conditions or []]


def _normalize_condition(condition: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(condition, str):
        if condition not in LEGACY_CONDITION_MAP:
            raise ValueError(f"Unknown condition id: {condition}")
        return _normalize_condition(LEGACY_CONDITION_MAP[condition])

    condition_type = condition.get("type")
    if not condition_type:
        raise ValueError("Condition object must include type")

    definition = _definition_for(condition_type)
    params = dict(condition.get("params") or {})
    schema = definition["params_schema"]
    normalized_params = {
        key: _normalize_param(condition_type, key, params.get(key, config.get("default")), config)
        for key, config in schema.items()
    }
    _validate_options(condition_type, normalized_params, schema)
    return {"type": condition_type, "params": normalized_params}


def _definition_for(condition_type: str) -> dict[str, Any]:
    for definition in CONDITION_REGISTRY:
        if definition["id"] == condition_type:
            return definition
    raise ValueError(f"Unknown condition type: {condition_type}")


def _validate_options(condition_type: str, params: dict[str, Any], schema: dict[str, Any]) -> None:
    for key, config in schema.items():
        options = config.get("options")
        if options and params[key] not in options:
            raise ValueError(f"Invalid {key} for {condition_type}: {params[key]}")


def _normalize_param(condition_type: str, key: str, value: Any, config: dict[str, Any]) -> Any:
    if condition_type == "ma_ordering" and key == "items":
        return _normalize_ma_ordering_items(value)
    return value


def _normalize_ma_ordering_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) < 2:
        raise ValueError("MA Ordering requires at least two items")
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("MA Ordering items must be objects")
        source = item.get("source")
        if source == "price":
            normalized.append({"source": "price"})
            continue
        if source != "ma":
            raise ValueError(f"Invalid MA Ordering source: {source}")
        ma_type = str(item.get("ma_type", "sma")).lower()
        if ma_type not in {"sma", "ema"}:
            raise ValueError(f"Invalid MA Ordering ma_type: {ma_type}")
        period = int(item.get("period", 21))
        if period < 1:
            raise ValueError("MA Ordering period must be positive")
        normalized.append({"source": "ma", "ma_type": ma_type, "period": period})
    return normalized

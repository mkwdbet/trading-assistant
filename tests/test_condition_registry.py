from app.conditions.registry import get_condition_registry, normalize_entry_conditions


def test_condition_registry_exposes_mvp_conditions() -> None:
    registry = get_condition_registry()
    ids = {condition["id"] for condition in registry}

    assert "ma_alignment" in ids
    assert "ma_ordering" in ids
    assert "ma_touch" in ids
    assert "rsi_threshold" in ids
    assert "volume_ratio" in ids
    assert "atr_rising" in ids

    touch = next(condition for condition in registry if condition["id"] == "ma_touch")
    assert touch["category"] == "MA"
    assert touch["params_schema"]["period"]["default"] == 21
    assert touch["params_schema"]["tolerance_pct"]["default"] == 0.001

    ordering = next(condition for condition in registry if condition["id"] == "ma_ordering")
    assert ordering["label"] == "MA Ordering"
    assert ordering["recommended"] is True
    assert ordering["params_schema"]["items"]["type"] == "ma_expression"
    assert ordering["params_schema"]["items"]["default"] == [
        {"source": "ma", "ma_type": "sma", "period": 21},
        {"source": "ma", "ma_type": "sma", "period": 60},
    ]


def test_legacy_condition_ids_normalize_to_parameterized_conditions() -> None:
    conditions = normalize_entry_conditions(["ma_bullish_4h", "touch_ma21", "rsi_lte_70"])

    assert conditions == [
        {
            "type": "ma_alignment",
            "params": {
                "direction": "bullish",
                "timeframe": "4h",
                "ma_type": "sma",
                "fast": 7,
                "mid": 21,
                "slow": 60,
            },
        },
        {
            "type": "ma_touch",
            "params": {
                "timeframe": "4h",
                "ma_type": "sma",
                "period": 21,
                "tolerance_pct": 0.001,
            },
        },
        {
            "type": "rsi_threshold",
            "params": {
                "timeframe": "4h",
                "period": 14,
                "operator": "<=",
                "value": 70,
            },
        },
    ]


def test_parameterized_condition_defaults_are_applied() -> None:
    conditions = normalize_entry_conditions(
        [
            {
                "type": "ma_touch",
                "params": {"period": 60, "tolerance_pct": 0.002},
            }
        ]
    )

    assert conditions == [
        {
            "type": "ma_touch",
            "params": {
                "timeframe": "4h",
                "ma_type": "sma",
                "period": 60,
                "tolerance_pct": 0.002,
            },
        }
    ]


def test_ma_ordering_condition_normalizes_expression_items() -> None:
    conditions = normalize_entry_conditions(
        [
            {
                "type": "ma_ordering",
                "params": {
                    "timeframe": "1d",
                    "items": [
                        {"source": "price"},
                        {"source": "ma", "ma_type": "ema", "period": "21"},
                        {"source": "ma", "ma_type": "sma", "period": 60},
                    ],
                },
            }
        ]
    )

    assert conditions == [
        {
            "type": "ma_ordering",
            "params": {
                "timeframe": "1d",
                "items": [
                    {"source": "price"},
                    {"source": "ma", "ma_type": "ema", "period": 21},
                    {"source": "ma", "ma_type": "sma", "period": 60},
                ],
            },
        }
    ]


def test_ma_conditions_support_research_timeframes() -> None:
    registry = get_condition_registry()
    expected = ["1h", "4h", "12h", "1d", "3d", "1w", "1M"]

    ma_alignment = next(condition for condition in registry if condition["id"] == "ma_alignment")
    ma_touch = next(condition for condition in registry if condition["id"] == "ma_touch")

    assert ma_alignment["params_schema"]["timeframe"]["options"] == expected
    assert ma_touch["params_schema"]["timeframe"]["options"] == expected
    assert normalize_entry_conditions(
        [{"type": "ma_touch", "params": {"timeframe": "1d", "period": 21}}]
    )[0]["params"]["timeframe"] == "1d"

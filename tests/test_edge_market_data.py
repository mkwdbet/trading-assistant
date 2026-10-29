from app.services.edge_market_data import normalize_yahoo_symbol


def test_tradingview_nq_continuous_futures_uses_yahoo_futures_symbol() -> None:
    assert normalize_yahoo_symbol("NQ1!") == "NQ=F"
    assert normalize_yahoo_symbol("CME_MINI:NQ1!") == "NQ=F"

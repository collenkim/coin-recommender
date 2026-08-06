"""Pure-pandas reference implementation used ONLY to oracle-test src/features.py's pandas-ta wrapper.
Not used in production code (see nfr-design/logical-components.md, Unit 2)."""
import pandas as pd


def reference_ichimoku(high: pd.Series, low: pd.Series, close: pd.Series, tenkan_n=9, kijun_n=26, senkou_n=52, shift=25):
    tenkan = (high.rolling(tenkan_n).max() + low.rolling(tenkan_n).min()) / 2
    kijun = (high.rolling(kijun_n).max() + low.rolling(kijun_n).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(shift)
    senkou_b_raw = (high.rolling(senkou_n).max() + low.rolling(senkou_n).min()) / 2
    senkou_b = senkou_b_raw.shift(shift)
    return pd.DataFrame({"tenkan": tenkan, "kijun": kijun, "senkou_a": senkou_a, "senkou_b": senkou_b})

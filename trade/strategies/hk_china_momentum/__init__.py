"""BL-B011-S2 HK-China Momentum satellite strategy (price-only).

Public surface mirrors ``us_quality_momentum``: ``generate_signal`` returns a
``SignalResult`` whose ``weights_dict()`` is the sleeve-relative target the
Master dispatch consumes.
"""

from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_momentum.signal import SignalResult, generate_signal

__all__ = ["HkChinaMomentumParameters", "SignalResult", "generate_signal"]

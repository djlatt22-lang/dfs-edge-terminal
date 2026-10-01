from __future__ import annotations

from math import exp
from statistics import NormalDist

NORMAL = NormalDist()


def american_to_implied(odds: float | int | None) -> float | None:
    if odds is None:
        return None
    odds = float(odds)
    if odds == 0:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def devig_two_way(over_price: float | None, under_price: float | None) -> tuple[float, float] | None:
    po = american_to_implied(over_price)
    pu = american_to_implied(under_price)
    if po is None or pu is None or (po + pu) <= 0:
        return None
    total = po + pu
    return po / total, pu / total


def norm_cdf(z: float) -> float:
    return NORMAL.cdf(z)


def norm_ppf(p: float) -> float:
    p = min(max(float(p), 1e-5), 1 - 1e-5)
    return NORMAL.inv_cdf(p)


def sigmoid(x: float) -> float:
    return 1 / (1 + exp(-x))

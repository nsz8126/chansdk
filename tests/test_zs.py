# -*- coding: utf-8 -*-
"""
Layer 6 Tests: chan.zs module
Covers: CZS construction, boundaries (ZG, ZD, GG, DD),
combine modes (zs vs peak), and CZSList creation.
"""

import pytest
from chan.common.enum import BI_DIR, KLINE_DIR, FX_TYPE
from chan.bi.bi import CBi
from chan.kline.kline import CKLine
from chan.zs.zs import CZS
from chan.zs.config import CZSConfig
from tests.conftest import create_klu


def make_mock_bi(idx: int, _dir: BI_DIR, begin_price: float, end_price: float) -> CBi:
    k1 = create_klu(2024, 1, 1, begin_price, max(begin_price, end_price), min(begin_price, end_price), begin_price)
    k2 = create_klu(2024, 1, 5, end_price, max(begin_price, end_price), min(begin_price, end_price), end_price)
    klc1 = CKLine(k1, idx * 5, KLINE_DIR.UP if _dir == BI_DIR.UP else KLINE_DIR.DOWN)
    klc2 = CKLine(k2, idx * 5 + 4, KLINE_DIR.UP if _dir == BI_DIR.UP else KLINE_DIR.DOWN)
    if _dir == BI_DIR.UP:
        klc1.set_fx(FX_TYPE.BOTTOM)
        klc2.set_fx(FX_TYPE.TOP)
    else:
        klc1.set_fx(FX_TYPE.TOP)
        klc2.set_fx(FX_TYPE.BOTTOM)
    return CBi(klc1, klc2, idx=idx, is_sure=True)


class TestCZSConstruction:
    """Tests for Zhongshu interval boundaries and invariants."""

    def test_three_strokes_forming_zs(self):
        """
        Stroke 1 (UP): 10 -> 30
        Stroke 2 (DOWN): 30 -> 15 (overlap with bi1 is [15, 30])
        Stroke 3 (UP): 15 -> 25 (overlap [15, 25])
        Zhongshu boundaries:
        ZG = min(highs) = min(30, 25) = 25 (self.high)
        ZD = max(lows) = max(10, 15) = 15 (self.low)
        GG = max(all highs) = 30 (self.peak_high)
        DD = min(all lows) = 10 (self.peak_low)
        """
        bi1 = make_mock_bi(0, BI_DIR.UP, 10.0, 30.0)
        bi2 = make_mock_bi(1, BI_DIR.DOWN, 30.0, 15.0)
        bi3 = make_mock_bi(2, BI_DIR.UP, 15.0, 25.0)

        zs = CZS([bi1, bi2, bi3])
        assert zs.low == 15.0      # ZD
        assert zs.high == 25.0     # ZG
        assert zs.peak_low == 10.0  # DD
        assert zs.peak_high == 30.0 # GG
        assert zs.mid == 20.0
        assert zs.low < zs.high

    def test_zs_combine_mode_zs(self):
        """Two overlapping Zhongshus combined under 'zs' mode."""
        # ZS 1: [15, 25]
        bi1 = make_mock_bi(0, BI_DIR.UP, 10.0, 30.0)
        bi2 = make_mock_bi(1, BI_DIR.DOWN, 30.0, 15.0)
        bi3 = make_mock_bi(2, BI_DIR.UP, 15.0, 25.0)
        zs1 = CZS([bi1, bi2, bi3])

        # ZS 2: [20, 28] (overlaps with [15, 25] on [20, 25])
        bi4 = make_mock_bi(3, BI_DIR.DOWN, 25.0, 20.0)
        bi5 = make_mock_bi(4, BI_DIR.UP, 20.0, 28.0)
        bi6 = make_mock_bi(5, BI_DIR.DOWN, 28.0, 22.0)
        zs2 = CZS([bi4, bi5, bi6])

        # Combining zs1 and zs2
        res = zs1.combine(zs2, combine_mode="zs")
        assert res is True
        # Combined ZD/ZG in chansdk takes the union: min(low) and max(high)
        assert zs1.low == 15.0
        assert zs1.high == 25.0
        assert zs2 in zs1.sub_zs_lst

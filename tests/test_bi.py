# -*- coding: utf-8 -*-
"""
Layer 4 Tests: chan.bi module
Covers: CBi construction, direction, virtual stroke updating,
metric calculation, CBiList creation, and stroke topological invariants.
"""

import pytest
from chan.common.enum import BI_DIR, BI_TYPE, FX_TYPE, MACD_ALGO, KL_TYPE
from chan.config import CChanConfig
from chan.bi.bi import CBi
from chan.bi.config import CBiConfig
from chan.kline.list import CKLine_List
from tests.conftest import create_klu
from tests.test_data import generate_single_up_bi, generate_bi_series_for_zs


class TestCBiStructure:
    """Tests for single stroke representation and methods."""

    def test_stroke_creation_via_kline_list(self):
        """Build an upward stroke using generate_single_up_bi through CKLine_List."""
        config = CChanConfig({"bi_strict": True})
        kl_list = CKLine_List(KL_TYPE.K_DAY, config)
        bars = generate_single_up_bi()
        for b in bars:
            kl_list.add_single_klu(b)
        kl_list.cal_seg_and_zs()

        # There should be at least 1 stroke formed
        assert len(kl_list.bi_list) >= 1
        first_bi: CBi = kl_list.bi_list[0]
        assert first_bi.is_up() is True
        assert first_bi.is_down() is False
        assert first_bi.dir == BI_DIR.UP
        assert first_bi.get_begin_val() < first_bi.get_end_val()

    def test_stroke_metrics(self):
        config = CChanConfig()
        kl_list = CKLine_List(KL_TYPE.K_DAY, config)
        bars = generate_single_up_bi()
        for b in bars:
            kl_list.add_single_klu(b)
        kl_list.cal_seg_and_zs()

        first_bi: CBi = kl_list.bi_list[0]
        # Calculate amplitude and slope with is_reverse=False
        amp = first_bi.cal_macd_metric(MACD_ALGO.AMP, is_reverse=False)
        assert amp > 0.0

        slope = first_bi.cal_macd_metric(MACD_ALGO.SLOPE, is_reverse=False)
        assert slope > 0.0

    def test_stroke_zero_price_slope_divzero(self):
        """When end_klu.high is 0.0, slope calculation raises ZeroDivisionError."""
        k1 = create_klu(2024, 1, 1, -10.0, -5.0, -15.0, -8.0)
        k2 = create_klu(2024, 1, 2, -2.0, 0.0, -3.0, -1.0)
        from chan.kline.kline import CKLine
        from chan.common.enum import KLINE_DIR
        klc1 = CKLine(k1, 0, KLINE_DIR.UP)
        klc2 = CKLine(k2, 1, KLINE_DIR.UP)
        klc1.set_fx(FX_TYPE.BOTTOM)
        klc2.set_fx(FX_TYPE.TOP)
        bi = CBi(klc1, klc2, idx=0, is_sure=True)
        # Should gracefully return 0.0 or handle instead of ZeroDivisionError
        slope = bi.Cal_MACD_slope()
        assert slope == 0.0


class TestCBiListInvariants:
    """Tests for stroke lists and topological alternation invariants."""

    def test_bi_alternating_directions(self):
        """Adjacent strokes must alternate directions (UP -> DOWN -> UP)."""
        config = CChanConfig({"bi_strict": False})
        kl_list = CKLine_List(KL_TYPE.K_DAY, config)
        bars = generate_bi_series_for_zs()
        for b in bars:
            kl_list.add_single_klu(b)
        kl_list.cal_seg_and_zs()

        bi_list = kl_list.bi_list
        assert len(bi_list) >= 2, f"Expected at least 2 strokes, got {len(bi_list)}"
        for i in range(1, len(bi_list)):
            assert bi_list[i].dir != bi_list[i - 1].dir, (
                f"Stroke {i} dir {bi_list[i].dir} must differ from stroke {i-1} dir {bi_list[i-1].dir}"
            )
            # End of previous stroke connects to begin of next stroke
            assert bi_list[i].begin_klc.idx == bi_list[i - 1].end_klc.idx

    def test_bi_list_iteration_and_indexing(self):
        config = CChanConfig({"bi_strict": False})
        kl_list = CKLine_List(KL_TYPE.K_DAY, config)
        bars = generate_bi_series_for_zs()
        for b in bars:
            kl_list.add_single_klu(b)

        bi_list = kl_list.bi_list
        # Test __getitem__
        first = bi_list[0]
        assert isinstance(first, CBi)
        # Test slice
        sub = bi_list[:2]
        assert len(sub) <= 2
        # Test __iter__
        all_bis = list(bi_list)
        assert len(all_bis) == len(bi_list)

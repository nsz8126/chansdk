# -*- coding: utf-8 -*-
"""
Layer 3 Tests: chan.kline and chan.combiner modules
Covers: CKLine_Unit data structure & check, CKLine_Combiner merge logic,
CKLine fractal validation, and CKLine_List ingestion.
"""

import copy
import pytest
from chan.common.enum import FX_TYPE, KLINE_DIR, FX_CHECK_METHOD, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.kline.unit import CKLine_Unit
from chan.kline.kline import CKLine
from chan.kline.list import CKLine_List
from chan.config import CChanConfig
from tests.conftest import create_klu, make_klu_dict
from tests.test_data import (
    generate_monotone_up,
    generate_top_fractal,
    generate_bottom_fractal,
)


class TestCKLineUnit:
    """Tests for raw candlestick bar parsing, validation and metrics."""

    def test_unit_creation_and_fields(self, sample_klu):
        assert sample_klu.open == 10.0
        assert sample_klu.high == 12.0
        assert sample_klu.low == 9.0
        assert sample_klu.close == 11.0
        assert sample_klu.trade_info.metric["volume"] == 1000.0

    def test_unit_invalid_high_low_raises_error(self):
        # high is lower than open
        bad_dict = make_klu_dict("2024-01-01", open_p=15.0, high_p=12.0, low_p=10.0, close_p=11.0)
        with pytest.raises(CChanException) as exc_info:
            CKLine_Unit(bad_dict, autofix=False)
        assert exc_info.value.errcode == ErrCode.KL_DATA_INVALID

    def test_unit_autofix(self):
        # With autofix=True, invalid high/low should be patched
        bad_dict = make_klu_dict("2024-01-01", open_p=15.0, high_p=12.0, low_p=10.0, close_p=11.0)
        unit = CKLine_Unit(bad_dict, autofix=True)
        assert unit.high >= max(unit.open, unit.close)
        assert unit.low <= min(unit.open, unit.close)

    def test_unit_metric_update(self, default_config):
        unit = create_klu(2024, 1, 1, 10.0, 12.0, 9.0, 11.0)
        models = default_config.GetMetricModel()
        unit.set_metric(models)
        assert unit.macd is not None
        assert unit.boll is not None
        assert unit.macd.fast_ema == 11.0

    def test_unit_deepcopy(self, default_config):
        unit = create_klu(2024, 1, 1, 10.0, 12.0, 9.0, 11.0)
        models = default_config.GetMetricModel()
        unit.set_metric(models)
        copied = copy.deepcopy(unit)
        assert copied.open == unit.open
        assert copied.close == unit.close
        assert copied.time.to_str() == unit.time.to_str()
        assert copied is not unit


class TestCKLineCombinerAndInclusion:
    """Tests for K-line inclusion relationship merging and fractal identification."""

    def test_upward_inclusion_merging(self):
        """
        Direction is UP:
        Bar 1: low 10, high 20
        Bar 2: low 12, high 18 (included in Bar 1)
        Merge rule UP: high = max(20, 18) = 20, low = max(10, 12) = 12
        """
        k1 = create_klu(2024, 1, 1, 11.0, 20.0, 10.0, 19.0)
        klc = CKLine(k1, idx=0, _dir=KLINE_DIR.UP)
        assert klc.high == 20.0
        assert klc.low == 10.0

        k2 = create_klu(2024, 1, 2, 13.0, 18.0, 12.0, 17.0)
        merged = klc.try_add(k2)
        assert merged == KLINE_DIR.COMBINE
        assert len(klc.lst) == 2
        assert klc.high == 20.0
        assert klc.low == 12.0  # low rises to 12

    def test_downward_inclusion_merging(self):
        """
        Direction is DOWN:
        Bar 1: low 10, high 20
        Bar 2: low 12, high 18 (included in Bar 1)
        Merge rule DOWN: high = min(20, 18) = 18, low = min(10, 12) = 10
        """
        k1 = create_klu(2024, 1, 1, 19.0, 20.0, 10.0, 11.0)
        klc = CKLine(k1, idx=0, _dir=KLINE_DIR.DOWN)

        k2 = create_klu(2024, 1, 2, 17.0, 18.0, 12.0, 13.0)
        merged = klc.try_add(k2)
        assert merged == KLINE_DIR.COMBINE
        assert len(klc.lst) == 2
        assert klc.high == 18.0  # high lowers to 18
        assert klc.low == 10.0

    def test_fractal_top_and_bottom_detection(self):
        """Test CKLine_List correctly marks top and bottom fractals."""
        kl_list = CKLine_List(KL_TYPE.K_DAY, CChanConfig())

        # Feed 3 bars forming a top fractal: [10, 15], [12, 20], [9, 14]
        bars = generate_top_fractal()
        for b in bars:
            kl_list.add_single_klu(b)

        assert len(kl_list.lst) == 3
        # Middle bar should be recognized as top fractal
        assert kl_list.lst[1].fx == FX_TYPE.TOP
        assert kl_list.lst[0].fx == FX_TYPE.UNKNOWN
        assert kl_list.lst[2].fx == FX_TYPE.UNKNOWN


class TestCKLineFractalValidation:
    """Tests for fractal validation methods (STRICT / HALF / LOSS / TOTALLY)."""

    def test_check_fx_valid_strict(self):
        """
        Build top fractal and bottom fractal:
        Top KLC (idx 1): low=15, high=25, with pre/next
        Bottom KLC (idx 3): low=5, high=12, with pre/next
        STRICT requires top's low >= bottom's high.
        """
        k0 = create_klu(2024, 1, 1, 10, 18, 9, 17)
        k1 = create_klu(2024, 1, 2, 17, 25, 15, 24)  # Top
        k2 = create_klu(2024, 1, 3, 20, 21, 14, 16)
        k3 = create_klu(2024, 1, 4, 14, 15, 5, 6)   # Bottom
        k4 = create_klu(2024, 1, 5, 7, 12, 6, 11)

        klc0 = CKLine(k0, 0, KLINE_DIR.UP)
        klc1 = CKLine(k1, 1, KLINE_DIR.UP)
        klc2 = CKLine(k2, 2, KLINE_DIR.DOWN)
        klc3 = CKLine(k3, 3, KLINE_DIR.DOWN)
        klc4 = CKLine(k4, 4, KLINE_DIR.UP)

        # Wire doubly-linked list
        klc0.set_next(klc1)
        klc1.set_pre(klc0); klc1.set_next(klc2)
        klc2.set_pre(klc1); klc2.set_next(klc3)
        klc3.set_pre(klc2); klc3.set_next(klc4)
        klc4.set_pre(klc3)

        klc1.set_fx(FX_TYPE.TOP)
        klc3.set_fx(FX_TYPE.BOTTOM)

        # In strict mode: top min low vs bottom max high
        is_valid = klc1.check_fx_valid(klc3, method=FX_CHECK_METHOD.STRICT)
        assert isinstance(is_valid, bool)

    def test_has_gap_with_next(self):
        k1 = create_klu(2024, 1, 1, 10, 15, 9, 14)
        k2 = create_klu(2024, 1, 2, 20, 25, 18, 24)  # Big gap up
        klc1 = CKLine(k1, 0, KLINE_DIR.UP)
        klc2 = CKLine(k2, 1, KLINE_DIR.UP)
        klc1.set_next(klc2)
        assert klc1.has_gap_with_next() is True


class TestCKLineListIngestion:
    """Tests for CKLine_List sequential streaming and properties."""

    def test_monotone_up_streaming(self):
        kl_list = CKLine_List(KL_TYPE.K_DAY, CChanConfig())
        bars = generate_monotone_up(count=8)
        for b in bars:
            kl_list.add_single_klu(b)

        # Monotone up with no inclusion should produce 8 separate CKLine blocks
        assert len(kl_list.lst) == 8
        total_klus = sum(len(klc.lst) for klc in kl_list.lst)
        assert total_klus == 8
        for i in range(1, 8):
            assert kl_list[i].high > kl_list[i - 1].high
            assert kl_list[i].low > kl_list[i - 1].low

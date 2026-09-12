# -*- coding: utf-8 -*-
"""
Layer 1 Tests: chan.common module
Covers: CTime, Enum, Exception, Cache decorator, and Util functions.
"""

import pytest
from chan.common.time import CTime
from chan.common.enum import (
    DATA_SRC, KL_TYPE, KLINE_DIR, FX_TYPE, BI_DIR, BI_TYPE,
    BSP_TYPE, AUTYPE, TREND_TYPE, TREND_LINE_SIDE, LEFT_SEG_METHOD,
    FX_CHECK_METHOD, SEG_TYPE, MACD_ALGO
)
from chan.common.exception import CChanException, ErrCode
from chan.common.cache import make_cache
from chan.common.util import (
    kltype_lt_day, kltype_lte_day, check_kltype_order,
    revert_bi_dir, has_overlap, str2float, _parse_inf
)


class TestCTime:
    """Tests for CTime representation, formatting, comparison and auto-adjustment."""

    def test_ctime_daily_formatting(self):
        t = CTime(2024, 5, 20, 0, 0)
        assert str(t) == "2024/05/20"
        assert t.to_str() == "2024/05/20"
        assert t.toDateStr() == "20240520"
        assert t.toDateStr(splt="/") == "2024/05/20"

    def test_ctime_minute_formatting(self):
        t = CTime(2024, 5, 20, 9, 30)
        assert str(t) == "2024/05/20 09:30"
        assert t.to_str() == "2024/05/20 09:30"

    def test_ctime_auto_daily_timestamp_adjustment(self):
        """When hour=0 and minute=0 with auto=True, timestamp is adjusted to 23:59:00."""
        t_daily = CTime(2024, 5, 20, 0, 0, auto=True)
        t_min = CTime(2024, 5, 20, 15, 0)
        # Daily bar timestamp should be numerically greater than 15:00 intraday bar of the same day
        assert t_daily.ts > t_min.ts

    def test_ctime_no_auto_timestamp(self):
        """When auto=False, hour=0 stays at 00:00:00."""
        t1 = CTime(2024, 5, 20, 0, 0, auto=False)
        t2 = CTime(2024, 5, 20, 1, 0)
        assert t2.ts > t1.ts

    def test_ctime_comparisons_gt_ge(self):
        t1 = CTime(2024, 1, 1, 10, 0)
        t2 = CTime(2024, 1, 1, 11, 0)
        assert t2 > t1
        assert t2 >= t1
        assert not (t1 > t2)
        assert not (t1 >= t2)

    def test_ctime_todate(self):
        t = CTime(2024, 3, 15, 14, 30)
        dt = t.toDate()
        assert dt.year == 2024
        assert dt.month == 3
        assert dt.day == 15
        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.auto is False

    def test_ctime_equality(self):
        t1 = CTime(2024, 1, 1, 10, 0)
        t2 = CTime(2024, 1, 1, 10, 0)
        # Two distinct instances representing the exact same time
        assert t1 == t2


class TestEnums:
    """Tests for Chan enum integrity, value ranges and uniqueness."""

    def test_data_src_enum(self):
        assert isinstance(DATA_SRC.CSV.value, int)
        assert DATA_SRC.CSV.name == "CSV"
        assert DATA_SRC.ELTDX.name == "ELTDX"
        assert DATA_SRC.CACHE_DB.name == "CACHE_DB"

    def test_kl_type_enum(self):
        assert isinstance(KL_TYPE.K_1M.value, int)
        assert KL_TYPE.K_1M.name == "K_1M"
        assert KL_TYPE.K_DAY.name == "K_DAY"
        assert KL_TYPE.K_WEEK.name == "K_WEEK"

    def test_bsp_type_enum(self):
        assert BSP_TYPE.T1.value == "1"
        assert BSP_TYPE.T1P.value == "1p"
        assert BSP_TYPE.T2.value == "2"
        assert BSP_TYPE.T2S.value == "2s"
        assert BSP_TYPE.T3A.value == "3a"
        assert BSP_TYPE.T3B.value == "3b"
        assert BSP_TYPE.T1.main_type() == "1"
        assert BSP_TYPE.T2S.main_type() == "2"
        assert BSP_TYPE.T3A.main_type() == "3"

    def test_bi_dir_enum(self):
        assert BI_DIR.UP.name == "UP"
        assert BI_DIR.DOWN.name == "DOWN"
        assert BI_DIR.UP != BI_DIR.DOWN

    def test_fx_type_enum(self):
        assert FX_TYPE.BOTTOM.name == "BOTTOM"
        assert FX_TYPE.TOP.name == "TOP"
        assert FX_TYPE.UNKNOWN.name == "UNKNOWN"


class TestExceptions:
    """Tests for CChanException and ErrCode categorization."""

    def test_chan_internal_err(self):
        e = CChanException("Test Chan error", ErrCode.BI_ERR)
        assert e.is_chan_err()
        assert not e.is_kldata_err()
        assert e.errcode == ErrCode.BI_ERR
        assert "Test Chan error" in str(e)

    def test_kldata_err(self):
        e = CChanException("Data missing", ErrCode.KL_DATA_INVALID)
        assert e.is_kldata_err()
        assert not e.is_chan_err()

    def test_trade_err(self):
        e = CChanException("Trade error", ErrCode.SIGNAL_EXISTED)
        assert not e.is_kldata_err()
        assert not e.is_chan_err()


class TestCacheDecorator:
    """Tests for make_cache instance-level caching decorator."""

    class MockItem:
        def __init__(self):
            self.calc_count = 0
            self._memoize_cache = {}

        @make_cache
        def expensive_calc(self):
            self.calc_count += 1
            return 42

        def clean_cache(self):
            self._memoize_cache = {}

    def test_cache_hits_and_invalidation(self):
        item = self.MockItem()
        assert item.expensive_calc() == 42
        assert item.calc_count == 1
        # Second access hits cache
        assert item.expensive_calc() == 42
        assert item.calc_count == 1

        # Clear cache and verify re-calculation
        item.clean_cache()
        assert item.expensive_calc() == 42
        assert item.calc_count == 2

    def test_cache_instance_isolation(self):
        item1 = self.MockItem()
        item2 = self.MockItem()
        assert item1.expensive_calc() == 42
        assert item1.calc_count == 1
        assert item2.calc_count == 0
        assert item2.expensive_calc() == 42
        assert item2.calc_count == 1


class TestUtils:
    """Tests for utility functions in chan.common.util."""

    def test_kltype_lt_day(self):
        assert kltype_lt_day(KL_TYPE.K_1M) is True
        assert kltype_lt_day(KL_TYPE.K_60M) is True
        assert kltype_lt_day(KL_TYPE.K_DAY) is False
        assert kltype_lt_day(KL_TYPE.K_WEEK) is False

    def test_kltype_lte_day(self):
        assert kltype_lte_day(KL_TYPE.K_60M) is True
        assert kltype_lte_day(KL_TYPE.K_DAY) is True
        assert kltype_lte_day(KL_TYPE.K_WEEK) is False

    def test_check_kltype_order(self):
        # Valid descending order: Day -> 60M -> 5M
        check_kltype_order([KL_TYPE.K_DAY, KL_TYPE.K_60M, KL_TYPE.K_5M])
        # Invalid order should raise AssertionError
        with pytest.raises(AssertionError):
            check_kltype_order([KL_TYPE.K_5M, KL_TYPE.K_DAY])

    def test_revert_bi_dir(self):
        assert revert_bi_dir(BI_DIR.UP) == BI_DIR.DOWN
        assert revert_bi_dir(BI_DIR.DOWN) == BI_DIR.UP

    def test_has_overlap(self):
        # Overlapping ranges [10, 20] and [15, 25]
        assert has_overlap(10, 20, 15, 25) is True
        # Non-overlapping ranges [10, 20] and [25, 35]
        assert has_overlap(10, 20, 25, 35) is False
        # Border touching [10, 20] and [20, 30]
        assert has_overlap(10, 20, 20, 30, equal=False) is False
        assert has_overlap(10, 20, 20, 30, equal=True) is True

    def test_str2float(self):
        assert str2float("3.14") == pytest.approx(3.14)
        assert str2float("invalid") == 0.0
        assert str2float("") == 0.0

    def test_parse_inf(self):
        assert _parse_inf(float("inf")) == 'float("inf")'
        assert _parse_inf(float("-inf")) == 'float("-inf")'
        assert _parse_inf(123) == 123

# -*- coding: utf-8 -*-
"""
Layer 2 Tests: chan.math module
Covers: MACD, BOLL, KDJ, RSI, DeMark, TrendModel, and TrendLine algorithms.
"""

import math
import pytest
from chan.math.macd import CMACD, CMACD_item
from chan.math.boll import BollModel, BOLL_Metric
from chan.math.kdj import KDJ, KDJ_Item
from chan.math.rsi import RSI
from chan.math.demark import CDemarkEngine
from chan.math.trend_model import CTrendModel
from chan.math.trend_line import Point, Line
from chan.common.enum import TREND_TYPE


class TestMACD:
    """Tests for Exponential Moving Average and MACD calculations."""

    def test_macd_initial_bar(self):
        macd = CMACD(fastperiod=12, slowperiod=26, signalperiod=9)
        item = macd.add(10.0)
        assert item.fast_ema == 10.0
        assert item.slow_ema == 10.0
        assert item.DIF == 0.0
        assert item.DEA == 0.0
        assert item.macd == 0.0

    def test_macd_constant_prices(self):
        macd = CMACD()
        for _ in range(30):
            item = macd.add(50.0)
        # Constant prices must result in zero DIF, DEA, and MACD
        assert pytest.approx(item.fast_ema, abs=1e-5) == 50.0
        assert pytest.approx(item.slow_ema, abs=1e-5) == 50.0
        assert pytest.approx(item.DIF, abs=1e-5) == 0.0
        assert pytest.approx(item.DEA, abs=1e-5) == 0.0
        assert pytest.approx(item.macd, abs=1e-5) == 0.0

    def test_macd_trending_up(self):
        macd = CMACD()
        for p in range(10, 30):
            item = macd.add(float(p))
        # When trending up, fast EMA > slow EMA, so DIF > 0
        assert item.fast_ema > item.slow_ema
        assert item.DIF > 0.0
        assert item.DEA > 0.0

    def test_macd_trending_down(self):
        macd = CMACD()
        for p in range(30, 10, -1):
            item = macd.add(float(p))
        # When trending down, fast EMA < slow EMA, so DIF < 0
        assert item.fast_ema < item.slow_ema
        assert item.DIF < 0.0
        assert item.DEA < 0.0


class TestBOLL:
    """Tests for Bollinger Bands calculation and sliding window."""

    def test_boll_window_and_constant_price(self):
        boll = BollModel(N=20)
        for _ in range(25):
            metric = boll.add(100.0)
        assert len(boll.arr) == 20
        assert metric.MID == 100.0
        # Standard deviation for constant is 0; truncated to 1e-7
        assert metric.theta == pytest.approx(1e-7)
        assert pytest.approx(metric.UP, abs=1e-5) == 100.0

    def test_boll_calculation_known_values(self):
        boll = BollModel(N=4)
        # Add 4 values: 10, 20, 30, 40 -> mean = 25
        # sum of sq diffs = (15^2 + 5^2 + 5^2 + 15^2) = 225 + 25 + 25 + 225 = 500
        # var = 500 / 4 = 125, std = sqrt(125) ~= 11.1803
        for v in [10.0, 20.0, 30.0, 40.0]:
            metric = boll.add(v)
        expected_ma = 25.0
        expected_std = math.sqrt(125.0)
        assert metric.MID == pytest.approx(expected_ma)
        assert metric.theta == pytest.approx(expected_std)
        assert metric.UP == pytest.approx(expected_ma + 2 * expected_std)
        assert metric.DOWN == pytest.approx(expected_ma - 2 * expected_std)


class TestKDJ:
    """Tests for KDJ indicator."""

    def test_kdj_initial_values(self):
        kdj = KDJ(period=9)
        # First bar
        item = kdj.add(high=12.0, low=8.0, close=10.0)
        # rsv = (10 - 8) / (12 - 8) * 100 = 50
        # k = 2/3 * 50 + 1/3 * 50 = 50
        # d = 2/3 * 50 + 1/3 * 50 = 50
        # j = 3*50 - 2*50 = 50
        assert pytest.approx(item.k) == 50.0
        assert pytest.approx(item.d) == 50.0
        assert pytest.approx(item.j) == 50.0

    def test_kdj_bullish_progression(self):
        kdj = KDJ(period=9)
        for i in range(10):
            item = kdj.add(high=10.0 + i, low=9.0 + i, close=10.0 + i)
        # Consecutive new highs push RSV to 100
        assert item.k > 80.0
        assert item.j > item.k


class TestRSI:
    """Tests for RSI Wilder smoothing indicator."""

    def test_rsi_first_bar(self):
        rsi = RSI(period=14)
        val = rsi.add(100.0)
        assert val == 50.0

    def test_rsi_monotone_up(self):
        rsi = RSI(period=14)
        for p in range(100, 130):
            val = rsi.add(float(p))
        # Strictly increasing prices -> 100 RSI
        assert pytest.approx(val) == 100.0

    def test_rsi_monotone_down(self):
        rsi = RSI(period=14)
        for p in range(130, 100, -1):
            val = rsi.add(float(p))
        # Strictly decreasing prices -> 0 RSI
        assert pytest.approx(val) == 0.0


class TestTrendModel:
    """Tests for CTrendModel rolling aggregations."""

    def test_trend_mean(self):
        model = CTrendModel(TREND_TYPE.MEAN, T=3)
        res1 = model.add(10.0)
        res2 = model.add(20.0)
        res3 = model.add(30.0)
        assert res1 == 10.0
        assert res2 == 15.0
        assert res3 == 20.0
        # Window slides
        res4 = model.add(40.0)
        assert res4 == 30.0  # (20 + 30 + 40) / 3

    def test_trend_max_and_min(self):
        max_model = CTrendModel(TREND_TYPE.MAX, T=3)
        min_model = CTrendModel(TREND_TYPE.MIN, T=3)
        for v in [10.0, 50.0, 20.0]:
            mx = max_model.add(v)
            mn = min_model.add(v)
        assert mx == 50.0
        assert mn == 10.0
        # Push 30: window is [50, 20, 30]
        assert max_model.add(30.0) == 50.0
        assert min_model.add(30.0) == 20.0


class TestTrendLine:
    """Tests for Point, Line, and geometry calculations."""

    def test_point_slope(self):
        p1 = Point(0, 0.0)
        p2 = Point(2, 4.0)
        assert p1.cal_slope(p2) == 2.0

    def test_line_distance(self):
        p0 = Point(0, 0.0)
        line = Line(p=p0, slope=0.0)  # y = 0
        p = Point(5, 3.0)
        assert pytest.approx(line.cal_dis(p)) == 3.0

    def test_vertical_line_dis_not_nan(self):
        p1 = Point(1, 2.0)
        p2 = Point(1, 5.0)
        slope = p1.cal_slope(p2)
        assert math.isinf(slope)
        line = Line(p=p1, slope=slope)
        dis = line.cal_dis(Point(3, 2.0))
        # Distance between x=1 and x=3 should be 2.0, not NaN
        assert not math.isnan(dis)
        assert pytest.approx(dis) == 2.0


class TestDeMarkConcurrencyDefect:
    """Tests DeMark engine behavior and class-variable mutation defect."""

    def test_demark_instance_isolation(self):
        e1 = CDemarkEngine(demark_len=9)
        e2 = CDemarkEngine(demark_len=5)
        assert getattr(e1, 'demark_len', None) == 9
        assert getattr(e2, 'demark_len', None) == 5

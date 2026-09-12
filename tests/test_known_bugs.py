# -*- coding: utf-8 -*-
"""Regression tests for defects found during gray testing."""

import math

import pytest

from chan.bi.bi import CBi
from chan.bsp.config import CPointConfig
from chan.chan import CChan
from chan.common.enum import DATA_SRC, FX_TYPE, KLINE_DIR, KL_TYPE, MACD_ALGO
from chan.common.exception import CChanException, ErrCode
from chan.common.time import CTime
from chan.config import CChanConfig
from chan.kline.kline import CKLine
from chan.math.demark import CDemarkEngine
from chan.math.trend_line import Line, Point
from tests.conftest import InMemoryStockApi, create_klu
from tests.test_data import generate_monotone_up


class TestKnownDefects:
    def test_alignment_mismatch_raises_domain_error(self, monkeypatch):
        monkeypatch.setattr(CChan, "GetStockAPI", lambda self: InMemoryStockApi)
        code = "DEFECT1"
        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, generate_monotone_up(count=2))
        InMemoryStockApi.register_data(code, KL_TYPE.K_60M, [])

        config = CChanConfig({
            "kl_data_check": True,
            "print_warning": False,
            "max_kl_misalgin_cnt": 1,
        })
        with pytest.raises(CChanException) as exc_info:
            CChan(
                code=code,
                data_src=DATA_SRC.CSV,
                lv_list=[KL_TYPE.K_DAY, KL_TYPE.K_60M],
                config=config,
            )
        assert exc_info.value.errcode == ErrCode.KL_DATA_NOT_ALIGN

    def test_bsp_config_parameter_is_applied_without_exec(self):
        config = CChanConfig()
        config.set_bsp_config({"divergence_rate": 0.5})
        assert config.bs_point_conf.b_conf.divergence_rate == 0.5
        assert config.bs_point_conf.s_conf.divergence_rate == 0.5

    def test_turnrate_avg_enum_mapping(self):
        args = {
            "divergence_rate": float("inf"),
            "min_zs_cnt": 1,
            "bsp1_only_multibi_zs": True,
            "max_bs2_rate": 0.9999,
            "macd_algo": "peak",
            "bs1_peak": True,
            "bs_type": "1",
            "bsp2_follow_1": True,
            "bsp3_follow_1": True,
            "bsp3_peak": False,
            "bsp2s_follow_2": False,
            "max_bsp2s_lv": None,
            "strict_bsp3": False,
            "bsp3a_max_zs_cnt": 1,
        }
        config = CPointConfig(**args)
        config.SetMacdAlgo("turnrate_avg")
        assert config.macd_algo == MACD_ALGO.TURNRATE_AVG

    def test_demark_instance_isolation(self):
        first = CDemarkEngine(demark_len=9)
        second = CDemarkEngine(demark_len=5)
        assert first.demark_len == 9
        assert second.demark_len == 5

    def test_ctime_equality(self):
        assert CTime(2024, 6, 1, 10, 30) == CTime(2024, 6, 1, 10, 30)

    def test_vertical_trendline_distance(self):
        first = Point(5, 10.0)
        second = Point(5, 20.0)
        line = Line(p=first, slope=first.cal_slope(second))
        distance = line.cal_dis(Point(8, 15.0))
        assert not math.isnan(distance)
        assert distance == pytest.approx(3.0)

    def test_bi_slope_zero_price_is_finite(self):
        first = CKLine(
            create_klu(2024, 1, 1, -10.0, -5.0, -15.0, -8.0),
            0,
            KLINE_DIR.UP,
        )
        second = CKLine(
            create_klu(2024, 1, 2, -2.0, 0.0, -3.0, -1.0),
            1,
            KLINE_DIR.UP,
        )
        first.set_fx(FX_TYPE.BOTTOM)
        second.set_fx(FX_TYPE.TOP)
        bi = CBi(first, second, idx=0, is_sure=True)
        assert bi.Cal_MACD_slope() == 0.0


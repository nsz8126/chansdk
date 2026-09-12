# -*- coding: utf-8 -*-
"""
Layer 6 Tests: chan.bsp module
Covers: CBSPointConfig, CPointConfig, CBS_Point,
and buy/sell point type identification.
"""

import pytest
from chan.common.enum import BSP_TYPE, MACD_ALGO
from chan.bsp.config import CBSPointConfig, CPointConfig
from chan.bsp.point import CBS_Point


def get_default_point_args():
    return {
        "divergence_rate": float("inf"),
        "min_zs_cnt": 1,
        "bsp1_only_multibi_zs": True,
        "max_bs2_rate": 0.9999,
        "macd_algo": "peak",
        "bs1_peak": True,
        "bs_type": "1,1p,2,2s,3a,3b",
        "bsp2_follow_1": True,
        "bsp3_follow_1": True,
        "bsp3_peak": False,
        "bsp2s_follow_2": False,
        "max_bsp2s_lv": None,
        "strict_bsp3": False,
        "bsp3a_max_zs_cnt": 1,
    }


class TestBSPConfig:
    """Tests for buy/sell point configurations and parameter mappings."""

    def test_default_bsp_config(self):
        args = get_default_point_args()
        conf = CBSPointConfig(**args)
        assert conf.b_conf is not None
        assert conf.s_conf is not None
        assert conf.b_conf.divergence_rate == float("inf")
        assert conf.b_conf.min_zs_cnt == 1

    def test_target_type_parsing(self):
        args = get_default_point_args()
        args["bs_type"] = "1,2,3a"
        conf = CPointConfig(**args)
        conf.parse_target_type()
        assert BSP_TYPE.T1 in conf.target_types
        assert BSP_TYPE.T2 in conf.target_types
        assert BSP_TYPE.T3A in conf.target_types
        assert BSP_TYPE.T1P not in conf.target_types
        assert BSP_TYPE.T3B not in conf.target_types

    def test_turnrate_avg_mapping_defect(self):
        args = get_default_point_args()
        conf = CPointConfig(**args)
        conf.SetMacdAlgo("turnrate_avg")
        # Should be MACD_ALGO.TURNRATE_AVG, but currently AMOUNT_AVG
        assert conf.macd_algo == MACD_ALGO.TURNRATE_AVG


class TestCBSPoint:
    """Tests for CBS_Point entity properties."""

    def test_bsp_initialization(self):
        from tests.conftest import create_klu
        from chan.kline.kline import CKLine
        from chan.bi.bi import CBi
        from chan.common.enum import KLINE_DIR, FX_TYPE

        k1 = create_klu(2024, 1, 1, 10.0, 12.0, 9.0, 11.0)
        k2 = create_klu(2024, 1, 5, 20.0, 22.0, 19.0, 21.0)
        klc1 = CKLine(k1, 0, KLINE_DIR.UP); klc1.set_fx(FX_TYPE.BOTTOM)
        klc2 = CKLine(k2, 4, KLINE_DIR.UP); klc2.set_fx(FX_TYPE.TOP)
        bi = CBi(klc1, klc2, idx=0, is_sure=True)

        bsp = CBS_Point(bi=bi, is_buy=True, bs_type=BSP_TYPE.T1, relate_bsp1=None)
        assert bsp.is_buy is True
        assert BSP_TYPE.T1 in bsp.type
        assert bsp.klu == bi.get_end_klu()
        assert "1" in str(bsp)
        assert bsp.type2str() == "1"

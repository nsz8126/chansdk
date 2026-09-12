# -*- coding: utf-8 -*-
"""
Layer 1 Tests: chan.config module
Covers: CChanConfig, ConfigWithCheck, parameter parsing, and Metric Model generation.
"""

import pytest
from chan.config import CChanConfig, ConfigWithCheck
from chan.bi.config import CBiConfig
from chan.bsp.config import CBSPointConfig
from chan.common.enum import TREND_TYPE, FX_CHECK_METHOD, LEFT_SEG_METHOD
from chan.common.exception import CChanException, ErrCode
from chan.math.macd import CMACD
from chan.math.boll import BollModel
from chan.math.demark import CDemarkEngine
from chan.math.rsi import RSI
from chan.math.kdj import KDJ
from chan.math.trend_model import CTrendModel


class TestCChanConfig:
    """Tests for default and custom configuration initialization."""

    def test_default_config_initialization(self):
        config = CChanConfig()
        assert config.bi_conf is not None
        assert config.bi_conf.bi_algo == "normal"
        assert config.bi_conf.is_strict is True
        assert config.bi_conf.bi_fx_check == FX_CHECK_METHOD.STRICT

        assert config.seg_conf is not None
        assert config.seg_conf.seg_algo == "chan"
        assert config.seg_conf.left_method == LEFT_SEG_METHOD.PEAK

        assert config.zs_conf is not None
        assert config.zs_conf.need_combine is True
        assert config.zs_conf.zs_combine_mode == "zs"

        assert config.trigger_step is False
        assert config.skip_step == 0
        assert config.kl_data_check is True

    def test_custom_bi_and_seg_config(self):
        conf_dict = {
            "bi_algo": "fx",
            "bi_strict": False,
            "seg_algo": "chan",
            "left_seg_method": "all",
            "zs_combine": False,
        }
        config = CChanConfig(conf_dict)
        assert config.bi_conf.bi_algo == "fx"
        assert config.bi_conf.is_strict is False
        assert config.seg_conf.left_method == LEFT_SEG_METHOD.ALL
        assert config.zs_conf.need_combine is False

    def test_unknown_parameter_rejection(self):
        conf_dict = {"unknown_key_xyz": 123}
        with pytest.raises(CChanException) as exc_info:
            CChanConfig(conf_dict)
        assert exc_info.value.errcode == ErrCode.PARA_ERROR
        assert "unknown_key_xyz" in str(exc_info.value)

    def test_metric_models_generation_default(self):
        config = CChanConfig()
        models = config.GetMetricModel()
        # By default: 1 CMACD and 1 BollModel
        types = [type(m) for m in models]
        assert CMACD in types
        assert BollModel in types
        assert RSI not in types
        assert KDJ not in types
        assert CDemarkEngine not in types

    def test_metric_models_generation_full(self):
        conf_dict = {
            "mean_metrics": [5, 10],
            "trend_metrics": [20],
            "cal_demark": True,
            "cal_rsi": True,
            "cal_kdj": True,
        }
        config = CChanConfig(conf_dict)
        models = config.GetMetricModel()
        types = [type(m) for m in models]

        assert CMACD in types
        assert BollModel in types
        assert RSI in types
        assert KDJ in types
        assert CDemarkEngine in types
        assert CTrendModel in types

        # Check count of CTrendModel: 2 from mean_metrics + 2 from trend_metrics (max + min) = 4
        trend_models = [m for m in models if isinstance(m, CTrendModel)]
        assert len(trend_models) == 4

    def test_bsp_custom_buy_sell_overrides(self):
        conf_dict = {
            "divergence_rate-buy": 0.8,
            "divergence_rate-sell": 0.6,
            "min_zs_cnt-buy": 2,
        }
        config = CChanConfig(conf_dict)
        assert config.bs_point_conf.b_conf.divergence_rate == 0.8
        assert config.bs_point_conf.s_conf.divergence_rate == 0.6
        assert config.bs_point_conf.b_conf.min_zs_cnt == 2


class TestConfigWithCheck:
    """Tests for ConfigWithCheck dictionary consumer wrapper."""

    def test_get_and_consumption(self):
        raw = {"a": 1, "b": 2}
        checker = ConfigWithCheck(raw)
        assert checker.get("a") == 1
        assert "a" not in checker.conf
        assert checker.get("c", default_value=99) == 99

    def test_check_passes_when_empty(self):
        raw = {"a": 1}
        checker = ConfigWithCheck(raw)
        checker.get("a")
        checker.check()  # Should not raise

    def test_check_raises_when_keys_remain(self):
        raw = {"leftover": "value"}
        checker = ConfigWithCheck(raw)
        with pytest.raises(CChanException) as exc_info:
            checker.check()
        assert exc_info.value.errcode == ErrCode.PARA_ERROR
        assert "leftover" in str(exc_info.value)

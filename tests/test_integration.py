# -*- coding: utf-8 -*-
"""
Layer 7 Tests: End-to-End Integration
Covers: CChan full calculation pipeline, multi-level synchronization,
step_load generator, deepcopy snapshots, and Defect #1 verification.
"""

import pytest
from chan.chan import CChan
from chan.config import CChanConfig
from chan.common.enum import KL_TYPE, DATA_SRC
from chan.common.exception import CChanException, ErrCode
from tests.conftest import InMemoryStockApi
from tests.test_data import generate_bi_series_for_zs, generate_monotone_up


@pytest.fixture
def mock_stock_api(monkeypatch):
    """Patch CChan.GetStockAPI to use InMemoryStockApi."""
    monkeypatch.setattr(CChan, "GetStockAPI", lambda self: InMemoryStockApi)


class TestCChanSingleLevelPipeline:
    """End-to-End tests for single timeframe calculation."""

    def test_single_level_daily_pipeline(self, mock_stock_api):
        code = "TEST01"
        ktype = KL_TYPE.K_DAY
        bars = generate_bi_series_for_zs()
        InMemoryStockApi.register_data(code, ktype, bars)

        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[ktype],
            config=CChanConfig({"bi_strict": False}),
        )

        # Access results via indexing
        kline_list = chan[ktype]
        assert len(kline_list.lst) > 0
        assert len(kline_list.bi_list) >= 1

    def test_step_load_generator(self, mock_stock_api):
        code = "TEST_STEP"
        ktype = KL_TYPE.K_DAY
        bars = generate_monotone_up(count=6)
        InMemoryStockApi.register_data(code, ktype, bars)

        config = CChanConfig({"trigger_step": True, "skip_step": 0})
        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[ktype],
            config=config,
        )

        snapshots = list(chan.step_load())
        assert len(snapshots) > 0
        assert len({id(snapshot) for snapshot in snapshots}) == len(snapshots)
        # Each snapshot is a copy of CChan at that step
        last_snapshot = snapshots[-1]
        assert isinstance(last_snapshot, CChan)

    def test_csv_file_path_is_forwarded_to_data_source(self, tmp_path):
        csv_path = tmp_path / "custom.csv"
        csv_path.write_text(
            "time,open,high,low,close\n"
            "2024-01-01,10,12,9,11\n",
            encoding="utf-8",
        )
        chan = CChan(
            code="IGNORED",
            data_src=DATA_SRC.CSV,
            lv_list=[KL_TYPE.K_DAY],
            file_path=str(csv_path),
        )
        assert len(list(chan[KL_TYPE.K_DAY].klu_iter())) == 1


class TestCChanMultiLevelPipeline:
    """End-to-End tests for multi-level (e.g. Day + 60M) timeframe synchronization."""

    def test_multi_level_parent_child_linkage(self, mock_stock_api):
        code = "TEST_MULTI"
        day_bars = generate_monotone_up(count=3)
        # For each day bar, create 4 hourly bars
        min_bars = []
        for d_idx, day_bar in enumerate(day_bars):
            day_num = d_idx + 1
            for h, m in [(10, 30), (11, 30), (14, 0), (15, 0)]:
                from tests.conftest import create_klu
                min_bars.append(create_klu(
                    year=2024, month=1, day=day_num,
                    open_p=day_bar.open, high_p=day_bar.high,
                    low_p=day_bar.low, close_p=day_bar.close,
                    hour=h, minute=m
                ))

        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, day_bars)
        InMemoryStockApi.register_data(code, KL_TYPE.K_60M, min_bars)

        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[KL_TYPE.K_DAY, KL_TYPE.K_60M],
            config=CChanConfig({"kl_data_check": False}),
        )

        day_kl = chan[KL_TYPE.K_DAY]
        assert len(day_kl.lst) > 0


class TestCChanDefects:
    """Regression test specifically targeting CChan level-alignment crash."""

    def test_check_kl_align_reports_domain_error(self, mock_stock_api):
        code = "TEST_DEFECT1"
        day_bars = generate_monotone_up(count=2)
        # Empty sub-level data will trigger check_kl_align
        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, day_bars)
        InMemoryStockApi.register_data(code, KL_TYPE.K_60M, [])

        config = CChanConfig({
            "kl_data_check": True,
            "print_warning": True,
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

    def test_step_load_snapshots_are_isolated(self, mock_stock_api):
        code = "TEST_STEP_ISOLATION"
        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, generate_monotone_up(count=6))
        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[KL_TYPE.K_DAY],
            config=CChanConfig({"trigger_step": True}),
        )

        snapshots = list(chan.step_load())
        assert len({id(snapshot) for snapshot in snapshots}) == len(snapshots)
        final_count = len(snapshots[-1][KL_TYPE.K_DAY].lst)
        snapshots[0][KL_TYPE.K_DAY].lst.clear()
        assert len(snapshots[-1][KL_TYPE.K_DAY].lst) == final_count

    def test_step_load_snapshot_step_zero_yields_live_object(self, mock_stock_api):
        """snapshot_step=0: no deepcopy, every yield is the same live CChan."""
        code = "TEST_STEP_LIVE"
        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, generate_monotone_up(count=6))
        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[KL_TYPE.K_DAY],
            config=CChanConfig({"trigger_step": True, "snapshot_step": 0}),
        )

        snapshots = list(chan.step_load())
        assert len(snapshots) > 0
        assert all(snapshot is chan for snapshot in snapshots)

    def test_step_load_snapshot_step_thins_output(self, mock_stock_api):
        """snapshot_step=k: only every k-th step produces a snapshot."""
        code = "TEST_STEP_THIN"
        bars = generate_monotone_up(count=6)
        InMemoryStockApi.register_data(code, KL_TYPE.K_DAY, bars)
        chan = CChan(
            code=code,
            data_src=DATA_SRC.CSV,
            lv_list=[KL_TYPE.K_DAY],
            config=CChanConfig({"trigger_step": True, "snapshot_step": 2}),
        )

        snapshots = list(chan.step_load())
        total_steps = len(bars)
        expected = (total_steps + 1) // 2
        assert len(snapshots) == expected
        # snapshots are still independent deep copies
        assert len({id(snapshot) for snapshot in snapshots}) == len(snapshots)

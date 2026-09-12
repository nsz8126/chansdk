# -*- coding: utf-8 -*-
"""chansdk basic tests"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_import():
    from chan import CChan, CChanConfig
    from chan import KL_TYPE, DATA_SRC, AUTYPE, BSP_TYPE
    from chan import KLINE_DIR, FX_TYPE, BI_DIR, BI_TYPE
    from chan import CChanException, CTime
    from chan import CKLine_Unit, CBi, CSeg, CZS, CBS_Point
    from chan import CCommonStockApi
    print("[PASS] All modules imported successfully")


def test_enum():
    from chan import KL_TYPE, DATA_SRC

    assert isinstance(KL_TYPE.K_DAY.value, int)
    assert isinstance(DATA_SRC.CSV.value, int)
    print("[PASS] Enum values correct")


def test_eltdx_data_source_route():
    from chan import CChan, DATA_SRC
    from chan.data.eltdx_api import CEldtxAPI

    chan = CChan.__new__(CChan)
    chan.data_src = DATA_SRC.ELTDX
    assert chan.GetStockAPI() is CEldtxAPI


def test_default_data_source_priority_order():
    from chan import CChan, DATA_SRC

    assert CChan.DATA_SRC_PRIORITY == (
        DATA_SRC.ELTDX,
        DATA_SRC.CSV,
    )


def test_default_data_source_falls_back_to_csv(monkeypatch):
    from chan import CChan, DATA_SRC
    from chan.data.csv_api import CSV_API

    monkeypatch.setattr("importlib.util.find_spec", lambda name: None)
    chan = CChan.__new__(CChan)
    chan.data_src = None

    assert chan.GetStockAPI() is CSV_API
    assert chan.data_src == DATA_SRC.CSV


def test_default_data_source_prefers_eltdx(monkeypatch):
    from chan import CChan, DATA_SRC

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: object() if name == "eltdx" else None,
    )
    chan = CChan.__new__(CChan)
    chan.data_src = None

    assert chan._get_default_data_src() == DATA_SRC.ELTDX


def test_config():
    from chan import CChanConfig

    config = CChanConfig()
    assert config.bi_conf is not None
    assert config.seg_conf is not None
    assert config.zs_conf is not None
    print("[PASS] Config initialized OK")


def test_time():
    from chan import CTime

    t1 = CTime(2024, 1, 1, 0, 0)
    t2 = CTime(2024, 1, 2, 0, 0)
    assert t1 < t2
    assert str(t1) == "2024/01/01"
    print("[PASS] CTime works correctly")


if __name__ == "__main__":
    test_import()
    test_enum()
    test_config()
    test_time()
    print("\nAll tests passed!")

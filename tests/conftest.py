# -*- coding: utf-8 -*-
"""
Pytest configuration and shared fixtures for chansdk testing.
Provides deterministic synthetic K-line data generators and in-memory stock API.
"""

import pytest
from typing import List, Dict, Optional, Iterable

from chan.common.time import CTime
from chan.common.enum import KL_TYPE, DATA_SRC, AUTYPE
from chan.kline.unit import CKLine_Unit
from chan.data.base import CCommonStockApi
from chan.config import CChanConfig


class InMemoryStockApi(CCommonStockApi):
    """
    In-memory stock data API for deterministic integration testing.
    Can be registered via dynamic loader string or used directly.
    """
    _data_registry: Dict[tuple, List[CKLine_Unit]] = {}

    @classmethod
    def register_data(cls, code: str, ktype: KL_TYPE, klu_list: List[CKLine_Unit]):
        cls._data_registry[(code, ktype)] = klu_list

    @classmethod
    def clear_registry(cls):
        cls._data_registry.clear()

    def SetBasciInfo(self):
        self.is_stock = True

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass

    def get_kl_data(self) -> Iterable[CKLine_Unit]:
        key = (self.code, self.k_type)
        if key in self._data_registry:
            yield from self._data_registry[key]
        else:
            return


@pytest.fixture(autouse=True)
def clean_in_memory_api():
    """Ensure in-memory API data registry is clean between tests."""
    InMemoryStockApi.clear_registry()
    yield
    InMemoryStockApi.clear_registry()


def make_klu_dict(
    time_str: str,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 1000.0,
    turnover: float = 10000.0,
    turnover_rate: float = 1.0,
) -> dict:
    """Helper to construct raw dictionary for CKLine_Unit."""
    return {
        "time_key": time_str,
        "open": float(open_p),
        "high": float(high_p),
        "low": float(low_p),
        "close": float(close_p),
        "volume": float(volume),
        "turnover": float(turnover),
        "turnover_rate": float(turnover_rate),
    }


def create_klu(
    year: int,
    month: int,
    day: int,
    open_p: float,
    high_p: float,
    low_p: float,
    close_p: float,
    volume: float = 1000.0,
    hour: int = 0,
    minute: int = 0,
    sub_kl_list: Optional[List[CKLine_Unit]] = None,
) -> CKLine_Unit:
    """Create a single CKLine_Unit with CTime and specified OHLCV."""
    time_str = f"{year:04d}-{month:02d}-{day:02d}" if hour == 0 and minute == 0 else f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
    d = make_klu_dict(time_str, open_p, high_p, low_p, close_p, volume)
    klu = CKLine_Unit(d)
    klu.time = CTime(year, month, day, hour, minute, auto=(hour == 0 and minute == 0))
    if sub_kl_list:
        klu.sub_kl_list = sub_kl_list
    return klu


@pytest.fixture
def sample_klu():
    """Returns a basic valid CKLine_Unit."""
    return create_klu(2024, 1, 1, 10.0, 12.0, 9.0, 11.0, 1000.0)


@pytest.fixture
def default_config():
    """Returns a default CChanConfig instance."""
    return CChanConfig()

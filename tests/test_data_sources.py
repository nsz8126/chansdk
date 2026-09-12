# -*- coding: utf-8 -*-
"""Regression tests for local and external data-source boundaries."""

import sqlite3
import warnings
from types import SimpleNamespace

import pytest

from chan.common.enum import AUTYPE, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.data.cache_api import CCacheDBAPI, get_stock_info_from_db, get_stock_list_from_db
from chan.data.csv_api import CSV_API


def create_cache_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE kline_data (
                code TEXT,
                kl_type TEXT,
                date TEXT,
                timestamp TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                amount REAL,
                turnover_rate REAL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO kline_data VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "000001",
                    "DAY",
                    "2024/01/01",
                    "2024-01-01 00:00:00",
                    10,
                    12,
                    9,
                    11,
                    1000,
                    10000,
                    1,
                    None,
                    None,
                ),
                (
                    "000001",
                    "DAY",
                    "2024/01/02",
                    "2024-01-02 00:00:00",
                    11,
                    13,
                    10,
                    12,
                    1100,
                    11000,
                    1.1,
                    None,
                    None,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_cache_api_reads_rows_and_helpers(tmp_path):
    db_path = tmp_path / "chan.db"
    create_cache_db(db_path)

    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        api = CCacheDBAPI("000001", KL_TYPE.K_DAY, db_path=str(db_path))
        rows = list(api.get_kl_data())

    assert [row.close for row in rows] == [11.0, 12.0]
    with warnings.catch_warnings():
        warnings.simplefilter("error", ResourceWarning)
        assert get_stock_list_from_db(str(db_path)) == ["000001"]
        assert get_stock_info_from_db("000001", str(db_path))["change"] == pytest.approx(100 / 11)


def test_cache_api_missing_database_is_domain_error(tmp_path):
    with pytest.raises(CChanException) as exc_info:
        CCacheDBAPI("000001", db_path=str(tmp_path / "missing.db"))
    assert exc_info.value.errcode == ErrCode.SRC_DATA_NOT_FOUND


def test_csv_date_filter_accepts_slash_and_dash_formats(tmp_path):
    csv_path = tmp_path / "mixed_dates.csv"
    csv_path.write_text(
        "time_key,open,high,low,close\n"
        "2024/01/01,10,12,9,11\n"
        "2024-01-02,11,13,10,12\n",
        encoding="utf-8",
    )

    api = CSV_API(
        "000001",
        KL_TYPE.K_DAY,
        begin_date="2024-01-01",
        end_date="2024-01-02",
        file_path=str(csv_path),
    )
    assert [item.close for item in api.get_kl_data()] == [11.0, 12.0]


def test_csv_api_uses_standard_csv_quoting(tmp_path):
    csv_path = tmp_path / "quoted.csv"
    csv_path.write_text(
        'time_key,open,high,low,close\n'
        '"2024-01-01","10","12","9","11"\n',
        encoding="utf-8",
    )

    api = CSV_API("000001", KL_TYPE.K_DAY, file_path=str(csv_path))
    rows = list(api.get_kl_data())

    assert len(rows) == 1
    assert rows[0].close == 11.0

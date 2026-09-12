"""SQLite-backed K-line data source."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Iterator, Optional

from chan.common.enum import AUTYPE, DATA_FIELD, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.common.time import CTime
from chan.kline.unit import CKLine_Unit

from .base import CCommonStockApi


def _get_db_path() -> str:
    """Return the default cache database path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    package_root = os.path.dirname(current_dir)
    db_path = os.path.join(package_root, "chan.db")
    if not os.path.exists(db_path):
        db_path = os.path.join(os.getcwd(), "chan.db")
    return db_path


def _parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    value = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"unsupported cache timestamp: {value}")


def _create_item_dict(row: tuple, autype: AUTYPE) -> dict:
    """Convert a kline_data row into CKLine_Unit input."""
    dt = _parse_timestamp(row[3])
    item = {
        DATA_FIELD.FIELD_TIME: CTime(dt.year, dt.month, dt.day, dt.hour, dt.minute),
        DATA_FIELD.FIELD_OPEN: float(row[4]),
        DATA_FIELD.FIELD_HIGH: float(row[5]),
        DATA_FIELD.FIELD_LOW: float(row[6]),
        DATA_FIELD.FIELD_CLOSE: float(row[7]),
        DATA_FIELD.FIELD_VOLUME: float(row[8] or 0),
        DATA_FIELD.FIELD_TURNOVER: float(row[9] or 0),
    }
    if row[10] is not None:
        item[DATA_FIELD.FIELD_TURNRATE] = float(row[10])
    return item


def _connect(db_path: str) -> sqlite3.Connection:
    if not os.path.exists(db_path):
        raise CChanException(f"cache database not found: {db_path}", ErrCode.SRC_DATA_NOT_FOUND)
    return sqlite3.connect(db_path)


@contextmanager
def _open_db(db_path: str) -> Iterator[sqlite3.Connection]:
    """Open a cache connection and always close it after the query."""
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def get_stock_list_from_db(db_path: Optional[str] = None) -> list:
    """Return stock codes with cached daily data."""
    db_path = db_path or _get_db_path()
    try:
        with _open_db(db_path) as conn:
            rows = conn.execute(
                "SELECT DISTINCT code FROM kline_data "
                "WHERE kl_type = 'DAY' ORDER BY code"
            ).fetchall()
        return [row[0] for row in rows]
    except CChanException:
        return []


def get_stock_info_from_db(code: str, db_path: Optional[str] = None) -> Optional[dict]:
    """Return the latest cached daily price and change for a stock."""
    db_path = db_path or _get_db_path()
    try:
        with _open_db(db_path) as conn:
            rows = conn.execute(
                "SELECT date, close FROM kline_data "
                "WHERE code = ? AND kl_type = 'DAY' "
                "ORDER BY date DESC LIMIT 2",
                (code,),
            ).fetchall()
    except CChanException:
        return None

    if not rows:
        return None

    latest_close = float(rows[0][1])
    previous_close = float(rows[1][1]) if len(rows) > 1 else None
    change_pct = (
        ((latest_close - previous_close) / previous_close) * 100
        if previous_close is not None and previous_close > 0
        else 0.0
    )
    return {
        "code": code,
        "name": code,
        "latest_price": latest_close,
        "change": change_pct,
    }


class CCacheDBAPI(CCommonStockApi):
    """Read cached daily, weekly, or monthly K-line data from SQLite."""

    def __init__(
        self,
        code,
        k_type=KL_TYPE.K_DAY,
        begin_date=None,
        end_date=None,
        autype=AUTYPE.QFQ,
        db_path: Optional[str] = None,
    ):
        self.db_path = db_path or _get_db_path()
        super().__init__(code, k_type, begin_date, end_date, autype)
        if not os.path.exists(self.db_path):
            raise CChanException(
                f"cache database not found: {self.db_path}",
                ErrCode.SRC_DATA_NOT_FOUND,
            )

    def get_kl_data(self) -> Iterable[CKLine_Unit]:
        kl_type_str = self._convert_kl_type()
        start_date = (self.begin_date or "2000-01-01").replace("-", "/")
        end_date = (self.end_date or "2099-12-31").replace("-", "/")
        query = """
            SELECT code, kl_type, date, timestamp, open, high, low, close,
                   volume, amount, turnover_rate, created_at, updated_at
            FROM kline_data
            WHERE code = ? AND kl_type = ? AND date >= ? AND date <= ?
            ORDER BY date ASC
        """
        try:
            with _open_db(self.db_path) as conn:
                rows = conn.execute(
                    query,
                    (self.code, kl_type_str, start_date, end_date),
                ).fetchall()
        except sqlite3.Error as exc:
            raise CChanException(
                f"cache query failed for {self.code}: {exc}",
                ErrCode.SRC_DATA_FORMAT_ERROR,
            ) from exc

        for row in rows:
            yield CKLine_Unit(_create_item_dict(row, self.autype))

    def SetBasciInfo(self):
        self.name = self.code
        self.is_stock = True

    @classmethod
    def do_init(cls):
        return None

    @classmethod
    def do_close(cls):
        return None

    def _convert_kl_type(self) -> str:
        mapping = {
            KL_TYPE.K_DAY: "DAY",
            KL_TYPE.K_WEEK: "WEEK",
            KL_TYPE.K_MON: "MON",
        }
        try:
            return mapping[self.k_type]
        except KeyError as exc:
            raise CChanException(
                f"cache database does not support {self.k_type}",
                ErrCode.PARA_ERROR,
            ) from exc


CacheDBAPI = CCacheDBAPI

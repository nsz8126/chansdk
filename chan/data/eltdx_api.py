"""eltdx data source adapter.

This adapter uses the ``eltdx`` package, a Rust-based TDX client with Python
bindings.  It supports server-side adjustment (QFQ/HFQ) and automatic server
discovery with connection pooling.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time
from typing import Callable, Iterable

from chan.common.enum import AUTYPE, DATA_FIELD, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.common.time import CTime
from chan.kline.unit import CKLine_Unit

from .base import CCommonStockApi


_KL_TYPE_MAP = {
    KL_TYPE.K_1M: "1m",
    KL_TYPE.K_5M: "5m",
    KL_TYPE.K_15M: "15m",
    KL_TYPE.K_30M: "30m",
    KL_TYPE.K_60M: "60m",
    KL_TYPE.K_DAY: "day",
    KL_TYPE.K_WEEK: "week",
    KL_TYPE.K_MON: "month",
    KL_TYPE.K_QUARTER: "quarter",
    KL_TYPE.K_YEAR: "year",
}

_AUTYPE_MAP = {
    AUTYPE.QFQ: "qfq",
    AUTYPE.HFQ: "hfq",
    AUTYPE.NONE: "none",
}


def _normalise_code(code: str) -> str:
    """Return eltdx-format code like 'sz000001' or 'sh600519'."""
    value = str(code).strip().lower().replace(".", "")
    if value.startswith(("sh", "sz", "bj")):
        return value
    if value.startswith("6"):
        return f"sh{value}"
    if value.startswith(("0", "2", "3")):
        return f"sz{value}"
    if value.startswith(("4", "8")):
        return f"bj{value}"
    raise ValueError(f"无法识别证券代码市场: {code}")


def _parse_datetime(value, *, is_end: bool = False) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, dt_time.max if is_end else dt_time.min)
    text = str(value).strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if len(text) == 10:
        return datetime.fromisoformat(text).replace(
            hour=23 if is_end else 0,
            minute=59 if is_end else 0,
            second=59 if is_end else 0,
            microsecond=999999 if is_end else 0,
        )
    return datetime.fromisoformat(text)


def _parse_bar_time(value) -> CTime:
    parsed = _parse_datetime(value)
    if parsed is None:
        raise ValueError("K线时间为空")
    return CTime(parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


def _bar_datetime(value) -> datetime:
    """Convert eltdx timezone-aware datetime to naive datetime."""
    if value is None:
        raise ValueError("K线时间为空")
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    return _parse_datetime(value)


def _create_item_dict(bar) -> dict:
    """Convert an eltdx KlineBar into CKLine_Unit input fields."""
    return {
        DATA_FIELD.FIELD_TIME: _parse_bar_time(bar.time),
        DATA_FIELD.FIELD_OPEN: float(bar.open),
        DATA_FIELD.FIELD_HIGH: float(bar.high),
        DATA_FIELD.FIELD_LOW: float(bar.low),
        DATA_FIELD.FIELD_CLOSE: float(bar.close),
        DATA_FIELD.FIELD_VOLUME: float(bar.volume_wire_value),
        DATA_FIELD.FIELD_TURNOVER: float(bar.amount),
    }


class CEldtxAPI(CCommonStockApi):
    """Fetch A-share/index K-lines through the ``eltdx`` Rust SDK."""

    def __init__(
        self,
        code,
        k_type=KL_TYPE.K_DAY,
        begin_date=None,
        end_date=None,
        autype=AUTYPE.QFQ,
        timeout=5.0,
        retry_count=2,
        retry_sleep=0.5,
        servers=None,
        host=None,
        **_kwargs,
    ):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if retry_count < 0:
            raise ValueError("retry_count must be non-negative")
        if retry_sleep < 0:
            raise ValueError("retry_sleep must be non-negative")

        self.timeout = float(timeout)
        self.retry_count = int(retry_count)
        self.retry_sleep = float(retry_sleep)
        self.host = host
        self._client = None
        super().__init__(code, k_type, begin_date, end_date, autype)

    def _new_client(self):
        try:
            from eltdx import TdxClient
        except ImportError as exc:
            raise ImportError("请安装 eltdx: pip install eltdx") from exc
        kwargs = {"timeout": self.timeout}
        if self.host:
            kwargs["host"] = self.host
        return TdxClient(**kwargs)

    def _connect(self):
        try:
            self._client = self._new_client()
            self._client.connect()
            return self._client
        except ImportError:
            raise
        except Exception as exc:
            error_msg = str(exc)
            if "timed out" in error_msg.lower():
                raise ConnectionError(
                    f"无法连接到通达信服务器 (连接超时): {exc}"
                ) from exc
            raise ConnectionError(f"无法连接到通达信服务器: {exc}") from exc

    def _close_connection(self):
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def _get_period(self):
        period = _KL_TYPE_MAP.get(self.k_type)
        if period is None:
            raise ValueError(f"eltdx 不支持 {self.k_type} 级别的 K 线数据")
        return period

    def _get_adjust(self):
        return _AUTYPE_MAP.get(self.autype, "none")

    def _fetch_bars(self):
        period = self._get_period()
        adjust = self._get_adjust()
        code = _normalise_code(self.code)

        try:
            result = self._client.bars.get(
                code,
                period=period,
                adjust=adjust,
                count=800,
            )
            return list(result.bars) if result and result.bars else []
        except Exception:
            return []

    def get_kl_data(self) -> Iterable[CKLine_Unit]:
        begin = _parse_datetime(self.begin_date)
        end = _parse_datetime(self.end_date, is_end=True)
        try:
            self._connect()
            bars = self._fetch_bars()
            bars.sort(key=lambda item: _bar_datetime(item.time))
            for bar in bars:
                bar_time = _bar_datetime(bar.time)
                if begin is not None and bar_time < begin:
                    continue
                if end is not None and bar_time > end:
                    continue
                yield CKLine_Unit(_create_item_dict(bar))
        except ImportError:
            raise
        except CChanException:
            raise
        except Exception as exc:
            raise CChanException(
                f"eltdx 获取 {self.code} 数据失败: {exc}",
                ErrCode.SRC_DATA_NOT_FOUND,
            ) from exc
        finally:
            self._close_connection()

    def SetBasciInfo(self):
        self.name = self.code
        code = str(self.code).lower().replace(".", "")
        self.is_stock = not code.startswith(("sh000", "sz399"))

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass

    def __del__(self):
        try:
            self._close_connection()
        except Exception:
            pass


EldtxAPI = CEldtxAPI

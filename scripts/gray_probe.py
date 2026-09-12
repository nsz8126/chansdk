"""Run a small, repeatable gray probe for chansdk data sources."""

import argparse
import csv
import json
import sqlite3
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chan import CChan, CChanConfig, DATA_SRC, KL_TYPE
from chan.common.exception import CChanException


def _parse_date(value):
    try:
        return date.fromisoformat(value.replace("/", "-"))
    except ValueError as exc:
        raise SystemExit(f"invalid date: {value}") from exc


def _make_rows(start_date, count=16):
    rows = []
    price = 10.0
    for offset in range(count):
        current_date = start_date + timedelta(days=offset)
        rows.append(
            {
                "date": current_date.isoformat(),
                "open": price,
                "high": price + 0.8,
                "low": price - 0.2,
                "close": price + 0.6,
                "volume": 1000.0 + (offset + 1) * 10,
                "amount": 10000.0 + (offset + 1) * 100,
                "turnover_rate": 1.0,
            }
        )
        price += 1.0
    return rows


def _metrics(source, chan, elapsed_ms):
    daily = chan[KL_TYPE.K_DAY]
    return {
        "source": source,
        "status": "PASS",
        "elapsed_ms": round(elapsed_ms, 2),
        "klu_count": sum(len(klc.lst) for klc in daily.lst),
        "bi_count": len(daily.bi_list),
        "seg_count": len(daily.seg_list),
        "zs_count": len(daily.zs_list),
        "bsp_count": len(daily.bs_point_lst),
    }


def _run_local_csv(rows, begin, end, repeat):
    results = []
    with tempfile.TemporaryDirectory(prefix="chansdk-gray-csv-") as tmp:
        csv_path = Path(tmp) / "000001_day.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time_key", "open", "high", "low", "close"])
            for row in rows:
                writer.writerow(
                    [
                        row["date"],
                        row["open"],
                        row["high"],
                        row["low"],
                        row["close"],
                    ]
                )

        for _ in range(repeat):
            started = time.perf_counter()
            chan = CChan(
                code="000001",
                begin_time=begin,
                end_time=end,
                data_src=DATA_SRC.CSV,
                lv_list=[KL_TYPE.K_DAY],
                config=CChanConfig({"bi_strict": False}),
                file_path=str(csv_path),
            )
            results.append(_metrics("CSV", chan, (time.perf_counter() - started) * 1000))
    return results


def _create_cache_db(db_path, rows):
    conn = sqlite3.connect(db_path)
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
                    row["date"].replace("-", "/"),
                    f"{row['date']} 00:00:00",
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                    row["amount"],
                    row["turnover_rate"],
                    None,
                    None,
                )
                for row in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _run_local_cache(rows, begin, end, repeat):
    results = []
    with tempfile.TemporaryDirectory(prefix="chansdk-gray-cache-") as tmp:
        db_path = Path(tmp) / "chan.db"
        _create_cache_db(db_path, rows)
        for _ in range(repeat):
            started = time.perf_counter()
            chan = CChan(
                code="000001",
                begin_time=begin,
                end_time=end,
                data_src=DATA_SRC.CACHE_DB,
                lv_list=[KL_TYPE.K_DAY],
                config=CChanConfig({"bi_strict": False}),
                db_path=str(db_path),
            )
            results.append(
                _metrics("CACHE_DB", chan, (time.perf_counter() - started) * 1000)
            )
    return results


def _run_external(source, begin, end, eltdx_timeout=10.0):
    started = time.perf_counter()
    kwargs = {
        "code": "000001",
        "begin_time": begin,
        "end_time": end,
        "data_src": source,
        "lv_list": [KL_TYPE.K_DAY],
        "config": CChanConfig({"bi_strict": False}),
        "timeout": eltdx_timeout,
        "retry_count": 0,
    }

    try:
        chan = CChan(**kwargs)
        return _metrics(
            source.name,
            chan,
            (time.perf_counter() - started) * 1000,
        )
    except CChanException as exc:
        error_msg = str(exc)
        if "连接超时" in error_msg or "连接" in error_msg:
            return {
                "source": source.name,
                "status": "SKIP",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "reason": "网络连接超时或服务器不可达",
                "error": error_msg,
            }
        return {
            "source": source.name,
            "status": "FAIL",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "errcode": getattr(exc.errcode, "name", str(exc.errcode)),
            "error": error_msg,
        }
    except Exception as exc:
        error_msg = str(exc)
        if "timed out" in error_msg.lower() or "connect" in error_msg.lower():
            return {
                "source": source.name,
                "status": "SKIP",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                "reason": "网络连接超时或服务器不可达",
                "error": error_msg,
            }
        return {
            "source": source.name,
            "status": "UNEXPECTED_FAILURE",
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "error_type": type(exc).__name__,
            "error": error_msg,
        }


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", default="000001")
    parser.add_argument("--begin", default="2024-01-01")
    parser.add_argument("--end", default="2024-01-16")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--include-external", action="store_true")
    parser.add_argument("--eltdx-timeout", type=float, default=10.0)
    parser.add_argument("--json-out", type=Path)
    return parser


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.repeat <= 0:
        raise SystemExit("--repeat must be positive")
    if args.code != "000001":
        raise SystemExit("the deterministic local probe currently supports code 000001")

    begin = _parse_date(args.begin)
    end = _parse_date(args.end)
    if end < begin:
        raise SystemExit("--end must not be earlier than --begin")

    rows = _make_rows(begin)
    results = []
    results.extend(_run_local_csv(rows, args.begin, args.end, args.repeat))
    results.extend(_run_local_cache(rows, args.begin, args.end, args.repeat))

    if args.include_external:
        results.append(
            _run_external(DATA_SRC.ELTDX, args.begin, args.end, args.eltdx_timeout)
        )

    failed = [item for item in results if item["status"] != "PASS"]
    payload = {
        "scope": "chansdk gray probe",
        "code": args.code,
        "window": [args.begin, args.end],
        "repeat": args.repeat,
        "include_external": args.include_external,
        "results": results,
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 2 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

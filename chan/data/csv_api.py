import csv
import os

from chan.common.enum import DATA_FIELD, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.common.time import CTime
from chan.common.util import str2float
from chan.kline.unit import CKLine_Unit

from .base import CCommonStockApi


def create_item_dict(data, column_name):
    for i in range(len(data)):
        data[i] = parse_time_column(data[i]) if column_name[i] == DATA_FIELD.FIELD_TIME else str2float(data[i])
    return dict(zip(column_name, data))


def parse_time_column(inp):
    # 20210902113000000
    # 2021-09-13
    if len(inp) == 10:
        year = int(inp[:4])
        month = int(inp[5:7])
        day = int(inp[8:10])
        hour = minute = 0
    elif len(inp) == 17:
        year = int(inp[:4])
        month = int(inp[4:6])
        day = int(inp[6:8])
        hour = int(inp[8:10])
        minute = int(inp[10:12])
    elif len(inp) == 19:
        year = int(inp[:4])
        month = int(inp[5:7])
        day = int(inp[8:10])
        hour = int(inp[11:13])
        minute = int(inp[14:16])
    else:
        raise Exception(f"unknown time column from csv:{inp}")
    return CTime(year, month, day, hour, minute)


class CSV_API(CCommonStockApi):
    def __init__(
        self,
        code,
        k_type=KL_TYPE.K_DAY,
        begin_date=None,
        end_date=None,
        autype=None,
        file_path=None,
    ):
        self.file_path = file_path
        self.headers_exist = True  # 第一行是否是标题，如果是数据，设置为False
        self.columns = [
            DATA_FIELD.FIELD_TIME,
            DATA_FIELD.FIELD_OPEN,
            DATA_FIELD.FIELD_HIGH,
            DATA_FIELD.FIELD_LOW,
            DATA_FIELD.FIELD_CLOSE,
            # DATA_FIELD.FIELD_VOLUME,
            # DATA_FIELD.FIELD_TURNOVER,
            # DATA_FIELD.FIELD_TURNRATE,
        ]  # 每一列字�?
        self.time_column_idx = self.columns.index(DATA_FIELD.FIELD_TIME)
        super(CSV_API, self).__init__(code, k_type, begin_date, end_date, autype)

    def get_kl_data(self):
        cur_path = os.path.dirname(os.path.realpath(__file__))
        k_type = self.k_type.name[2:].lower()
        file_path = self.file_path or f"{cur_path}/../{self.code}_{k_type}.csv"
        if not os.path.exists(file_path):
            raise CChanException(f"file not exist: {file_path}", ErrCode.SRC_DATA_NOT_FOUND)

        begin_time = parse_time_column(self.begin_date) if self.begin_date is not None else None
        end_time = parse_time_column(self.end_date) if self.end_date is not None else None

        with open(file_path, 'r', newline='', encoding='utf-8') as csv_file:
            lines = enumerate(csv.reader(csv_file))
            for line_number, data in lines:
                if self.headers_exist and line_number == 0:
                    continue
                if len(data) != len(self.columns):
                    raise CChanException(f"file format error: {file_path}", ErrCode.SRC_DATA_FORMAT_ERROR)
                try:
                    row_time = parse_time_column(data[self.time_column_idx])
                except (TypeError, ValueError, IndexError) as exc:
                    raise CChanException(
                        f"file time format error: {file_path}:{line_number + 1}",
                        ErrCode.SRC_DATA_FORMAT_ERROR,
                    ) from exc
                if begin_time is not None and row_time < begin_time:
                    continue
                if end_time is not None and row_time > end_time:
                    continue
                yield CKLine_Unit(create_item_dict(data, self.columns))

    def SetBasciInfo(self):
        pass

    @classmethod
    def do_init(cls):
        pass

    @classmethod
    def do_close(cls):
        pass

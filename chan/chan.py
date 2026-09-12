import copy
import datetime
import importlib.util
import pickle
import sys
import warnings
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Union
from chan.bsp.point import CBS_Point
from chan.config import CChanConfig
from chan.common.enum import AUTYPE, DATA_SRC, KL_TYPE
from chan.common.exception import CChanException, ErrCode
from chan.common.time import CTime
from chan.common.util import check_kltype_order, kltype_lte_day
from chan.data.base import CCommonStockApi
from chan.kline.list import CKLine_List
from chan.kline.unit import CKLine_Unit


class CChan:

    DATA_SRC_PRIORITY = (
        DATA_SRC.ELTDX,
        DATA_SRC.CSV,
    )

    def __init__(
        self,
        code,
        begin_time=None,
        end_time=None,
        data_src: Optional[Union[DATA_SRC, str]] = None,
        lv_list=None,
        config=None,
        autype: AUTYPE = AUTYPE.QFQ,
        **data_src_kwargs,
    ):
        if lv_list is None:
            lv_list = [KL_TYPE.K_DAY, KL_TYPE.K_60M]
        check_kltype_order(lv_list)  # lv_list顺序从高到低
        self.code = code
        self.begin_time = str(begin_time) if isinstance(begin_time, datetime.date) else begin_time
        self.end_time = str(end_time) if isinstance(end_time, datetime.date) else end_time
        self.autype = autype
        self.data_src = data_src
        self.lv_list: List[KL_TYPE] = lv_list
        self.data_src_kwargs = data_src_kwargs
        if config is None:
            config = CChanConfig()
        self.conf = config
        self.kl_misalign_cnt = 0
        self.kl_inconsistent_detail = defaultdict(list)
        self.g_kl_iter = defaultdict(list)
        self.do_init()
        if not config.trigger_step:
            for _ in self.load():
                ...

    def __deepcopy__(self, memo):
        cls = self.__class__
        obj: CChan = cls.__new__(cls)
        memo[id(self)] = obj
        obj.code = self.code
        obj.begin_time = self.begin_time
        obj.end_time = self.end_time
        obj.autype = self.autype
        obj.data_src = self.data_src
        obj.lv_list = copy.deepcopy(self.lv_list, memo)
        obj.data_src_kwargs = copy.deepcopy(self.data_src_kwargs, memo)
        obj.conf = copy.deepcopy(self.conf, memo)
        obj.kl_misalign_cnt = self.kl_misalign_cnt
        obj.kl_inconsistent_detail = copy.deepcopy(self.kl_inconsistent_detail, memo)
        # Load iterators are live generators and cannot be deep-copied. A
        # snapshot only needs the calculated data, not the source cursor.
        obj.g_kl_iter = defaultdict(list)
        if hasattr(self, 'klu_cache'):
            obj.klu_cache = copy.deepcopy(self.klu_cache, memo)
        if hasattr(self, 'klu_last_t'):
            obj.klu_last_t = copy.deepcopy(self.klu_last_t, memo)
        obj.kl_datas = {}
        for kl_type, ckline in self.kl_datas.items():
            obj.kl_datas[kl_type] = copy.deepcopy(ckline, memo)
        for kl_type, ckline in self.kl_datas.items():
            for klc in ckline:
                for klu in klc.lst:
                    assert id(klu) in memo
                    if klu.sup_kl:
                        memo[id(klu)].sup_kl = memo[id(klu.sup_kl)]
                    memo[id(klu)].sub_kl_list = [memo[id(sub_kl)] for sub_kl in klu.sub_kl_list]
        return obj

    def do_init(self):
        self.kl_datas: Dict[KL_TYPE, CKLine_List] = {}
        for idx in range(len(self.lv_list)):
            self.kl_datas[self.lv_list[idx]] = CKLine_List(self.lv_list[idx], conf=self.conf)

    def load_stock_data(self, stockapi_instance: CCommonStockApi, lv) -> Iterable[CKLine_Unit]:
        for KLU_IDX, klu in enumerate(stockapi_instance.get_kl_data()):
            klu.set_idx(KLU_IDX)
            klu.kl_type = lv
            yield klu

    def get_load_stock_iter(self, stockapi_cls, lv):
        stockapi_instance = stockapi_cls(
            code=self.code,
            k_type=lv,
            begin_date=self.begin_time,
            end_date=self.end_time,
            autype=self.autype,
            **self.data_src_kwargs,
        )
        return self.load_stock_data(stockapi_instance, lv)

    def add_lv_iter(self, lv_idx, iter):
        if isinstance(lv_idx, int):
            self.g_kl_iter[self.lv_list[lv_idx]].append(iter)
        else:
            self.g_kl_iter[lv_idx].append(iter)

    def get_next_lv_klu(self, lv_idx):
        if isinstance(lv_idx, int):
            lv_idx = self.lv_list[lv_idx]
        if len(self.g_kl_iter[lv_idx]) == 0:
            raise StopIteration
        try:
            return self.g_kl_iter[lv_idx][0].__next__()
        except StopIteration:
            self.g_kl_iter[lv_idx] = self.g_kl_iter[lv_idx][1:]
            if len(self.g_kl_iter[lv_idx]) != 0:
                return self.get_next_lv_klu(lv_idx)
            else:
                raise

    def step_load(self):
        assert self.conf.trigger_step
        self.do_init()  # 清空数据，防止再次重跑没有数�?
        yielded = False  # 是否曾经返回过结�?
        snapshot_step = self.conf.snapshot_step
        for idx, snapshot in enumerate(self.load(self.conf.trigger_step)):
            if idx < self.conf.skip_step:
                continue
            if snapshot_step == 0:
                # 不做深拷贝，直接产出实时对象。调用方不应持有其引用，
                # 下一次迭代对象内容即被更新
                yield snapshot
            elif (idx - self.conf.skip_step) % snapshot_step == 0:
                yield copy.deepcopy(snapshot)
            else:
                continue
            yielded = True
        if not yielded:
            yield self

    def trigger_load(self, inp):
        # {type: [klu, ...]}
        if not hasattr(self, 'klu_cache'):
            self.klu_cache: List[Optional[CKLine_Unit]] = [None for _ in self.lv_list]
        if not hasattr(self, 'klu_last_t'):
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0) for _ in self.lv_list]
        for lv_idx, lv in enumerate(self.lv_list):
            if lv not in inp:
                if lv_idx == 0:
                    raise CChanException(f"最高级别{lv}没有传入数据", ErrCode.NO_DATA)
                continue
            for klu in inp[lv]:
                klu.kl_type = lv
            assert isinstance(inp[lv], list)
            self.add_lv_iter(lv, iter(inp[lv]))
        for _ in self.load_iterator(lv_idx=0, parent_klu=None, step=False):
            ...
        if not self.conf.trigger_step:  # 非回放模式全部算完之后才算一次中枢和线段
            for lv in self.lv_list:
                self.kl_datas[lv].cal_seg_and_zs()

    def init_lv_klu_iter(self, stockapi_cls):
        # 为了跳过一些获取数据失败的级别
        lv_klu_iter = []
        valid_lv_list = []
        for lv in self.lv_list:
            try:
                lv_klu_iter.append(self.get_load_stock_iter(stockapi_cls, lv))
                valid_lv_list.append(lv)
            except CChanException as e:
                if e.errcode == ErrCode.SRC_DATA_NOT_FOUND and self.conf.auto_skip_illegal_sub_lv:
                    if self.conf.print_warning:
                        print(f"[WARNING-{self.code}]{lv}级别获取数据失败，跳过")
                    del self.kl_datas[lv]
                    continue
                raise e
        self.lv_list = valid_lv_list
        return lv_klu_iter

    def GetStockAPI(self):
        if self.data_src is None:
            self.data_src = self._get_default_data_src()
        _dict = {}
        if self.data_src == DATA_SRC.CSV:
            from chan.data.csv_api import CSV_API
            _dict[DATA_SRC.CSV] = CSV_API
        elif self.data_src == DATA_SRC.ELTDX:
            from chan.data.eltdx_api import CEldtxAPI
            _dict[DATA_SRC.ELTDX] = CEldtxAPI
        elif self.data_src == DATA_SRC.CACHE_DB:
            from chan.data.cache_api import CCacheDBAPI
            _dict[DATA_SRC.CACHE_DB] = CCacheDBAPI
        if self.data_src in _dict:
            return _dict[self.data_src]
        assert isinstance(self.data_src, str)
        if self.data_src.find("custom:") < 0:
            raise CChanException("load src type error", ErrCode.SRC_DATA_TYPE_ERR)
        package_info = self.data_src.split(":")[1]
        package_name, cls_name = package_info.rsplit(".", 1)
        import importlib
        try:
            module = importlib.import_module(package_name)
        except ImportError:
            module = importlib.import_module(f"chan.data.{package_name}")
        return getattr(module, cls_name)

    @classmethod
    def _get_default_data_src(cls) -> DATA_SRC:
        """Choose the highest-priority installed optional data source."""
        for data_src in cls.DATA_SRC_PRIORITY:
            if data_src == DATA_SRC.ELTDX and importlib.util.find_spec("eltdx"):
                return data_src
            if data_src == DATA_SRC.CSV:
                return data_src
        return DATA_SRC.CSV

    def load(self, step=False):
        stockapi_cls = self.GetStockAPI()
        try:
            stockapi_cls.do_init()
            for lv_idx, klu_iter in enumerate(self.init_lv_klu_iter(stockapi_cls)):
                self.add_lv_iter(lv_idx, klu_iter)
            self.klu_cache: List[Optional[CKLine_Unit]] = [None for _ in self.lv_list]
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0) for _ in self.lv_list]
            yield from self.load_iterator(lv_idx=0, parent_klu=None, step=step)  # 计算入口
            if len(self[0]) == 0:
                raise CChanException("最高级别没有获得任何数据", ErrCode.NO_DATA)
            if not step:  # 非回放模式全部算完之后才算一次中枢和线段
                for lv in self.lv_list:
                    self.kl_datas[lv].cal_seg_and_zs()
        finally:
            stockapi_cls.do_close()

    def set_klu_parent_relation(self, parent_klu, kline_unit, cur_lv, lv_idx):
        if self.conf.kl_data_check and kltype_lte_day(cur_lv) and kltype_lte_day(self.lv_list[lv_idx-1]):
            self.check_kl_consitent(parent_klu, kline_unit)
        parent_klu.add_children(kline_unit)
        kline_unit.set_parent(parent_klu)

    def add_new_kl(self, cur_lv: KL_TYPE, kline_unit):
        try:
            self.kl_datas[cur_lv].add_single_klu(kline_unit)
        except Exception:
            if self.conf.print_err_time:
                print(f"[ERROR-{self.code}]在计算{kline_unit.time}K线时发生错误!")
            raise

    def try_set_klu_idx(self, lv_idx: int, kline_unit: CKLine_Unit):
        if kline_unit.idx >= 0:
            return
        if len(self[lv_idx]) == 0:
            kline_unit.set_idx(0)
        else:
            kline_unit.set_idx(self[lv_idx][-1][-1].idx + 1)

    def load_iterator(self, lv_idx, parent_klu, step):
        # K线时间天级别以下描述的是结束时间，如60M线，每天第一根是10�?0�?
        # 天以上是当天日期
        cur_lv = self.lv_list[lv_idx]
        pre_klu = self[lv_idx][-1][-1] if len(self[lv_idx]) > 0 and len(self[lv_idx][-1]) > 0 else None
        while True:
            if self.klu_cache[lv_idx]:
                kline_unit = self.klu_cache[lv_idx]
                assert kline_unit is not None
                self.klu_cache[lv_idx] = None
            else:
                try:
                    kline_unit = self.get_next_lv_klu(lv_idx)
                    self.try_set_klu_idx(lv_idx, kline_unit)
                    if not kline_unit.time > self.klu_last_t[lv_idx]:
                        raise CChanException(f"kline time err, cur={kline_unit.time}, last={self.klu_last_t[lv_idx]}, or refer to quick_guide.md, try set auto=False in the CTime returned by your data source class", ErrCode.KL_NOT_MONOTONOUS)
                    self.klu_last_t[lv_idx] = kline_unit.time
                except StopIteration:
                    break
            if parent_klu and kline_unit.time > parent_klu.time:
                self.klu_cache[lv_idx] = kline_unit
                break
            kline_unit.set_pre_klu(pre_klu)
            pre_klu = kline_unit
            self.add_new_kl(cur_lv, kline_unit)
            if parent_klu:
                self.set_klu_parent_relation(parent_klu, kline_unit, cur_lv, lv_idx)
            if lv_idx != len(self.lv_list)-1:
                for _ in self.load_iterator(lv_idx+1, kline_unit, step):
                    ...
                self.check_kl_align(kline_unit, lv_idx)
            if lv_idx == 0 and step:
                yield self

    def check_kl_consitent(self, parent_klu, sub_klu):
        if parent_klu.time.year != sub_klu.time.year or \
           parent_klu.time.month != sub_klu.time.month or \
           parent_klu.time.day != sub_klu.time.day:
            self.kl_inconsistent_detail[str(parent_klu.time)].append(sub_klu.time)
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]父级别时间是{parent_klu.time}，次级别K线时间是{sub_klu.time}")
            if len(self.kl_inconsistent_detail) >= self.conf.max_kl_inconsistent_cnt:
                raise CChanException(f"父/子级别K线时间不一致条数超过{self.conf.max_kl_inconsistent_cnt}！！", ErrCode.KL_TIME_INCONSISTENT)

    def check_kl_align(self, kline_unit, lv_idx):
        if self.conf.kl_data_check and len(kline_unit.sub_kl_list) == 0:
            self.kl_misalign_cnt += 1
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]父级别时间是{kline_unit.time}，未找到次级别K线")
            if self.kl_misalign_cnt >= self.conf.max_kl_misalgin_cnt:
                raise CChanException(f"在次级别找不到K线条数超过{self.conf.max_kl_misalgin_cnt}！！", ErrCode.KL_DATA_NOT_ALIGN)

    def __getitem__(self, n) -> CKLine_List:
        if isinstance(n, KL_TYPE):
            return self.kl_datas[n]
        elif isinstance(n, int):
            return self.kl_datas[self.lv_list[n]]
        else:
            raise CChanException("unsupport query type", ErrCode.COMMON_ERROR)

    def __iter__(self):
        if self.conf.trigger_step:
            return self.step_load()
        return iter(self.kl_datas.values())

    def get_bsp(self, idx=None) -> List[CBS_Point]:
        warnings.warn("get_bsp is deprecated, use get_latest_bsp instead", DeprecationWarning, stacklevel=2)
        if idx is not None:
            return self[idx].bs_point_lst.getSortedBspList()
        assert len(self.lv_list) == 1
        return self[0].bs_point_lst.getSortedBspList()

    def get_latest_bsp(self, idx=None, number=1) -> List[CBS_Point]:
        # number=0则取全部bsp，从最新到最旧排�?
        if idx is not None:
            return self[idx].bs_point_lst.get_latest_bsp(number)
        assert len(self.lv_list) == 1
        return self[0].bs_point_lst.get_latest_bsp(number)

    def chan_dump_pickle(self, file_path):
        _pre_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(0x100000)
        try:
            for kl_list in self.kl_datas.values():
                for klc in kl_list.lst:
                    for klu in klc.lst:
                        klu.pre = None
                        klu.next = None
                    klc.set_pre(None)
                    klc.set_next(None)
                for bi in kl_list.bi_list:
                    bi.pre = None
                    bi.next = None
                for seg in kl_list.seg_list:
                    seg.pre = None
                    seg.next = None
                for segseg in kl_list.segseg_list:
                    segseg.pre = None
                    segseg.next = None
            with open(file_path, "wb") as f:
                pickle.dump(self, f)
        finally:
            sys.setrecursionlimit(_pre_limit)
            self.chan_pickle_restore()

    @staticmethod

    def chan_load_pickle(file_path) -> 'CChan':
        with open(file_path, "rb") as f:
            chan = pickle.load(f)
        chan.chan_pickle_restore()
        return chan

    def chan_pickle_restore(self):
        for kl_list in self.kl_datas.values():
            last_klu = None
            last_klc = None
            last_bi = None
            last_seg = None
            last_segseg = None
            for klc in kl_list.lst:
                for klu in klc.lst:
                    klu.pre = last_klu
                    if last_klu:
                        last_klu.next = klu
                    last_klu = klu
                klc.set_pre(last_klc)
                if last_klc:
                    last_klc.set_next(klc)
                last_klc = klc
            for bi in kl_list.bi_list:
                bi.pre = last_bi
                if last_bi:
                    last_bi.next = bi
                last_bi = bi
            for seg in kl_list.seg_list:
                seg.pre = last_seg
                if last_seg:
                    last_seg.next = seg
                last_seg = seg
            for segseg in kl_list.segseg_list:
                segseg.pre = last_segseg
                if last_segseg:
                    last_segseg.next = segseg
                last_segseg = segseg

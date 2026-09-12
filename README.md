# chansdk - 缠论核心算法 SDK

纯 Python 实现的缠论（Chan Theory）核心算法库，零外部依赖。

## 功能

- **K线合并**：包含关系处理、分型识别
- **笔（Bi）**：笔的构建、验证、MACD度量
- **线段（Seg）**：特征序列法、1+1算法、break算法
- **中枢（ZS）**：中枢构建、合并、背驰判断
- **买卖点（BSP）**：1/1p/2/2s/3a/3b 六类买卖点识别
- **技术指标**：MACD、BOLL、RSI、KDJ、Demark、趋势线
- **多级别分析**：支持多级别K线联动分析

## 安装

```bash
# 基础安装（零依赖）
pip install chansdk

# 带 eltdx 数据源（Rust实现，支持复权）
pip install chansdk[eltdx]

# 开发依赖（pytest、build）
pip install chansdk[dev]
```

## 数据源

SDK 内置三种数据源，并支持自定义数据源：

| 数据源 | 说明 |
|---|---|
| `DATA_SRC.ELTDX` | 通达信行情（需 `pip install chansdk[eltdx]`，Rust 实现，支持复权） |
| `DATA_SRC.CSV` | 本地 CSV 文件（零依赖，始终可用） |
| `DATA_SRC.CACHE_DB` | 本地 SQLite 缓存库（默认读取 `chan.db` 的 `kline_data` 表） |
| `custom:module.ClassName` | 自定义数据源（见下文） |

未显式传入 `data_src` 时，SDK 按以下顺序选择已安装的数据源：`eltdx` -> `CSV`。
显式传入 `DATA_SRC` 或自定义数据源时，按指定数据源执行。

## 快速开始

```python
# docs: run
import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from chan import CChan, KL_TYPE, DATA_SRC

with TemporaryDirectory() as temp_dir:
    csv_path = Path(temp_dir) / "000001_day.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_key", "open", "high", "low", "close"])
        writer.writerows(
            [
                ["2024-01-01", 10, 12, 9, 11],
                ["2024-01-02", 11, 13, 10, 12],
                ["2024-01-03", 12, 14, 11, 13],
            ]
        )

    chan = CChan(
        code="000001",
        begin_time="2024-01-01",
        end_time="2024-01-03",
        data_src=DATA_SRC.CSV,
        lv_list=[KL_TYPE.K_DAY],
        file_path=str(csv_path),
    )

    kline_list = chan[KL_TYPE.K_DAY]
    print(f"笔数量: {len(kline_list.bi_list)}")
    print(f"线段数量: {len(kline_list.seg_list)}")
    print(f"中枢数量: {len(kline_list.zs_list)}")
    print(f"买卖点数量: {len(kline_list.bs_point_lst)}")
```

### eltdx 数据源（推荐的外部行情源）

`eltdx` 是基于 Rust 实现的通达信行情客户端，支持服务端复权和 43 台主站自动测速：

```python
# docs: eltdx
from chan import CChan, KL_TYPE, DATA_SRC, AUTYPE

# 前复权（默认）
chan = CChan(
    code="600519",
    data_src=DATA_SRC.ELTDX,
    autype=AUTYPE.QFQ,
    lv_list=[KL_TYPE.K_DAY],
)

# 后复权
chan = CChan(
    code="600519",
    data_src=DATA_SRC.ELTDX,
    autype=AUTYPE.HFQ,
    lv_list=[KL_TYPE.K_DAY],
)

# 定点复权（需要 eltdx >= 3.0）
chan = CChan(
    code="600519",
    data_src=DATA_SRC.ELTDX,
    autype=AUTYPE.QFQ,
    lv_list=[KL_TYPE.K_DAY],
    anchor_date="2024-06-03",
)
```

eltdx 特性：
- 支持 `AUTYPE.QFQ`（前复权）、`AUTYPE.HFQ`（后复权）、`AUTYPE.NONE`（未复权）
- 支持定点复权（`anchor_date` 参数）
- 支持 1/5/15/30/60 分钟、日/周/月/季/年线
- Rust 实现，43 台候选主站自动测速
- 生产级稳定性（Production/Stable）
- 零 Python 运行时依赖
- 许可证：仅允许个人学习和非商业研究

> 注意：eltdx 许可证禁止商业使用。外部行情服务可能受网络、服务端限流或历史数据边界影响，生产灰度建议先限制标的数量和时间窗口，并记录 `CChanException` 的错误信息。

## 灰度探测

仓库提供可重复执行的串行灰度脚本。默认只验证本地 CSV 和 SQLite 链路：

```bash
python scripts/gray_probe.py
```

需要探测外部行情源时显式开启，并限制超时：

```bash
python scripts/gray_probe.py --include-external --begin 2025-01-02 --end 2025-01-10
```

保存灰度报告：

```bash
python scripts/gray_probe.py --json-out build/release/gray_probe.json
```

脚本输出 JSON 结果，外部服务不可用时返回非零退出码，不会把失败伪装成空数据成功。

发布前一键检查：

```bash
python scripts/verify_release.py
```

默认执行测试、编译、文档示例、本地灰度、wheel 构建和隔离导入，并将报告写入 `build/release/release_report.json`。

单独校验 README 代码块：

```bash
python scripts/verify_docs.py --run-marked --json-out build/release/docs_report.json
```

## 使用自定义数据源

如果需要接入其他行情服务，可按下方接口实现自定义数据源。

```python
# docs: skeleton
from chan import CChan, KL_TYPE
from chan.data.base import CCommonStockApi

class MyDataAPI(CCommonStockApi):
    def SetBasciInfo(self):
        self.name = self.code
        self.is_stock = True

    @classmethod
    def do_init(cls):
        # 初始化连接
        pass

    @classmethod
    def do_close(cls):
        # 释放连接
        pass

    def get_kl_data(self):
        # 返回 CKLine_Unit 可迭代对象
        pass

chan = CChan(
    code="my_stock",
    data_src="custom:my_module.MyDataAPI",
    lv_list=[KL_TYPE.K_DAY],
)
```

## API 参考

### CChan

```python
# docs: reference
CChan(
    code: str,                    # 股票代码
    begin_time: str = None,       # 开始时间
    end_time: str = None,         # 结束时间
    data_src: DATA_SRC = ...,     # 数据源
    lv_list: List[KL_TYPE] = ..., # 分析级别
    config: CChanConfig = None,   # 配置
    autype: AUTYPE = ...,         # 复权类型
    **kwargs                      # 传递给数据源的参数
)
```

### CChanConfig

```python
# docs: run
from chan import CChanConfig

config = CChanConfig()
config.bi_conf.bi_algo = "peak"  # 笔算法
config.seg_conf.seg_algo = "chan"  # 线段算法
```

`trigger_step=True`（逐步回放）时，每一步默认产出一份深拷贝快照。可通过 `snapshot_step` 调整快照频率以降低开销：

```python
# docs: run
from chan import CChanConfig

config = CChanConfig({
    "trigger_step": True,
    "snapshot_step": 10,  # 每 10 步产出一次深拷贝快照；0 表示不做深拷贝，直接产出实时对象（调用方不应持有引用）
})
```

## 许可证

MIT License

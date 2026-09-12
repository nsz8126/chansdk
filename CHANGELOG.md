# Changelog

本文件记录 chansdk 的版本变更，版本号遵循语义化版本（SemVer）。

## 1.0.2 - 2026-09-12

文档与包元数据修正版本，无算法与 API 变更。

### 变更

- 重写 CHANGELOG：移除代码中不存在的 `Akshare`/`Pytdx` 数据源描述，补全 1.0.1 实际发布内容。
- README 补充 PyPI / CI / 许可证徽章、示例文件清单、国内镜像安装提示、`scripts/` 脚本清单。
- README 措辞修正：线段算法标注 `1+1`、`break` 已弃用；数据源描述由「内置三种」修正为「内置两种零依赖数据源 + 可选外部源」。
- 新增 `LICENSE`（MIT），并纳入 MANIFEST.in 与打包产物。
- `pyproject.toml` 补充 `keywords`、`classifiers` 与 `[project.urls]`，完善 PyPI 项目页信息。
- 测试 `test_project_version_is_declared` 由硬编码版本号改为 SemVer 格式校验，避免每次发版都需改测试。

## 1.0.1 - 2026-09-12

首个公开版本，已发布至 PyPI（`pip install chansdk`）与 GitHub Release。

### 功能

- **K 线合并**：包含关系处理、分型识别。
- **笔（Bi）**：构建与验证，支持 `peak` 等笔算法，附带 MACD 度量。
- **线段（Seg）**：默认 `chan`（特征序列法）算法；`1+1`、`break` 为已弃用算法，调用时给出 `DeprecationWarning`。
- **中枢（ZS）**：中枢构建、合并与背驰判断。
- **买卖点（BSP）**：1/1p/2/2s/3a/3b 六类买卖点识别。
- **技术指标**：MACD、BOLL、RSI、KDJ、Demark、趋势线。
- **多级别分析**：多级别 K 线联立计算，支持 `trigger_step` 逐步回放。

### 数据源

- 支持 `DATA_SRC.CSV`（本地 CSV）、`DATA_SRC.CACHE_DB`（本地 SQLite）、`custom:module.ClassName`（自定义数据源）。
- `DATA_SRC.ELTDX` 为可选扩展，需 `pip install chansdk[eltdx]`。
- 未显式指定时，按 `eltdx -> CSV` 顺序选择已安装的数据源。

### 修复

- 修复 `CKLine_Unit.__deepcopy__` 在未调用 `set_metric()` 时访问 `macd`/`boll` 抛 `AttributeError` 的问题：恢复属性初始化。
- 修复 `CChan.chan_dump_pickle()` 缺少异常保护的问题：改为 `try/finally`，序列化失败时保证恢复 `pre`/`next` 引用链与递归深度上限。
- 修复 18 个源文件、125 行因编码转换错误产生的注释乱码（gb18030 逆向还原）。
- 修正异常信息拼写错误（`unspoourt` → `unsupport`、`algoright` → `algorithm`）。
- 删除 `CChan.load()` 中 `except Exception: raise` 冗余分支。
- 修复 SQLite 数据源连接未显式关闭的问题。
- 修复 CSV 日期过滤对 `YYYY-MM-DD` 与 `YYYY/MM/DD` 混用的兼容性问题。
- 修复多级别对齐、`step_load` 快照隔离、Demark 配置污染、MACD 除零和趋势线垂直距离问题。
- 移除配置加载中的动态 `exec`，增加配置参数校验。

### 优化

- `CChanConfig` 新增 `snapshot_step` 参数，用于调节 `trigger_step` 逐步回放的快照频率：默认 `1`（每步深拷贝，保持兼容）；`10` 表示每 10 步快照一次；`0` 表示不深拷贝、直接产出实时对象。1000 根日线实测由 18.44s 降至 0.24s（约 77 倍）。
- 弃用提示由 `print` 改为标准 `warnings.warn(DeprecationWarning)`，便于调用方过滤。
- 压缩 `chan/chan.py` 冗余空行（799 → 413 行），纯格式调整，无行为变化。

### 文档与工程化

- README 与实际支持的数据源对齐，移除代码中不存在的 `tdxrs`/`tdx-python`/`pytdxdata` 说明。
- 新增 `.gitignore`（排除 `__pycache__`、`build/`、`dist/`、`*.egg-info`、`chan.db` 等）。
- 新增 GitHub Actions CI：Python 3.11–3.13 矩阵，执行 pytest 与 README 代码块校验。
- 新增 `scripts/verify_release.py` 发布门禁：串联测试、编译、文档示例、本地灰度、wheel 构建与隔离导入检查。
- 新增 `scripts/verify_docs.py` README 代码块编译与执行校验。
- 新增 `scripts/gray_probe.py` 可重复执行的串行灰度探测脚本。
- 新增 `scripts/fix_mojibake.py` 注释乱码检测与修复工具。

### 质量

- 111 个单元/集成测试全部通过。
- wheel 与 sdist 在干净虚拟环境安装并通过端到端冒烟测试。

### 已知限制

- 外部数据源 `eltdx` 的许可证仅允许个人学习与非商业研究。
- `chan_dump_pickle` 序列化的是对象图：类结构变更后旧文件不可加载，且仅应加载可信文件。如需长期持久化，建议改用 schema 化的 dict/JSON 导出。

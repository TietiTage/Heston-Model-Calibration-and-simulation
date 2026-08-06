# progress.md — 项目进度记录

> 依据 `code/AGENTS.md` 要求，在完成较大结构改动后记录更新与项目进展，并同步推送到本地 git 仓库。

## 2026-08-06 初始化项目文档并重写依赖

### 本次改动

1. **新增 `summary_proj.md`（项目文档）**
   - 首次读取项目目录后按 `code/AGENTS.md` 要求生成，UTF-8 编码。
   - 内容包含：目录结构与文件清单；数据文件格式（列、类型、编码）；各源码文件的格式、内容构成、类构成、函数输入输出与主要作用、变量类型；命名风格与编码规范；环境与运行说明。（流程图与 ER 图章节已移出，独立存放。）

2. **新增 `project_design.md`（设计辅助文档）**
   - 依据 `code/AGENTS.md` 对“流程图、ER 图等辅助文档”的要求，将从 `summary_proj.md` 移出的内容独立成文。
   - 包含四张流程图（总体数据流、单日校准两阶段优化与回退策略、定价验证、希腊字母分析）与一张数据实体关系 ER 图。
   - `summary_proj.md` 文档头已加入指向该文档的说明。

3. **重写 `requirements.txt`**
   - 原文件为 `pip freeze` 导出结果（UTF-16 编码，含大量 `file:///` 本地 conda 构建路径，无法在其他环境直接安装）。
   - 重写为 UTF-8、可直接 `pip install -r requirements.txt` 安装的清单，仅保留项目直接导入的依赖并固定版本（与 `data_process` 虚拟环境一致）：
     `numpy==1.26.4`、`pandas==2.2.3`、`scipy==1.16.0`、`QuantLib==1.42`、`akshare==1.18.56`、`matplotlib==3.8.4`、`seaborn==0.13.2`、`scikit-learn==1.5.1`。

### 项目当前状态

- 核心模块（数据处理、Heston 校准、定价验证、希腊字母分析）已可运行，`code/main.ipynb` 为总入口。
- 校准输出 `output/calibrated_params_daily.csv`、定价对比与希腊字母 CSV、论文图表 PDF 均已生成。
- 待办/注意事项：
  - `code/main.ipynb` 中希腊字母相关 cell 曾出现报错，需要进一步排查（notebook cell 19 备注）。
  - 完整 2025 年数据校准约 3 小时，复现时可加载 `code/processor.pkl` 跳过校准。

### 关联文件

- `code/AGENTS.md`：Agent 工作偏好（用户指示，禁止修改）。
- `readme.md`：项目总结文档（已合并原 summary_proj.md 内容）。
- `docs/project_design.md`：设计辅助文档（流程图）。
- `index.html` / `start_docs.bat`：统一本地文档入口与一键打开脚本。
- `requirements.txt`：重写后的依赖清单。

## 2026-08-07 按新版 AGENTS.md 重构文档（MkDocs 化）

### 背景

用户更新了 `code/AGENTS.md`，新要求：文档统一存放在与 `code/` 同级的文件夹并使用 MkDocs 创建维护；`summary_proj.md` 聚焦文件职能、模块依赖、数据流向、算法选择与设计思想；类的构成、函数输入输出、变量类型改由 API 文档承载；py 代码必须使用 typehint 并为函数/类编写 docstring。

### 本次改动

1. **新建 MkDocs 站点骨架**
   - 新增 `mkdocs.yml`（readthedocs 主题、中文、mkdocstrings 插件、`paths: [code]`）。
   - 新增 `docs/index.md` 首页与 `docs/api/*.md`（data_process / data_processor / model_calibrator / pricing_verification / greeks_analysis 五个 API 参考页）。
   - `docs/summary_proj.md`、`docs/project_design.md` 由项目根目录移入 `docs/`（git mv 保留历史）。
   - 安装 mkdocstrings / mkdocstrings-python / pymdown-extensions（虚拟环境 data_process），`mkdocs build` 构建成功。

2. **重写 `docs/summary_proj.md`**
   - 按新 AGENTS.md 调整定位：每个文件的职能、模块依赖、数据流向、算法选择与设计思想；删除类/函数明细表（改由 API 文档承载）。
   - 保留并更新数据文件格式、命名规范、环境说明等章节。

3. **补齐 py 代码 docstring 与类型注解**
   - data_process.py：函数类型注解与返回类型、`get_expiry` docstring；
   - data_processor.py：类 docstring、`short_term_filter` 注解与 docstring；
   - model_calibrator.py：dataclass/TypedDict/docstring、`calibrate` 参数注解、`_loss_function` 注解；
   - pricing_verification.py：各定价器类与方法 docstring、`compare_pricing_on_date` 完整注解与 docstring、`BlackScholesPricer.price` 注解；
   - greeks_analysis.py：TypedDict 与类 docstring、`update_spot` 注解。
   - 均为文档性变更（无逻辑改动），`py_compile` 与 `mkdocs build` 均通过。

4. **配套更新**
   - `readme.md`：目录结构加入 `docs/` 与 `mkdocs.yml`，新增“文档”章节。
   - 新增 `.gitignore`：忽略 `site/`、`__pycache__/`、`*.pyc`。

### 待办 / 说明

- `code/` 下若干 .py 与 `main.ipynb` 仍包含用户未提交的修改（含本次 docstring 补充）。按 AGENTS.md“逻辑代码改变需先通过 pytest 再推送”的要求，本次未将这些代码改动提交；`tests/` 目录尚未建立。
- `site/` 为 mkdocs 构建产物，已加入 .gitignore。

## 2026-08-07 提交核心代码并建立 pytest 测试套件

### 本次改动

1. **提交五个核心 py 文件**
   - 用户确认五个核心 py 文件（data_process / data_processor / model_calibrator / pricing_verification / greeks_analysis）可以提交。
   - 除 docstring 与类型注解外，工作区相对上次提交还包含：`prior_v0_center` 元组括号 bug 修复（`(max(atm_iv), 0.05)**2` → `max(atm_iv, 0.05)**2`），以及校准过滤逻辑去重（`run_daily_calibration` 内嵌 `apply_filter` 替换为共享的 `filter_calibration_options`）。

2. **新增 pytest 测试套件（36 个用例，全部通过）**
   - 新增 `pytest.ini` 与 `tests/`（conftest.py + 5 个 `test_<模块名>.py`），测试数据取自 `data/`。
   - 覆盖：合约解析与到期日（test_data_process）；数据清洗、现货/股息率/利率插值、BS 隐含波动率与统一过滤（test_data_processor）；Heston 参数集合、BS 先验、helpers 构建、单期权定价与误差计算（test_model_calibrator）；BS 公式对照 QuantLib、平价关系、Heston 半解析与 MC 一致性（test_pricing_verification）；希腊字母计算、spot 更新与动态分析（test_greeks_analysis）。
   - 说明：完整的 `calibrate()`（DE + L-BFGS-B）计算量过大，未放入单元测试，其核心路径以组件级测试覆盖。
   - 环境：在 data_process 虚拟环境安装 pytest 9.1.1；运行 `pytest`（或 `python -m pytest`）3.6 秒通过。

3. **配套更新**
   - `readme.md` 与 `docs/` 增加测试章节与 tests/ 目录说明。

### 待办 / 说明

- `code/main.ipynb` 仍保留用户未提交的修改，本次未提交。

## 2026-08-07 删除 ER 图并同步相关文档

### 本次改动

1. 用户删除 `docs/project_design.md` 中不必要的 ER 图章节（原第 2 节）。
2. 同步更新引用 ER 图的文档：
   - `docs/project_design.md`：标题与说明改为“设计辅助文档（流程图）”，移除随 ER 图遗留的“期权记录为核心实体”说明段；
   - `mkdocs.yml`：导航标签改为“设计文档（流程图）”；
   - `docs/index.md`：导航表与目录结构中的 ER 图字样去除；
   - `docs/summary_proj.md`：文档头与文件职能表中的 ER 图字样去除；
   - `readme.md`：目录结构与文档说明中的 ER 图字样去除。

### 说明

- 设计辅助文档现仅保留四张流程图（总体数据流、单日校准、定价验证、希腊字母分析）。

## 2026-08-07 合并 summary_proj 至 readme 并重构本地文档入口

### 本次改动

1. **合并 `summary_proj.md` 到 `readme.md`，消除冗余**
   - 原 `docs/summary_proj.md` 的文件职能、模块依赖、数据流向、算法选择与设计思想、数据文件格式、命名规范等内容全部并入根目录 `readme.md`（并保留原有环境/运行/注意事项等章节，去重合并“核心模块说明”）。
   - 删除 `docs/summary_proj.md`；MkDocs 导航移除“项目总结”页。

2. **重构网页阅览方式，提供统一本地入口（与 readme 同级）**
   - 新增根目录 `index.html`：统一入口页（自包含样式），汇总链接项目总结、设计文档、MkDocs 站点与 5 个 API 参考页。
   - 新增根目录 `start_docs.bat`：一键构建 MkDocs 站点并打开入口页。
   - `docs/index.md` 精简为 MkDocs 站点导航首页；`mkdocs.yml` 导航改为：首页 / 设计文档（流程图）/ API 参考。

3. **配套更新**
   - `docs/project_design.md`：项目整体说明指向根目录 `readme.md`。

### 说明

- `site/` 为 mkdocs 构建产物（已 gitignore），首次使用请先运行 `start_docs.bat` 或 `mkdocs build`。

## 2026-08-07 代码审查整改：提交工作区改动并清理仓库产物

### 本次改动

1. **提交此前未提交的工作区改动**
   - `main.ipynb`：相对路径硬编码改用 `pathlib`；`PROJECT_ROOT` 兼容从仓库根目录或 `code/` 启动两种情况。
   - 五个核心 py 文件 docstring 统一为 numpy 风格（`Parameters` / `Returns`）。
   - `pytest` 36 用例全部通过。
2. **修复 `index.html`**
   - 恢复卡片浅色背景（此前误改为深色导致文字不可读）。
   - 文档/API 链接从已 gitignore 的 `site/` 构建产物改为 `docs/` 源文件，GitHub 上可直接渲染。
3. **停止跟踪运行产物（`git rm --cached`，本地文件保留）**
   - `code/processor.pkl`、`code/calibration_options.csv`、`code/2025-04-01-pricing_comparison.csv`、`code/greeks_dynamics_C3900_20250620.csv`。
   - `.gitignore` 新增 `code/*.csv`、`code/processor.pkl`、`.pytest_cache/`。
4. **仓库卫生**
   - 新增 `.gitattributes`（`text=auto`、notebook LF、图片/PDF 二进制）。
   - `start_docs.bat`：优先使用 `data_process` 环境，缺失时回退到 PATH 中的 `python`。
   - `readme.md`：注明输出文件由 notebook 生成且不入版本库。

### 说明

- `processor.pkl` 与生成 CSV 仅停止跟踪（本地文件保留），历史提交中的体积未做重写。

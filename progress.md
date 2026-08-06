# progress.md — 项目进度记录

> 依据 `code/AGENTS.md` 要求，在完成较大结构改动后记录更新与项目进展，并同步推送到本地 git 仓库。

## 2026-08-06 初始化项目文档并重写依赖

### 本次改动

1. **新增 `summary_proj.md`（项目文档）**
   - 首次读取项目目录后按 `code/AGENTS.md` 要求生成，UTF-8 编码。
   - 内容包含：目录结构与文件清单；数据文件格式（列、类型、编码）；各源码文件的格式、内容构成、类构成、函数输入输出与主要作用、变量类型；总体数据处理流程、单日校准（两阶段优化 + 回退策略）、定价验证、希腊字母分析四张流程图；数据实体关系 ER 图；命名风格与编码规范；环境与运行说明。

2. **重写 `requirements.txt`**
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
- `summary_proj.md`：项目详细文档。
- `requirements.txt`：重写后的依赖清单。

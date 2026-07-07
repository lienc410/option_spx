# SPEC-128 — Book 账本全链路迁入前端系统（Drive → native）

**PM 决策（2026-07-06）**：把家庭合伙账本的整套数据链与计算逻辑从 Google Drive
Excel（Partnership_Shares_v3.5，20 表 ~1,290 公式）迁入本系统，成为**唯一真值源**。
Drive 表冻结为只读归档。触发背景：7/6 Book 页 env 竞态事故暴露外部依赖链
（Drive SA + 本地 xlsx 双缺任一即不可用）；迁入后消除 Drive/SA/xlsx 三个运行时依赖。

**设计原则**（house 纪律）：
- 迁移方向是**消灭双真值**——Excel 引擎退役，Python 引擎接管；迁移时刻用 Excel 的
  data_only 缓存值做**逐分 parity 验收**（现成 oracle：`read_book()` 解析的输出）。
- 输入数据 = PII → `data/book/`（gitignore；随 F-1 备份链：L1 日拉 + L2 周归档）。
- 事件账本 append-only + void/correction 事件（同 trade_log 纪律，H-3 lessons）。
- 引擎 = 输入 JSONL 的纯函数；重算幂等；写后即时重算并回传六项校验。

## 1. 数据模型（data/book/，全部 gitignore）

| 文件 | 内容 | 事件 |
|---|---|---|
| `config.json` | 成员+别名（Xinzhong≡CXZ）、池定义、ET 并入常数（2026-06-01：Lien base 339,348.13 "option B"；CXZ 份额基 298,551/个人成本基 207,907）、Lien TWR-since-2025 口径、guarantees 条款 | 静态 |
| `sw_snapshots.jsonl` / `et_snapshots.jsonl` | `{id, event, date, total, note, closed}` | `snapshot`/`void` |
| `sw_cashledger.jsonl` / `et_cashledger.jsonl` | 11 列（snapshot_date/bank_date/partner/from/to/amount/fee/instrument/counts/type/note）+ id | `flow`/`void` |
| `cxz_etrade.jsonl` / `lien_etrade.jsonl` | `mark`（月/季市值）、`flow_year`（年度净流水）| 同上 |

## 2. 引擎 `web/book_engine.py`

纯函数 `compute_book(data_dir)` → payload **与现 `read_book()` 完全同构**（members/
total/aum/by_year/etrade_pool/etrade_by_year/member_statements/reconciled）外加
`recon_checks`（六项）、`guarantees`、`subaccounts`、`source:"native"`。

复刻（引用 v3.5 SPEC 章节）：
- **池引擎**（SW/ET 同构，§3.2/3.3）：快照定期间；每期每人净流水 = Σ(Counts=Yes,
  Contribution) − Σ(Distribution)；期间 P&L = ΔV − 净流入，按**期初份额**分摊；
  NAV/unit 基 100 期末定价。
- **汇总**：净投入/累计 P&L/现值/份额%/Simple/**XIRR**（bisection）/年度 TWR + 各人年度 P&L。
- **子账户待转**：CXZ-481 / Koching-276 的 Counts=No 进出轧差（应为 0）。
- **六项校验**（§SW_Reconciliation）：余额和=快照总值 / 份额和=100% / P&L 分摊和=期间
  P&L / 无负余额 / Summary 勾稽 / 子账户非负——任一红即 payload 标红。
- **Guarantees**：floor = basis×(1+hurdle) vs 实际值。
- **个人序列**：CXZ 6842 逐年（年末−年初−净流水）；Lien PM 逐年 + 自 2025 TWR 连乘
  （含"2024 数据不全"标注）。
- **Consolidation / Member_Statement**：池 + 个人序列拼装。

**Phase 2（DEFERRED 注册，不在本批）**：Flow_Recon 对账单收入录入、Portfolio_Risk、
券商流水自动抓取+Counts/Type/Partner 分类规则引擎（v3.5 §7.2）、快照自动采集。

## 3. 迁移 `scripts/book_migrate_from_xlsx.py`（本机执行，xlsx 只在本机）

1. 输入表逐行抽取 → JSONL + config。
2. **Parity gate（不过不落 marker）**：`compute_book()` vs xlsx oracle 逐字段——
   金额 ±$0.01、比例 ±0.01pp、XIRR/TWR ±0.05pp。
3. 交叉核对 v3.5 §9 锚点（AUM $1,265,104 等）。
4. 落 `data/book/.migrated`（记 oracle 哈希）→ rsync → oldair。

## 4. API / UI

- **读**：`/api/partnership/book` → `data/book/` 存在走 native；否则回退旧链（过渡保命）。
- **写**（append-only；closed 快照期写入 → 409）：
  `POST .../book/snapshot`、`.../book/flow`、`.../book/mark`、`.../book/void`。
  写后即时重算，响应携带六项校验（红则提示，不拦截——Counts/Type/Partner 的业务判断
  保持人工，表单只是结构化）。
- **UI（partnership.html，中文豁免页）**：现有展示不动 + source badge；六项校验状态行 +
  Guarantees 行；「+ 记快照 / + 记资金流 / + 记个人市值」三个 modal；行级 void 入口。

## 5. Cutover / 运维

- parity 绿 → **PM 把 Drive 表改名 `_archive`**（其归档约定）；SA env 保留（importer
  兜底）；旧读链保留一个版本周期后删。
- 备份：oldair `data/book/**` 自动入 F-1 L1/L2（验证 pattern 覆盖子目录）。
- 无新定时任务；payload 按输入 mtime 缓存。

## 6. AC

1. **Parity**：native vs xlsx oracle 全字段（§3.2 容差），migration 硬门。
2. **锚点**：v3.5 §9 关键数字直接断言（AUM/份额/TWR/个人年度收益率）。
3. 六项校验迁移数据全绿；注入坏行（负余额/份额≠100%）各触发对应红（否定测试）。
4. 写流程：POST→重算→可读；void 回滚；closed 期 409；append-only（文件只增）断言。
5. 回退：`data/book/` 缺失时旧链完整可用。
6. PII：CI 断言 `data/book/` gitignored 且 repo 内无账本 JSONL。
7. XIRR 与 Excel 对拍（全成员 ±0.05pp）。
8. oldair 部署后 Book 页 native 渲染 + 写表单冒烟。

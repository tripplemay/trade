# AI 量化交易系统 MVP PRD

## 1. 产品背景

本项目目标是研发一个由 AI 驱动的全球证券市场量化交易系统。当前阶段面向个人自用，未来在策略、数据、风控、交易和合规能力成熟后，再评估是否产品化给外部客户。

项目已完成两类基础规划：

- B001：策略研发路线图，明确全球 ETF 动量、风险平价、美股质量动量、港股/中国 ETF 小仓位、AI 新闻/公告风控五个策略方向。
- B002：数据源、券商适配、数据模型、point-in-time 和环境隔离规格。

MVP 的职责是把这些规划收敛成第一阶段可交付产品边界，避免工程基线和回测实现偏离产品目标。

## 2. 用户画像

首期用户：项目所有者本人。

特征：

- 个人账户资金规模：USD 100k-500k。
- 关注美股、港股和全球 ETF。
- 偏好低频、稳健、可解释策略。
- 允许采购必要数据，但不希望一开始被机构级数据成本绑定。
- 先自用，成熟后再考虑对外服务。

非首期用户：

- 多用户 SaaS 客户。
- 外部资金委托客户。
- 高频交易团队。
- 期权或复杂衍生品交易员。

## 3. MVP 目标

MVP 目标：

> 建立一个可复现、可测试、可审计的低频量化研究与回测系统，首期支持全球 ETF 动量轮动策略的端到端研究闭环，并为后续风险平价、Paper Trading 和券商适配打好工程基础。

MVP 成功后，系统应能回答：

- 是否能基于标准化 ETF 数据生成策略信号？
- 是否能按 T 日收盘信号、T+1 执行假设完成回测？
- 是否能输出可信的绩效报告？
- 是否能记录参数、数据快照和结果，保证回测可复现？
- 是否能在不连接真实券商、不使用真实资金的情况下验证核心策略逻辑？

## 4. MVP 范围

### 4.1 产品范围

MVP 包含：

- 工程基础：Python 包结构、配置、测试、CI。
- 数据层：本地/fixture 数据接口、ETF 日线数据 schema、数据质量检查规则。
- 策略层：全球 ETF 动量轮动策略基准版本。
- 回测层：低频月度调仓回测。
- 报告层：JSON/Markdown 回测报告。
- 风控层：基础仓位上限、趋势过滤、防守资产规则。
- 审计层：参数、数据快照、运行结果可追踪。
- AI 边界：仅作为后续风险解释和报告增强，不进入 MVP 自动决策。

### 4.2 策略范围

MVP 只实现：

- 全球 ETF 动量轮动策略。

作为文档和后续规划保留：

- 风险平价 / 波动率目标。
- 美股质量动量 / 多因子。
- 港股/中国 ETF 小仓位。
- AI 新闻/公告风控。

MVP 不实现这些后续策略的实盘或完整回测。

### 4.3 数据范围

MVP 数据范围：

- ETF 主数据。
- 日线 OHLCV。
- 复权收盘价。
- 公司行为。
- 交易日历。
- 防守资产数据。
- 小型测试 fixture。

MVP 不强依赖：

- 机构级数据源。
- 真实券商 API。
- 实时行情。
- tick 数据。
- Level 2 订单簿。
- 完整基本面数据库。

### 4.4 回测范围

MVP 回测必须支持：

- 月度调仓。
- T 日收盘生成信号。
- T+1 执行假设。
- 交易成本和滑点参数。
- 防守资产切换。
- Top N 持仓。
- 等权 + 风险上限。
- 基准对比。

必须输出：

- 净值曲线数据。
- 年化收益。
- 年化波动率。
- Sharpe。
- 最大回撤。
- 换手率。
- 月度/年度收益。
- 当前参数和数据快照 ID。

### 4.5 Paper Trading 范围

MVP 不实现真实 paper broker API。

MVP 只为后续 Paper Trading 做准备：

- 目标仓位输出格式。
- 策略配置格式。
- 回测报告格式。
- Broker Adapter 接口文档引用。

Paper Trading 作为后续批次实现。

## 5. 非 MVP 范围

MVP 明确不包含：

- 真实资金自动交易。
- live broker 下单。
- IBKR/Alpaca/Futu/Tiger 实际 API 接入。
- 多用户系统。
- 外部客户产品化。
- 完整前端 dashboard。
- 云端生产部署。
- 高频交易。
- 期权策略。
- 杠杆 ETF 和反向 ETF。
- 复杂衍生品。
- 完整美股多因子生产系统。
- AI 自动下单。
- AI 自动修改策略参数。
- 机构级数据作为硬依赖。

## 6. 核心用户流程

### 6.1 数据准备流程

用户目标：准备可回测的 ETF 历史数据。

流程：

1. 配置 ETF universe。
2. 准备本地 fixture 或历史数据文件。
3. 运行数据加载。
4. 执行数据质量检查。
5. 生成数据快照 ID。

验收：数据质量检查通过，数据快照可追踪。

### 6.2 策略配置流程

用户目标：配置全球 ETF 动量策略参数。

流程：

1. 选择 ETF universe。
2. 设置动量窗口和权重。
3. 设置趋势过滤。
4. 设置 Top N。
5. 设置防守资产。
6. 设置交易成本和调仓频率。

验收：策略参数被结构化保存，不散落在代码中。

### 6.3 回测执行流程

用户目标：执行一次可复现回测。

流程：

1. 选择策略配置。
2. 选择数据快照。
3. 运行回测。
4. 生成结果对象。
5. 保存报告。

验收：相同配置和数据快照可复现相同结果。

### 6.4 报告查看流程

用户目标：理解策略表现。

流程：

1. 查看核心指标。
2. 查看基准对比。
3. 查看回撤。
4. 查看换手率和交易成本。
5. 查看仓位历史。

MVP 输出 Markdown/JSON 报告，不实现正式前端 dashboard。

### 6.5 风控检查流程

用户目标：确认策略是否违反基础风控。

流程：

1. 检查单 ETF 上限。
2. 检查港股/中国上限。
3. 检查商品/高收益债上限。
4. 检查趋势过滤。
5. 检查防守资产切换。

验收：违反风控时回测或报告必须显式标记。

### 6.6 Paper Trading 准备流程

用户目标：为后续模拟交易准备目标仓位格式。

流程：

1. 从策略生成目标权重。
2. 输出目标仓位文件。
3. 记录信号日期。
4. 等待后续 Paper Trading 批次消费。

验收：不连接真实 broker，只输出可审计目标仓位。

## 7. 前端边界

> 2026-05-15 修订：MVP 完工路径包含一个本地 graphical workbench。原 §7 文本（"MVP 不实现正式前端 dashboard"）已被推翻，理由是当时引用的 4 条阻塞原因中 3 条已通过 B007 / B009 / B010 / B011 / B012 解决（回测 schema、策略配置 schema、数据质量输出均已稳定），第 4 条（execution 层 schema 不稳）通过 Phase 1 / Phase 2 拆分被规避（execution 工作流推迟到 Phase 2）。完整背景见 `docs/adr/2026-05-15-workbench-direction.md`。

### Workbench 路径（cloud-deployed multi-device addendum 2026-05-15）

> 二次修订：原 §7 (commit `522e34a`) 描述 workbench 为 localhost-only 单机应用。用户后续要求**多设备访问**（笔记本 + 手机 + iPad），决定 deploy 到现有 GCP VM (`trade.guangai.ai`) 加 Google OAuth gating。完整背景见 ADR `docs/adr/2026-05-15-workbench-direction.md` §"Addendum 2026-05-15 — Cloud Deploy Pivot + Renumber"。

- **B020 Dev Infrastructure**（5 features，~1.5 周）：workbench skeleton + Python/Node 工具链 + CI workflows + 测试策略 + 安全 guard 脚手架 + OpenAPI ↔ TS pipeline + 文档。无云依赖，纯本地 dev tooling。
- **B021 Cloud Deploy & Auth Infrastructure**（6 features，~2-3 周）：Google OAuth (NextAuth + 后端验证 + 单 email allowlist) + SQLite + Alembic + Repository 数据层 + Dockerfile + systemd + nginx vhost + cert (certbot for trade.guangai.ai) + CI/CD (GitHub Actions push→SSH deploy→health check→rollback) + 备份 (SQLite snapshot → GCS) + 可观测性 (healthcheck + 结构化 log)。
- **B022 Workbench Phase 1**（14 features，~5-6 周）：FastAPI + Next.js 15 + TypeScript + shadcn/ui + Tailwind + AG Grid Community + TradingView lightweight-charts + ECharts；read-mostly 7 页（Home / Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog）+ 最小必要 write 操作（snapshot refresh / backlog CRUD / 触发 backtest / 导出 target positions Markdown）。
- **B023 Workbench Phase 2**：在 Phase 1 之上加 manual execution UI（target positions diff / order ticket / fill journal）。
- 部署位置：用户已有 GCP VM（与 aigcgateway 共住）；resource quota via systemd `CPUQuota=200%` + `MemoryMax=2G` 隔离。
- 公网访问：仅 `https://trade.guangai.ai`，OAuth allowlist 单 email；非 allowlisted user 拒绝。
- 安全约束保持：不引入 broker SDK / paper API / live endpoint；不存付费行情；下单永远由用户在券商客户端手动完成。

### Workbench 与 CLI 并行

- 报告文件依旧落 Markdown / JSON / CSV，CLI 入口完整保留以支持自动化、CI、headless 复现；
- 工作台是用户可发现性的主要 surface，CLI 是可重现性、自动化与 audit 的主要 surface；
- 任何在工作台中可触发的操作必须有等价的 CLI 命令。

### 仍属非 MVP（PRD §5 范围）

- 自动连接 broker / paper API（`BrokerAdapter` ABC 在 B012 留作扩展锚点，永久延后）；
- 多用户 / 外部客户 / 注册流程（OAuth allowlist 仅含单 email）；
- 桌面打包（Tauri / Electron）；
- 实时数据流 / 自动调仓 / 多 panel dockable / 命令面板 / i18n；
- PDF 报告组装 / 自包含 HTML 快照（浏览器 print-to-PDF 是 0 成本兜底）。

## 8. 云部署边界

> 2026-05-15 修订：原 §8 描述 MVP "不要求云端生产部署"。用户 2026-05-15 决定 workbench 部署到现有 GCP VM (`trade.guangai.ai`)，复用与 aigcgateway 的共享基础设施。详见 ADR `docs/adr/2026-05-15-workbench-direction.md` 云部署 addendum。

### Workbench 云部署（B021 落地）

- **平台：** 用户已有 GCP VM（与 aigcgateway 共住）；不另购云资源。
- **隔离：** systemd unit 显式 `CPUQuota=200%` + `MemoryMax=2G` 把 workbench 资源消耗封顶；不与 aigcgateway 抢资源。
- **域名 / TLS：** `trade.guangai.ai` via 现有 nginx + certbot Let's Encrypt 自动续。
- **数据：** SQLite 在 `/var/lib/workbench/workbench.db`，Alembic 管理 schema；不与 aigcgateway DB 共享。
- **Secrets：** 通过 systemd `EnvironmentFile=` 加载（GOOGLE_OAUTH_CLIENT_SECRET / NEXTAUTH_SECRET / ALLOWED_USER_EMAIL / 可选 SENTRY_DSN）；GitHub Actions Secrets 持有 SSH 部署私钥；**不入 git**。
- **日志：** uvicorn access log → 文件 + systemd journald；结构化 application log 含 request_id；可选 Sentry。
- **备份：** systemd timer 触发 SQLite snapshot → gzip → GCS bucket（30 daily + 12 monthly retention + restore script）。
- **CI/CD：** push to main → GitHub Actions 跑测试 → build 产物 → SSH deploy → health check → 失败 rollback symlink。
- **资源成本：** 边际 $0（VM 已存在）；GCS backup ≤ 10 GB ≈ $0.20/月。

### 仍属非 MVP

- 多 region / HA / auto-scaling；
- 多 VM / k8s / Cloud Run；
- 多用户 SaaS；
- 实时行情接入（WebSocket）；
- 商用 broker/paper API 接入（PRD §5 永久禁止）。

## 9. 安全与合规要求

必须遵守：

- 不提交 API key。
- 不提交 `.env`。
- 不提交付费行情数据。
- 不提交真实账户导出。
- 不执行未经授权的真实券商调用。
- 不执行真实资金交易。
- 不向外部客户提供投资建议。
- AI 不直接控制交易。

真实 broker 或 live-money 测试必须单独授权，且授权需包含 broker、账户、策略、金额和时间窗口。

### Workbench cloud-deployment 安全约束（B021 落地）

- 所有 workbench 路由（除 `/api/health` 与 OAuth 回调）必须经 Google OAuth + 单 email allowlist 鉴权；非 allowlist 用户返回 403。
- Secrets（OAuth client secret / NextAuth secret / 部署 SSH key）通过 systemd `EnvironmentFile=` 或 GitHub Actions Secrets 注入；**不入 git**；regression test 验证 `.env` / 私钥文件不在 commit。
- TLS 强制：`trade.guangai.ai` 仅 HTTPS；HTTP 重定向到 HTTPS；HSTS 头开。
- 资源隔离：systemd `CPUQuota=200%` + `MemoryMax=2G` 防止 backtest 失控拖死 aigcgateway。
- 数据隔离：SQLite 数据库 + 文件存储独立目录 `/var/lib/workbench/`；与 aigcgateway 数据 0 共享。
- 不允许 broker SDK / paper API URL / live API URL 出现在 workbench 任何代码或配置中（regression test 守住）。
- 备份：SQLite snapshot 含账户状态 + journal，作为敏感数据，加密存 GCS（GCS server-side encryption + bucket-level access control）。
- 审计：所有 mutation 操作（snapshot refresh / backlog CRUD / target positions export）记结构化 log（user_id + request_id + action + timestamp）。

## 10. 成功指标

MVP 成功标准：

- 工程基线可安装、可测试、CI 可运行。
- 全球 ETF universe 可配置。
- 本地历史数据或 fixture 可加载。
- 数据质量检查可执行。
- ETF 动量信号可生成。
- 月度回测可完成。
- 绩效报告可生成。
- 回测可复现。
- 无真实 API key、无真实 broker、无真实资金依赖。

## 11. 验收标准

MVP 整体验收要求：

- B004 工程基线完成。
- B005 全球 ETF 回测 MVP 完成。
- 默认 CI 不依赖外部 API。
- 所有测试使用 fixture 或 mock。
- 报告明确数据源、参数和假设。
- 回测遵守 T 日信号、T+1 执行。
- 策略不绕过风控。
- 不存在 live trading 入口。

## 12. 里程碑

> 2026-05-15 修订（二次）：原 B009 Broker Adapter Paper 已移除；workbench 路径从 2 个批次（B020/B021）扩为 4 个批次（B020 Dev Infra + B021 Cloud Deploy + B022 Workbench Phase 1 + B023 Workbench Phase 2）以容纳 cloud-deployed 多设备访问需求。详见 ADR `docs/adr/2026-05-15-workbench-direction.md` 及云部署 addendum。

| PRD 编号 | 目标 | 状态 / 实际批次 |
|---|---|---|
| B004 Core Engineering Foundation | Python 包结构、测试、CI、配置、接口边界、前端规划文档 | ✅ 已完成（项目实际批次 B003-B004） |
| B005 Global ETF Backtest MVP | ETF universe、数据加载、动量信号、月度回测、报告 | ✅ 已完成（项目实际批次 B005-B007） |
| B006 Risk Parity Backtest MVP | 风险平价、目标波动率、组合风险稳定器 | ✅ 已完成（B010；B019 retune 收口） |
| B007 Portfolio Allocation and Risk | 多策略资金分配、组合级风控 | ✅ 已完成（B011） |
| B008 Paper Trading / Mock Broker | 目标仓位输出 + 抽象 BrokerAdapter + Mock | ✅ 已完成（B012） |
| **B020 Workbench Dev Infrastructure** | workbench skeleton + Python/Node 工具链 + CI workflows + 测试策略 + 安全 guard 脚手架 + OpenAPI ↔ TS pipeline + 文档 | 🚧 计划中（next batch） |
| **B021 Workbench Cloud Deploy & Auth** | Google OAuth + SQLite + Repository 数据层 + Dockerfile + systemd + nginx vhost + cert + CI/CD + 备份 + 可观测性 | ⏳ B020 完成后 |
| **B022 Research Workbench (Phase 1)** | cloud SPA: 7 页 read-mostly + 最小 write，部署到 trade.guangai.ai | ⏳ B021 完成后 |
| **B023 Workbench Phase 2** | 手动执行 UI：position diff / order ticket / fill journal | ⏳ B022 完成后 |

> 注：原 "B009 Broker Adapter Paper（IBKR/Alpaca paper adapter，仍不做 live）" 已移除。
> PRD §5 已将"实际 broker API 接入"明确划入非 MVP；用户路线选择 manual execution，
> 由 B023 工作台 UI 服务，不做自动 paper / live 接入。`BrokerAdapter` ABC（B012）保留为
> 未来扩展锚点，永久延后到非 MVP 范围。

## 13. 风险清单

### 13.1 产品风险

- MVP 范围膨胀，过早进入前端或券商接入。
- 策略研究和产品交付边界混淆。
- 过度追求完整平台，延迟第一个可运行回测。

缓解：严格按批次推进，B004/B005 优先可运行闭环。

### 13.2 数据风险

- 数据源质量不足。
- 复权和公司行为错误。
- point-in-time 缺失。
- 付费数据授权不清。

缓解：先做数据质量检查、数据快照和明确数据限制。

### 13.3 技术风险

- 代码写成一次性脚本，后续推倒重来。
- 模块边界不清。
- CI 不稳定。
- 测试依赖外部 API。

缓解：B004 先做轻量但可扩展的工程基线。

### 13.4 合规风险

- 未授权使用数据。
- 误触发真实券商操作。
- 对外提供投资建议。

缓解：MVP 不做 live，不做外部客户，不提交数据文件和 secrets。

### 13.5 交易风险

- 回测过拟合。
- 交易成本低估。
- 极端市场相关性上升。
- 实盘滑点与回测不同。

缓解：Paper Trading 前不进入实盘；所有策略需回测、稳健性测试和风控检查。

## 14. AI 能力边界

MVP 不实现 AI 自动交易。

AI 在 MVP 中只作为后续规划边界：

- 可用于未来报告解释。
- 可用于未来新闻/公告风险过滤。
- 不直接买入。
- 不直接加仓。
- 不直接修改参数。
- 不绕过风控。

## 15. Open Questions

- B005 使用真实公开样例数据还是完全合成 fixture 起步？
- B005 是否引入真实数据源下载脚本，还是只定义 provider 接口？
- 回测报告首期是否需要图表文件，还是 JSON/Markdown 足够？
- B004 是否启用 mypy，还是先用 ruff + pytest + compileall？
- B006 风险平价是否依赖 B005 的同一数据接口直接复用？

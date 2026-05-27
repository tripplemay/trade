# B031 — LLM Gateway（Phase 2 起点 / Stream 3.A）

> Status：active (planning → building)
> Owner：Generator (F001-F002) + Codex (F003)
> Predecessor：B030 (Real Data Cutover — 里程碑 A Layer 0→1 达成) — done 2026-05-27
> 估时：1-2 个轻量-中型批次
> 范围分类：post-MVP product alignment batch（**Phase 2 起点 / Stream 3.A**；属 implementation-path-2026-05.md §4 第六个 batch；本批次属 Layer 1.5 AI-augmented advisory 基础设施）

## 1. 目标

为 Stream 3 AI advisor 打基础：把 **aigc-gateway**（本项目已有 MCP server，30+ tools）接入 workbench backend，提供统一 chat completion 抽象层 + multi-tier model routing（Sonnet 主力 / Haiku 高频 / Flash news / Opus quarterly）+ cost guard（¥1500 月 cap）+ log 全请求。

**不做**：prompt template 设计（留 Stream 3.C AI advisor MVP）；safety eval 红队（留 B032 = Stream 3.B）；具体 AI advisor endpoint（留 B036 = Stream 3.C）；前端 UI（留 Stream 4 Home + Stream 5 UI 简化）。

## 2. 决策矩阵（2026-05-27 用户已批）

| 维度 | 决策 |
|---|---|
| Gateway 接入 | **aigc-gateway**（本项目自有 MCP server；30+ tools 已集成；统一 chat / embed / log）|
| 接入协议 | Backend 走 aigc-gateway HTTP REST API（**不走 MCP**，MCP 主要给 IDE/assistant 集成）；通过 `mcp__aigc-gateway__create_api_key` 在 aigc-gateway 内创建一个 backend 专用 API key |
| Routing 策略 | **Multi-tier**（llm-provider-evaluation §5.2 路由表）：Daily advisor=Haiku-4.5 / Quarterly deep review=Sonnet-4.6（升级 Opus-4.7 复杂）/ News summarize=Gemini-2.0-Flash（长 context）/ Tooltip+简化文案=Haiku / 离线 CI=Qwen2.5 32B local |
| Cost cap | **¥1500/月**（llm-provider-evaluation §6 推荐 + roadmap §2 ¥500-2000 上限内）|
| Cost guard 触发 | ≥80% (¥1200) → alert log + fallback Haiku/Flash；≥100% (¥1500) → `BudgetExceeded` raise + halt（参考 B027 §(g) Tiingo $10 cap pattern）|
| 范围 | **纯 basic infra**：gateway 抽象 + routing 配置 + cost guard + log；不接 advisor endpoint / 不接 safety eval / 不接 prompt templates |
| Provider keys 管理 | **aigc-gateway 内部管理**（Anthropic / OpenAI / Gemini 等 provider keys 通过 `mcp__aigc-gateway__create_api_key` 在 gateway 配；workbench backend 仅需 1 个 `AIGC_GATEWAY_API_KEY`）|
| API key 接线（v0.9.30 §12.9 4 处接线遵守）| `.env.example` + `config.py` + `deploy.sh` pre-flight + `bootstrap-env.yml` |
| 离线 CI | **mock aigc-gateway HTTP responses**（CI 不调真 LLM）；本机离线 pytest 全过 |
| Layer 1.5 准备 | 本批次是 AI advisory 基础设施；不引入 buy/sell 信号 / 不引入预期收益数字（永久边界 v0.9.28 AI 5 子条）|

## 3. 永久硬边界（B031 起继续 enforced）

继承 B012-B030 + framework v0.9.31 全部边界：

- **系统层：** no-broker SDK / no live trading URL / no-credential（AIGC_GATEWAY_API_KEY 走 secret）/ no-auto-execution / 多用户禁 / Cloud SQL 禁 / same-origin /api/* / auth-gated / Repository pattern
- **UI 层：** no-execution buttons + 中文等价禁词 / Order ticket Markdown 双语 disclaimer / B026 banner decommissioned（保留可重启路径）
- **数据 / CI 层：** fixture-first 离线 CI（**本批次：mock aigc-gateway responses；CI 不调真 LLM**）/ pyproject runtime-vs-dev hygiene（v0.9.29 §12.8）/ paths-trigger 已含 trade/+scripts/+pyproject.toml（v0.9.27 §12.7.1）
- **AI 边界（v0.9.28，本批次开始触发）：** 5 子条 **本批次仅是 gateway infra，不触 advisor 逻辑**；但 spec acceptance 列出全集（任何 LLM 调用未来必须遵守）：
  - (a) no auto-execution
  - (b) no 收益预测数字输出
  - (c) no 替代 quant 评分作为唯一决策依据
  - (d) 必须基于 quant signal + real data + 可引用 news
  - (e) 解释 / summarize / translate / context aggregation 允许
- **B027/B029/B030 继续 enforced**
- **B030 起 (k) Layer 状态不可逆向滑落**：本批次启动 Layer 1.5 准备工作；若 fix-round 发现 aigc-gateway 严重 unreliable 必须新批次 spec 决议
- **新增产品边界（B031 起）：**
  - **(l) LLM provider routing 不可硬编码 model name in 业务代码**：必须走 `workbench_api/llm/gateway.py` routing table；业务代码调 `llm_gateway.advise(task="daily_advisor")` 不直接传 model name
  - **(m) LLM 月预算 cap ¥1500 enforced**：参考 B027 §(g) Tiingo cost guard pattern；超 ¥1200 alert + fallback / 超 ¥1500 raise + halt

## 4. 技术架构

### 4.1 文件结构

```
workbench/backend/workbench_api/llm/    # 【新增 F001】LLM gateway 模块
├── __init__.py
├── gateway.py                          # LLMGateway 抽象 + aigc-gateway HTTP client
├── routing.py                          # Multi-tier model routing table
├── cost_guard.py                       # MonthlyBudgetGuard for LLM (cap ¥1500)
└── fixtures/                           # mock responses for CI
    ├── aigc_gateway_chat_responses/    # mock chat completion 抽样
    └── aigc_gateway_balance_response/  # mock balance check

workbench/backend/workbench_api/repositories/  # 既有
└── llm_budget_log.py                   # 【新增 F002】SQLite 表 llm_budget_log

workbench/backend/.env.example          # 【F001 改】加 AIGC_GATEWAY_API_KEY=
workbench/backend/workbench_api/config.py  # 【F001 改】加 AIGC_GATEWAY_API_KEY 读取
workbench/deploy/scripts/deploy.sh      # 【F001 改】加 pre-flight check
.github/workflows/bootstrap-env.yml     # 【F001 改】加 AIGC_GATEWAY_API_KEY inject (v0.9.30 §12.9)
pyproject.toml                          # 不引入新 dep (httpx 已有；走 aigc-gateway HTTP REST)
tests/safety/test_runtime_dependencies_pinned.py  # 不动 (无新 dep)
```

### 4.2 LLMGateway 抽象 + routing table

```python
# workbench_api/llm/gateway.py
"""Abstract LLM gateway with aigc-gateway HTTP backend.

Per llm-provider-evaluation-2026-05.md §3.1 + §5.1:
- Backend talks to aigc-gateway via HTTP REST (not MCP);
  aigc-gateway internally manages Anthropic/OpenAI/Gemini provider keys.
- Multi-tier routing per §5.2 (task → model).
- Cost guard per §6 (¥1500 monthly cap).
"""
import os
from dataclasses import dataclass
import httpx
from workbench_api.llm.routing import route_task
from workbench_api.llm.cost_guard import MonthlyBudgetGuard


@dataclass(frozen=True, slots=True)
class ChatRequest:
    task: str                    # "daily_advisor" | "quarterly_review" | "news_summarize" | "tooltip" | etc.
    messages: list[dict]         # [{role: ..., content: ...}, ...]
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model_used: str              # e.g. "claude-haiku-4-5"
    input_tokens: int
    output_tokens: int
    cost_usd_est: float
    aigc_log_id: str             # aigc-gateway internal log ID for tracing


class LLMGateway:
    BASE_URL = "https://aigc-gateway.example.com"  # 实际 URL 由 aigc-gateway 部署决定

    def __init__(self, api_key: str | None = None, guard: MonthlyBudgetGuard | None = None):
        self.api_key = api_key or os.environ.get("AIGC_GATEWAY_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "AIGC_GATEWAY_API_KEY missing; configure .env.production via "
                "GitHub Secret. Create one at aigc-gateway dashboard / via "
                "mcp__aigc-gateway__create_api_key (per llm-provider-evaluation §5.1)."
            )
        self.guard = guard or MonthlyBudgetGuard.default()
        self._client = httpx.Client(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def advise(self, request: ChatRequest) -> ChatResult:
        """High-level chat completion with task → model routing + cost guard."""
        model = route_task(request.task)  # multi-tier routing
        self.guard.check_and_increment(estimated_cost_usd=self._estimate_cost(model, request))
        # POST /chat with model + messages → ChatResult
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Multilingual embedding via aigc-gateway (Cohere multilingual default)."""
        ...

    def health_check(self) -> bool:
        """GET /balance to verify API key + aigc-gateway 可达."""
        ...
```

### 4.3 Multi-tier routing table

```python
# workbench_api/llm/routing.py
"""Task → model routing per llm-provider-evaluation §5.2.

永久边界 (l): 业务代码不可硬编码 model name；只通过 task name 间接路由。
"""

ROUTING_TABLE: dict[str, str] = {
    # llm-provider-evaluation §5.2 推荐配置
    "daily_advisor": "claude-haiku-4-5",         # 高频 Home 一句话建议
    "quarterly_review": "claude-sonnet-4-6",     # 季度调仓建议
    "quarterly_review_deep": "claude-opus-4-7",  # 复杂多 sleeve 综合判断（升级）
    "news_summarize": "gemini-2.0-flash",        # 长 context 优势
    "topic_tagging": "claude-haiku-4-5",         # 简短分类
    "sharpe_tooltip": "claude-haiku-4-5",        # Sharpe / Sortino tooltip 解释
    "robinhood_simplify": "claude-haiku-4-5",    # 简化文案
    "embedding": "cohere-embed-multilingual-v3", # News + RAG embedding
    # Fallback chain on cost cap hit or 5xx
    "_fallback_advisor": "claude-haiku-4-5",
    "_fallback_news": "gemini-2.0-flash",
    "_fallback_embedding": "gemini-text-embedding-004",  # free tier
    # CI / 离线
    "_ci_mock": "mock-provider",                 # 仅在 mock fixture 中使用
}

def route_task(task: str) -> str:
    """Map task → model. Unknown task → RuntimeError (forces explicit routing)."""
    if task not in ROUTING_TABLE:
        raise RuntimeError(
            f"Unknown LLM task '{task}'. Add to workbench_api/llm/routing.py "
            f"ROUTING_TABLE per llm-provider-evaluation §5.2."
        )
    return ROUTING_TABLE[task]
```

### 4.4 Cost guard

```python
# workbench_api/llm/cost_guard.py
"""LLM monthly budget guard. ¥1500/月 cap per llm-provider-evaluation §6."""

from datetime import date
from dataclasses import dataclass
from workbench_api.repositories import llm_budget_log


# ¥1500 ≈ $200 USD (按 2026-05-26 中间汇率 7.5)
@dataclass(frozen=True, slots=True)
class MonthlyBudgetGuard:
    monthly_cap_usd: float = 200.0        # ≈ ¥1500
    alert_threshold_ratio: float = 0.80   # 80% → fallback Haiku/Flash
    halt_threshold_ratio: float = 1.00    # 100% → BudgetExceeded raise

    @classmethod
    def default(cls) -> "MonthlyBudgetGuard":
        return cls()

    def check_and_increment(self, estimated_cost_usd: float) -> None:
        current_usd = llm_budget_log.get_month_total_usd(date.today())
        next_usd = current_usd + estimated_cost_usd
        if next_usd >= self.monthly_cap_usd:
            raise BudgetExceeded(
                f"Monthly LLM budget cap ${self.monthly_cap_usd} (¥{self.monthly_cap_usd * 7.5:.0f}) "
                f"hit (used ${current_usd:.2f}); request not sent. Fallback or wait for next month."
            )
        if next_usd >= self.alert_threshold_ratio * self.monthly_cap_usd:
            logger.warning(
                "llm_budget_near_cap",
                extra={"used_usd": current_usd, "next_usd": next_usd, "cap_usd": self.monthly_cap_usd},
            )
        llm_budget_log.increment(date.today(), estimated_cost_usd)


class BudgetExceeded(RuntimeError):
    """Raised when LLM monthly cap is hit; caller must use fallback model or halt."""
```

### 4.5 Production secret 接线（v0.9.30 §12.9 4 处接线遵守）

| 处 | 操作 |
|---|---|
| 1. `.env.example` | 加 `AIGC_GATEWAY_API_KEY=` 注释行 + 说明（"Create via aigc-gateway dashboard or `mcp__aigc-gateway__create_api_key`"）|
| 2. `workbench_api/config.py` | 加 `AIGC_GATEWAY_API_KEY` 读取 + 缺时 raise RuntimeError 含修复指引 |
| 3. `workbench/deploy/scripts/deploy.sh` | 加 pre-flight check：`if [ -z "${AIGC_GATEWAY_API_KEY}" ]; then echo "AIGC_GATEWAY_API_KEY missing" && exit 1; fi`（不阻塞 B021-B030 deploy 仅 B031 deploy 时验）|
| 4. `.github/workflows/bootstrap-env.yml` | 加 `AIGC_GATEWAY_API_KEY=${{ secrets.AIGC_GATEWAY_API_KEY }}` 写入 production VM `/etc/workbench/workbench.env`（v0.9.30 §12.9 关键铁律）|

### 4.6 SQLite 表

```sql
-- llm_budget_log
CREATE TABLE llm_budget_log (
    date TEXT PRIMARY KEY,           -- YYYY-MM-DD
    month_year TEXT NOT NULL,        -- YYYY-MM
    call_count INTEGER NOT NULL DEFAULT 0,
    total_cost_usd_est REAL NOT NULL DEFAULT 0.0
);
```

alembic migration `add_llm_budget_log_table.py`（参考 B027 既有 `add_tiingo_budget_log_table.py` 模式）。

## 5. Feature 拆分

### F001 — LLMGateway + routing + aigc-gateway HTTP client + secret 接线（generator，3-4 天）

**Acceptance：**

(1) 新建 `workbench_api/llm/__init__.py` + `gateway.py`：
- `ChatRequest` / `ChatResult` dataclass frozen + slots
- `LLMGateway` 类 + `__init__` 接收 `api_key` + `guard`
- `advise(request)` 路由 + cost guard check + httpx POST → `ChatResult`
- `embed(texts)` 嵌入
- `health_check()` GET /balance

(2) 新建 `workbench_api/llm/routing.py`：
- `ROUTING_TABLE` 含 §4.3 列出的 8+ task 映射
- `route_task(task)` unknown task → RuntimeError
- **永久边界 (l)** 验证：业务代码不可硬编码 model name（通过 grep 守门测试）

(3) 改 `workbench_api/config.py`：加 `AIGC_GATEWAY_API_KEY` 读取（缺时 raise RuntimeError 含修复指引：`mcp__aigc-gateway__create_api_key` or dashboard URL）

(4) 改 `.env.example`：加 `# AIGC Gateway API key for B031+ LLM access (https://aigc-gateway.example.com/dashboard)` `AIGC_GATEWAY_API_KEY=`

(5) 改 `workbench/deploy/scripts/deploy.sh`：加 pre-flight check（v0.9.25 §12.5 模式 + v0.9.30 §12.9 反 anti-pattern 规避）

(6) **改 `.github/workflows/bootstrap-env.yml`**（**v0.9.30 §12.9 关键铁律 — 不可漏！**）：加 `AIGC_GATEWAY_API_KEY=${{ secrets.AIGC_GATEWAY_API_KEY }}` 写入 production VM `/etc/workbench/workbench.env`

(7) 新建 `workbench_api/llm/fixtures/aigc_gateway_chat_responses/` + `aigc_gateway_balance_response.json`：mock 抽样响应

(8) pytest 新增 ≥12 测试：
- `ChatRequest` / `ChatResult` dataclass frozen + slots + 类型
- `LLMGateway` 缺 API key → raise RuntimeError 含修复指引
- mock httpx POST /chat → ChatResult 解析正确
- mock 5xx → 3 次重试 + alert log
- mock 429 rate limit → 重试 + backoff
- `health_check` mock /balance 200 → True
- `route_task("daily_advisor")` → "claude-haiku-4-5"
- `route_task("unknown_task")` → RuntimeError 含 routing.py 添加指引
- 业务代码 grep 守门：`grep -E "claude-(haiku|sonnet|opus)|gpt-|gemini-" workbench_api/` 应仅命中 routing.py（其他业务文件 0 hits）
- ROUTING_TABLE 含全部 §4.3 task
- 永久边界 (l) 守门测试：业务代码不能 import model name 字符串
- API key 字面值不入 build artifact / log

(9) Gates：
- `pytest tests` ≥408 baseline (B030) + ≥12 = ≥420 passed
- `ruff check .` exit=0
- `mypy workbench_api tests` exit=0
- frontend 不动 vitest ≥172 不破

(10) **不动**：
- B027/B028/B029/B030 既有 loader / scripts / strategy 代码
- trade/ 代码（本批次纯 LLM gateway infra，不接业务）
- workbench backend endpoints（不引入新 endpoint）
- Frontend / UI
- B026 banner decommissioned 状态

### F002 — LLM cost guard + budget log + alembic migration（generator，2-3 天）

**Acceptance：**

(1) 新建 `workbench_api/llm/cost_guard.py`：
- `MonthlyBudgetGuard` dataclass（cap=200.0 USD ≈ ¥1500 / alert=0.80 / halt=1.00）
- `check_and_increment(estimated_cost_usd)` 检查 + 写 budget log
- `BudgetExceeded` exception 含修复指引

(2) 新建 `workbench_api/repositories/llm_budget_log.py`：
- SQLite 表 `llm_budget_log` (date PK, month_year, call_count, total_cost_usd_est)
- CRUD: `get_month_total_usd(date)` / `increment(date, cost_usd)`

(3) alembic migration `add_llm_budget_log_table.py`：参考 B027 `add_tiingo_budget_log_table.py` 模式；不破既有 schema

(4) 改 `LLMGateway.advise`：入口调 `guard.check_and_increment(estimated_cost)` + 调用前估算 cost（按 routing table 选定 model 的输入 token × 价格表估算）

(5) 改 `/api/debug/recent-errors`（B022 既有）：确认能捕获 `llm_budget_near_cap` warning + `BudgetExceeded` raise log

(6) pytest 新增 ≥10 测试：
- `MonthlyBudgetGuard.default()` 默认值正确（cap=200.0 / alert=0.80）
- `check_and_increment(estimated=10)` 月内首次通过
- 接近 80% (next ≥ 160 USD) → log warning
- ≥100% (next ≥ 200 USD) → raise BudgetExceeded
- BudgetExceeded 异常含 ¥-equivalent 显示
- llm_budget_log SQLite CRUD（fixture DB）
- 月份切换 5→6 calls/cost 归零
- alembic up/down 在 fixture DB
- `LLMGateway` 集成 cost_guard（mock guard.check_and_increment → advise 成功 / BudgetExceeded → 不调 HTTP）
- llm_budget_log 表 schema 一致性 assert

(7) Gates：
- `pytest tests` ≥420 + ≥10 = ≥430 passed
- `ruff` + `mypy` 清
- alembic up/down 在 fixture DB 验证
- Frontend 不动

(8) **不动**：F001 已完成的 gateway / routing 接口；其他 backend endpoint / strategy 代码

### F003 — Codex L1 + L2 真 VM 验收 + signoff（codex，1-2 天）

**L1 (CI 内)：**

- F001 + F002 全 generator 验收脚本跑通：backend pytest ≥430 / ruff / mypy / alembic up-down OK
- Frontend 不动既有 vitest ≥172 + Playwright ≥38 不破
- safety regression 全绿（含 v0.9.29 §12.8.1 + **v0.9.30 §12.9 bootstrap-env.yml grep 守门**：确认 `AIGC_GATEWAY_API_KEY` 在 bootstrap-env.yml）+ **永久边界 (l) 守门**（business code grep 无硬编码 model name）
- artifact grep `AIGC_GATEWAY_API_KEY` value / aigc-gateway HTTP endpoint 字面值 0 命中
- CI 完全离线 `pytest --no-network` 全过（mock fixture）

**L2 (真 VM)：**

1. Generator 实施期间已在 GitHub repo Settings 加 `AIGC_GATEWAY_API_KEY` secret（用户协助生成 via `mcp__aigc-gateway__create_api_key`）；deploy workflow inject 成功
2. Production VM `cat /etc/workbench/workbench.env | grep AIGC_GATEWAY_API_KEY` 存在（值脱敏）
3. `curl https://trade.guangai.ai/api/health` 200 + version SHA 与 main HEAD 等价
4. `curl https://trade.guangai.ai/api/debug/recent-errors` 返回 `{"count":0,"records":[]}`
5. Production backend log（systemd journal）含 alembic migration `add_llm_budget_log_table` 成功记录
6. SSH 到 VM 跑 `sqlite3 ... "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_budget_log'"` 返回 1 行
7. **smoke API test**（Evaluator 临时跑一次）：production backend SSH 触发 `LLMGateway().health_check()` → aigc-gateway /balance 返回 200 / llm_budget_log 不应增（health check 不计 cost）
8. B026 banner 仍 decommissioned 不破（HTML grep `研究原型` / `SyntheticDataBanner` 0 hits）
9. Production HEAD ≡ main HEAD（v0.9.25 §Production/HEAD 等价性）+ Post-signoff Deploy 段（v0.9.27 / §12.7.1）

**Signoff：**

- `docs/test-reports/B031-llm-gateway-signoff-2026-MM-DD.md` 用 framework/templates/signoff-report.md（含 v0.9.27 §Post-signoff Deploy + v0.9.31 §Decommission Checklist "本批次不含 decommission" + §Production/HEAD）
- `docs/screenshots/B031-llm-gateway/` ≥2 PNG：production /api/health 响应 + llm_budget_log 表存在

**Framework 候选：**

预期无重大 framework learning（v0.9.30 §12.9 已守门 secret 接线；v0.9.31 §16 已守门 decommission 但本批次非 decommission；永久边界 (l) routing 守门是本批次新加）。若 fix-round 出现 aigc-gateway 接入意外（鉴权 / rate limit / 价格表估算偏差 / MCP vs HTTP 混淆）记录 signoff §Framework Learnings。

## 6. 不做的事（YAGNI）

- ❌ **Prompt template 设计**（留 Stream 3.C AI advisor MVP = B036+）
- ❌ **AI safety eval 红队 dataset**（留 B032 = Stream 3.B）
- ❌ **具体 AI advisor endpoint**（留 B036 = Stream 3.C）— 本批次仅 infra
- ❌ **前端 UI 改动**（留 Stream 4 Home + Stream 5 UI 简化）
- ❌ **Anthropic / OpenAI / Gemini SDK 直接 import**（业务代码强制走 aigc-gateway HTTP；avoid SDK lock-in）
- ❌ **每次调用前 token counter**（首版用 routing table input token × model 价格表估算；精确 token counter 留下批次）
- ❌ **Streaming chat completion**（本批次仅 sync HTTP；streaming SSE 留 Stream 3.C 视需要再加）
- ❌ **Cache 策略实施**（routing.py + cost_guard 即可；prompt caching 留下批次按 llm-provider-evaluation §5.4 设计）

## 7. 验收门槛汇总

| 门槛 | F# 责任 |
|---|---|
| `LLMGateway` 抽象 + aigc-gateway HTTP client + retry + health_check | F001 |
| `routing.py` ROUTING_TABLE 含 8+ task；`route_task` unknown → RuntimeError | F001 |
| **永久边界 (l) 守门：业务代码不可硬编码 model name**（grep regression test）| F001 |
| `.env.example` + `config.py` + `deploy.sh` + **`bootstrap-env.yml` 四处接线（v0.9.30 §12.9）**| F001 |
| `MonthlyBudgetGuard` cap=200 USD (~¥1500) + alert 80% + halt 100% | F002 |
| `llm_budget_log` SQLite 表 + alembic migration | F002 |
| `LLMGateway.advise` 集成 cost guard | F002 |
| Backend pytest ≥430 + ruff + mypy 清 | F001+F002+F003 |
| Frontend 不破 vitest ≥172 + Playwright ≥38 | F003 |
| L2 GitHub Secret 注入 + production VM grep 含 AIGC_GATEWAY_API_KEY | F003 |
| L2 alembic migration 成功 + llm_budget_log 表存在 + smoke health_check | F003 |
| Production HEAD ≡ main HEAD + Post-signoff Deploy 段 | F003 |
| B026 banner 仍 decommissioned（HTML grep 0 hits）| F003 |
| Signoff 报告 framework/templates/signoff-report.md 全段 + §Decommission Checklist "本批次不含 decommission" | F003 |

## 8. 参考文档

- `docs/product/implementation-path-2026-05.md` §4 Phase 2 起点 / §7 永久边界 / §8 Planner 接续 checklist / §9 spec 撰写要点
- `docs/product/llm-provider-evaluation-2026-05.md` **§3.1 aigc-gateway 首选** / §5.1 gateway / **§5.2 routing 表** / **§6 cost 预算** / §7 切换策略 / §8 不做的事
- `docs/product/positioning-2026-05.md` §1.1 AI 角色与边界 + §6.1 永久边界 5 子条
- `docs/product/roadmap-2026-05.md` Stream 3.A
- `docs/specs/B027-real-data-snapshot-foundation-spec.md` cost guard pattern（Tiingo $10 cap；本批次 LLM $200 cap 参考相同 pattern）
- `docs/specs/B029-fundamentals-snapshot-spec.md` SimpleRateLimit + httpx + secret 三处接线（本批次复用）
- `framework/STRUCTURE.md` framework/ 目录语义
- `framework/harness/planner.md` §"AI 边界精细化（v0.9.28）" §"Cloud-deploy spec checklist v0.9.27 扩展 (e)"
- `framework/harness/generator.md` §10 GHA / §12.5-12.7 deploy / **§12.9 production secret 三处接线铁律（v0.9.30 — 本批次必须遵守）** / §12.8 pyproject runtime vs dev / §16 decommission 四处清理（本批次不触）
- `framework/harness/evaluator.md` §21 signoff Production/HEAD + §22 decommission E2E 翻转（本批次不触）
- `framework/templates/signoff-report.md` v0.9.27 §Post-signoff Deploy + v0.9.31 §Decommission Checklist
- aigc-gateway MCP 工具集合（30+ tools via `mcp__aigc-gateway__*`）
- llm-provider-evaluation §5.2 routing 表
- llm-provider-evaluation §6 cost 预算分配（含 alert/halt 阈值）

## 9. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `AIGC_GATEWAY_API_KEY` 泄漏 | v0.9.30 §12.9 4 处接线全部完成（含 bootstrap-env.yml）；artifact grep 0 命中守门 |
| aigc-gateway HTTP API 改 schema | 抽象在 `gateway.py` 一层；schema 改时仅改 1 文件；业务代码不感知 |
| Provider SDK 直接 import 漏（永久边界 (l) 违反）| F001 acceptance 含 regression test grep 业务代码不命中 model name 字符串 |
| Cost 估算偏差导致 budget 不准 | routing.py 输入 token × 价格表估算（首版可接受 ±20% 偏差）；后续精确 token counter 留下批次 |
| aigc-gateway 5xx / rate limit | retry 3 次 + backoff；连续 fail → fallback Haiku/Flash via routing；最终 BudgetExceeded raise 让业务感知 |
| LLM provider 模型升级（如 Sonnet 4.6 → 4.8）| ROUTING_TABLE 集中改一处；业务代码不动 |
| 月预算被 burst 一次吃完 | alert 80% 已 fallback；100% raise 阻断；业务代码必须 catch BudgetExceeded |
| aigc-gateway 接入 MCP vs HTTP 混淆 | spec §2 决策矩阵明确"backend 走 aigc-gateway HTTP REST API（不走 MCP）"；F001 acceptance 明示 |

## 10. 与既有批次的边界

- 不动 B027 既有 Tiingo loader / cost_guard (Tiingo $10 cap)；本批次 LLM cost guard 是**独立 MonthlyBudgetGuard 实例**（不复用 Tiingo budget log；不同 SQLite 表）
- 不动 B028 backfill / B029 SEC EDGAR loader / B030 strategy 切真
- 不动 B026 banner（仍 decommissioned；v0.9.31 §16 守门 + §22 测试守 +§Decommission Checklist 守）
- 不动 strategy 代码 / trade/data/loader.py / Recommendations / Risk Panel / Reports / Frontend
- 不动 既有 alembic migrations（仅新增 `add_llm_budget_log_table`）

## 11. 后续批次（不在 B031 范围）

按 implementation-path §4 Phase 2 顺序：

- **B032 = Phase 2 / Stream 3.B** AI safety eval framework（红队 dataset + LLM judge + INSUFFICIENT_GROUNDING fallback；按 ai-safety-evals-2026-05.md §3-§6）
- **B033 = Phase 2 / Stream 2.A** News ingest 框架（SEC EDGAR filings + Yahoo Finance RSS + FRED 宏观）
- **B034 = Phase 2 / Stream 2.B** News ↔ ticker / sleeve 关联（Cohere multilingual embedding 接入 aigc-gateway）
- **B035 = Phase 2 / Stream 2.C** Market context（FRED + Alpha Vantage 指数）
- **B036 = Phase 2 / Stream 3.C** AI advisor MVP（整合 quant signal + real data + news → 文本建议含引用；通过 §31 + §32 + §33-35 输出）→ **里程碑 B AI advisory 框架可用**

**Phase 2 完成 (B036 done)**：implementation-path §6 里程碑 B 达成；AI advisory 框架可用 + production 上 AI 建议必带引用 + 永无收益预测数字 + CI gate 兜底。

---

> 本 spec 完成后，progress.json status=building，current_sprint=F001，Generator 接 LLMGateway + routing + aigc-gateway HTTP client 实现。

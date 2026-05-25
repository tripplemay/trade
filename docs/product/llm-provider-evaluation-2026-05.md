# LLM Provider Evaluation（2026-05-25）

> **状态：** **approved**（2026-05-25 用户批准）
> **配套：** `docs/product/positioning-2026-05.md` §1.1 AI 角色与边界 + `docs/product/roadmap-2026-05.md` Stream 3.A
> **目的：** 为 Stream 3（AI advisory engine）做 LLM provider + gateway + embedding 选型，作为后续 batch spec 的权威输入。
> **范围：** 评估 + 推荐配置 + cost 预算 + 切换策略。**不含**：prompt template 设计 / safety eval（→ doc F）/ 实施 detail。

---

## 1. 选型约束（用户已批 2026-05-25）

| 维度 | 用户偏好 | 含义 |
|---|---|---|
| 优先级 | **质量优先**（金融推理） | 偏向高端模型，cost 可上 ¥1500-3000/月 |
| Provider 锁定 vs 抽象 | **聊天网关代理层** | 不锁单一 SDK；通过 aigc-gateway / OpenRouter 等 aggregator |
| Embedding | **必需** | News 语义检索 + RAG（与 quant signal 关联）|
| 账号现状 | 无；代理层启动后选 | Doc 必须讲多 provider 对比 |
| 月预算（合计）| ¥500-2000/月（roadmap §2 确认）| 含 LLM API + 可选 embedding + cache 预算 |

**衍生原则：** 因质量优先 + 预算中等，**推荐配置避开顶端旗舰**（Opus 4.7 / GPT-5 / Gemini 2.5 Pro 经常 burn cost），**优先中端高质量模型**（Sonnet 4.6 / GPT-4o / Gemini 2.0 Flash），关键复杂推理路径升级到旗舰。

## 2. 候选 Provider 对比（as of 2026-05；价格请使用前自行核实）

### 2.1 Anthropic Claude

| Model ID | Capability | Cost ($/MTok input / output) | Context | 适用场景 |
|---|---|---|---|---|
| **claude-opus-4-7** | 最强推理（金融 / 复杂多步）| ~$15 / $75 | 1M（特殊版本）/ 200K 标准 | 季度 deep review / 关键复杂决策 |
| **claude-sonnet-4-6** | 编码 + 推理平衡（推荐主力）| ~$3 / $15 | 200K | **AI advisor 主力模型** |
| **claude-haiku-4-5** | 90% Sonnet 能力，3x 便宜 | ~$0.80 / $4 | 200K | 高频 advisory / 解释 / tooltip / summarize |

**双语：** zh-CN 能力优秀，与 en 同级。
**Safety：** Anthropic constitutional AI 训练，对金融预测有自带保守倾向（与本项目 AI 边界 5 子条天然契合）。
**Prompt caching：** 支持，可显著降本（重复 prompt 部分缓存 10% 价格）。
**JSON mode：** 支持（structured output）。

### 2.2 OpenAI GPT

| Model ID | Capability | Cost ($/MTok in / out) | Context | 适用场景 |
|---|---|---|---|---|
| **gpt-5** | 旗舰推理 | ~$10 / $30 | 200K+ | 复杂多步推理 |
| **gpt-4o** | 主力平衡 | ~$2.50 / $10 | 128K | AI advisor 备用主力 |
| **gpt-4o-mini** | 轻量 | ~$0.15 / $0.60 | 128K | summarize / 解释 / tooltip |

**双语：** 中等-良好，zh-CN 略逊 Anthropic / Qwen。
**JSON mode：** 强大（Structured Outputs JSON Schema）。
**Function calling：** 强大。

### 2.3 Google Gemini

| Model ID | Capability | Cost ($/MTok) | Context | 适用场景 |
|---|---|---|---|---|
| **gemini-2.5-pro** | 旗舰推理 | ~$3.50 / $10.50 | 2M | 长文档分析（SEC EDGAR 全文）|
| **gemini-2.0-flash** | 主力 | ~$0.15 / $0.60 | 1M | AI advisor 主力候选 |
| **gemini-2.0-flash-thinking** | 推理增强 flash | ~$0.30 / $1.20 | 1M | 复杂推理但 cost 控 |

**双语：** zh-CN 优秀。
**Context length：** 业内最长（2M for Pro / 1M for Flash），适合 SEC EDGAR 全文 + 多 news 文档同读。
**Free tier：** 慷慨（Gemini Flash 每分钟 15 次 / 每天 1500 次免费）。

### 2.4 Local / 自部署（Ollama）

| Model | 量级 | 本机硬件需求 | 推荐场景 |
|---|---|---|---|
| Qwen2.5 32B / Qwen2.5-Coder | 中文领先 | 24GB+ VRAM | 中文摘要 / 离线测试 |
| Llama-3.3 70B | 通用 | 48GB+ VRAM 或量化 | 离线 fallback |
| DeepSeek-R1 distilled | 推理 | 16GB+ VRAM | 实验性推理 |

**优点：** cost = 0；数据不出本机；离线 CI 可用。
**缺点：** 推理质量不及 frontier；本机硬件占用大；金融场景 hallucination 风险更高。
**用法：** 不作为生产主力；可作为离线 CI smoke / 红队 eval baseline。

## 3. Gateway 对比

### 3.1 aigc-gateway（本项目 MCP server，强推）

**优点：**
- 已通过 `mcp__aigc-gateway__*` 工具集成（chat / embed / list_models / list_logs / get_balance / create_action 等 30+ tools）
- 统一 chat completion 接口；provider 切换零代码改动
- 内置 cost 追踪（`get_usage_summary` / `get_balance`）+ log 全请求（`list_logs` / `get_log_detail`）
- 支持 Action（提示词 + 模型绑定的复用单元）+ Template（多步编排）
- 已有 embedding 接口（`embed_text`）
- 项目内部资产，长期可控

**缺点：**
- 中间一层延迟 + 单点故障风险（gateway down 全断）
- 需要 gateway 内 API key 池配置（gateway 自身 vendor key 管理）

### 3.2 OpenRouter

**优点：**
- 业内最广 provider 覆盖（100+ models）
- OpenAI-compatible API（直接 openai SDK 兼容）
- 公开 model leaderboard + 实时 cost 对比
- pay-per-use（无月费），可微小流量验证

**缺点：**
- 不是本项目控制资源
- 中间加价（5%-10%）
- log / debug 工具不如 native SDK

### 3.3 Helicone（不评估为主选）

主要做 LLM observability + cost tracking，不是 provider aggregator。可与上述 gateway 并存（但本项目优先选有 aggregator 能力的）。

## 4. Embedding 选型

| Provider | Model | Cost ($/MTok) | Dimensions | 双语 |
|---|---|---|---|---|
| OpenAI | text-embedding-3-large | $0.13 | 3072 | 良好 |
| OpenAI | text-embedding-3-small | $0.02 | 1536 | 良好 |
| Voyage AI | voyage-3 | $0.06 | 1024 | 优秀（双语）|
| Cohere | embed-multilingual-v3 | $0.10 | 1024 | **专为多语优化** |
| Anthropic | （Anthropic 不提供原生 embedding） | n/a | n/a | n/a |
| Gemini | text-embedding-004 | 免费 tier 慷慨 | 768 | 良好 |
| 本地 | bge-large-zh-v1.5（Qwen / BGE）| 本机硬件 | 768 / 1024 | **中文优秀** |

**对本项目（zh-CN news + en SEC EDGAR）建议：**

- 主选：**Cohere embed-multilingual-v3** 或 **Voyage-3**（双语优化，中文质量优于 OpenAI）
- 备选：**Gemini text-embedding-004**（免费 tier 覆盖）
- 离线 / 备份：**bge-large-zh-v1.5 本地**

## 5. 推荐配置（v0.9.28 起 Stream 3.A 落地参考）

### 5.1 Gateway

**首选：`aigc-gateway`（本项目自有）** — 通过 `mcp__aigc-gateway__*` MCP 工具集合接入。

### 5.2 Provider routing（按场景）

| 场景 | 主力 model | 备用 | 触发条件 |
|---|---|---|---|
| Daily AI advisor（Home 一句话建议）| **claude-haiku-4-5** 或 **gemini-2.0-flash** | claude-sonnet-4-6 | 默认走主力；quant signal 复杂时升级备用 |
| Quarterly deep review（季度调仓建议） | **claude-sonnet-4-6** | claude-opus-4-7 | 默认 Sonnet；季度日 + 需多 sleeve 综合判断时 升级 Opus |
| News summarize / topic tagging | **gemini-2.0-flash**（长 context 优势） | gpt-4o-mini | 默认 Flash；长 SEC EDGAR 全文优势 |
| Sharpe / Sortino 等 tooltip 解释 | **claude-haiku-4-5** | gpt-4o-mini | 低 cost 高频；静态文案 cache |
| Robinhood-style 简化文案 | **claude-haiku-4-5** | gpt-4o-mini | 一次性生成 + cache |
| 离线 CI smoke / 红队 eval baseline | **Qwen2.5 32B local** | — | CI 离线约束 |

### 5.3 Embedding

- 主选 **Cohere embed-multilingual-v3**（aigc-gateway 接入）
- 备选 **Gemini text-embedding-004**（free tier，cost guard 触发时切换）

### 5.4 Cache 策略

| 类型 | 策略 |
|---|---|
| Anthropic prompt caching | 全用；system prompt + quant signal payload + recent news 段进 cache（5 分钟 TTL，跨调用复用）|
| Application-layer cache | SHA(quant_signal + as_of_date + news_set) → AI 输出 cache（24h 内同 input 直接复用）|
| Cost guard | 月度 budget 接近上限时 → 强制 main path 走 Haiku / Flash；deep review 路径打回普通 |

## 6. Cost 预算分配（¥500-2000/月）

| 项 | 月预估 |
|---|---|
| AI advisor daily（30 days × ~3K tok in / ~500 tok out × Haiku/Flash）| ¥30-80 |
| Quarterly deep review（4 × 季度 × Sonnet 全 sleeve 推理 ~50K in / ~5K out）| ¥30-50 |
| News summarize（每日 ~20 篇 × ~5K in / ~500 out × Flash）| ¥80-200 |
| Embedding（每日 ~50 篇 × 5K tok × multilingual）| ¥20-40 |
| Tooltip / 简化文案（首次生成 + cache 几乎不再调用）| ¥10-20 |
| Burst / 实验 / red-team eval | ¥100-200 |
| **小计** | **~¥270-590 / 月** |
| 缓冲（含突发 + 模型升级 + cost 不准确）| ¥500-1000 |
| **建议月预算 cap** | **¥1500** |

**Cost guard：** aigc-gateway `get_balance` + cron 监控；月度走到 ¥1200 时所有路径 fallback 到 Haiku / Flash。

## 7. 切换策略（避免锁定）

通过 aigc-gateway 抽象层 + 多 provider 配置：

```python
# 示意伪代码（实际由 Stream 3.A 落地 workbench_api/llm/gateway.py）
class LLMGateway:
    def chat(self, messages: list[dict], task: str = "default") -> ChatResult:
        model = self.route(task)  # 按 task 选 model
        response = self.call_via_aigc_gateway(model, messages)
        return response

    def route(self, task: str) -> str:
        # 按 §5.2 路由表 + cost guard + 5xx fallback
        ...
```

**Failover 顺序（任一 provider 5xx 或 budget 触顶）：**

```
claude-sonnet-4-6 → claude-haiku-4-5 → gpt-4o → gemini-2.0-flash → local Qwen
```

## 8. 不做的事

- ❌ 直接 `import anthropic` / `import openai` 在业务代码（强制走 gateway 抽象）
- ❌ 把 API key 写入代码（走 env / secret manager）
- ❌ 跨 provider 的 prompt 一致性"魔改"（每 provider 各自有最佳 prompt 风格；可在 Action 层管理多个版本）
- ❌ 用 LLM 替代 quant Master Portfolio 评分（永久边界 v0.9.28 (c)）
- ❌ 用 LLM 出 buy/sell 信号无 quant signal + news 引用（永久边界 v0.9.28 (d)）
- ❌ 用 LLM 输出"预期年化 X%" 等收益预测数字（永久边界 v0.9.28 (b)）
- ❌ 把 user 财产持仓 raw 数据发到不可控 provider（凡 prod 走 gateway，gateway 内可控）

## 9. 后续 batch 依赖

- **Stream 3.A 实施 batch** 必须基于本 doc 选型：aigc-gateway 接入 + Sonnet/Haiku/Flash 三主力路由 + Cohere/Gemini embedding + 5.4 cache 策略
- **doc F**（AI safety evals）将基于本 doc 配置定义红队 dataset + pass 阈值
- **doc D**（data source evaluation）独立，不与本 doc 强耦合

## 10. Doc Lifecycle

- **当前状态：** **approved**（2026-05-25 用户批准）
- **生效信号：** Stream 3.A LLM gateway batch spec 必须引用本 doc §5（推荐配置）+ §6（预算）+ §7（切换策略）+ §8（不做的事）
- **修订流程：** Provider 模型迭代速度快（Claude 4.X / GPT-5 / Gemini 2.X），本 doc 模型/价格表至少**每 6 个月校准一次**；重大方向变更（如改走纯 local / 改走单一 provider 锁定）需新 doc 替代

---

> 配套：positioning §1.1 AI 角色与边界 + roadmap Stream 3.A + 待写 doc F（ai-safety-evals）

# B002 Data Source and Broker Adapter Spec Signoff 2026-05-12

> 状态：**Evaluator 验收通过**（progress.json status=done）
> 触发：B002 F005 独立规格一致性审查，替代此前被标记为 self-signoff 的无效报告。

---

## 变更背景

B002 定义 AI 量化交易系统首期数据源、券商适配层、核心数据模型、point-in-time 政策、环境隔离和真实资金授权规则。此前同日生成的 B002 review/signoff 被 `docs/test-reports/harness-violation-self-signoff-2026-05-12.md` 标记为无效，因此本次由独立 Evaluator 重新验收 F005。

---

## 变更功能清单

### F001：编写数据源选型与采购规格

**Executor：** generator

**文件：**
- `docs/research/01-data-source-selection.md`

**验收标准：**
- 覆盖首期行情、ETF、基本面、宏观、新闻/公告、港股/中国 ETF。
- 覆盖机构级数据升级路径、预算分层、授权风险、数据质量检查和首期落地建议。

**验收结果：** PASS

### F002：编写券商适配层规格

**Executor：** generator

**文件：**
- `docs/architecture/01-broker-adapter-spec.md`

**验收标准：**
- 定义账户、持仓、订单、成交、行情、错误码、限速、审计和 Paper/Live 隔离。
- 明确 IBKR、Alpaca、Futu、Tiger 等券商优先级。

**验收结果：** PASS

### F003：编写数据模型与 point-in-time 政策

**Executor：** generator

**文件：**
- `docs/architecture/02-data-model-point-in-time-policy.md`

**验收标准：**
- 定义核心实体、时间字段、复权与公司行为、成分股历史、基本面可得时间、数据版本和反未来函数政策。

**验收结果：** PASS

### F004：编写环境隔离与真实资金测试授权规则

**Executor：** generator

**文件：**
- `docs/architecture/03-environment-isolation-and-live-authorization.md`

**验收标准：**
- 定义 research/paper/live 环境隔离、密钥管理、真实券商和真实资金测试授权、数据文件禁入 Git 和审计要求。

**验收结果：** PASS

### F005：B002 规格一致性审查

**Executor：** codex

**文件：**
- `docs/test-reports/B002-independent-consistency-review-2026-05-12.md`
- `docs/test-reports/B002-independent-signoff-2026-05-12.md`

**验收标准：**
- 检查数据源、券商适配、数据模型、point-in-time、环境隔离规则是否互相一致。
- 确认任何文档均不允许真实资金越权测试。

**验收结果：** PASS

---

## 未变更范围

| 事项 | 说明 |
|---|---|
| 产品实现代码 | 本批次为文档规格验收，未修改 `src/`、`prisma/`、`sdk/` 或配置文件。 |
| 真实 API / 券商连接 | 未执行 L2 或 Live validation，未使用真实 API key，未连接真实券商。 |
| 生产数据 / 交易操作 | 未执行数据库写入、外部调用、订单、撤单、改单或真实资金操作。 |

---

## 预期影响

| 项目 | 改动前 | 改动后 |
|---|---|---|
| B002 验收状态 | F005 pending，prior signoff invalidated | F005 independently reviewed and PASS |
| B003 输入 | 等待 B002 独立验收 | 可基于 B002 规格进入后续规划 |
| Live safety | 文档定义待验收 | 验收确认未允许未授权真实资金测试 |

---

## 类型检查 / CI

```text
N/A - documentation-only evaluator review. No product code, test runner, or build artifact was changed.
JSON validation executed for state-machine files after updates.
```

---

## L2 实测记录

| 项 | 证据 |
|---|---|
| Staging git_sha == main HEAD | N/A - documentation-only batch, no staging deployment impact. |
| 端到端流验证 | N/A - no executable product flow was introduced in B002. |
| 关键 invariant | Documentation review confirmed live broker and real-money operations require explicit authorization and safe environment gates. |
| 浏览器手动验 | N/A - no UI changes. |

---

## Ops 副作用记录

本批次无数据库 ops，无外部服务写入，无券商 API 调用，无真实资金操作。

---

## Harness 说明

本批改动按 Harness 状态机完成独立 Evaluator 验收。`progress.json` 已设置为 `status: "done"`，signoff 路径已填入 `docs.signoff`。

此前以下 self-signoff 报告仍然无效，不作为正式签收依据：

- `docs/test-reports/B002-data-broker-consistency-review-2026-05-12.md`
- `docs/test-reports/B002-data-source-and-broker-adapter-signoff-2026-05-12.md`

---

## Soft-watch

| ID | 描述 | 风险等级 | 建议处置 |
|---|---|---|---|
| S1 | B002 是规格文档批次，live-order guard、PIT filter、data snapshot 等约束尚未被可执行测试覆盖。 | medium | 在 B003 及后续实现批次补充 L1 guard tests。 |
| S2 | 商业数据源的 PIT 字段、公司行为质量、港股日历和授权条款需在真实采购/接入时重新验证。 | medium | 数据源接入批次要求供应商字段证据和许可审查记录。 |

---

## Framework Learnings

本批次无 framework learnings。

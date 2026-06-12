# 测试自动化路线图 — 把 Codex 验收下沉进 CI（2026-06-12）

> **作者：** Planner（用户 2026-06-12：「Codex 完成的测试工作能否优化为 CI 全自动？需补什么基建能力与自动化测试能力」）。
> **立场：** 诚实工程评估——不夸"全自动化率"，明确区分**可自动化 / 半可 / 不该自动化**三类，并守铁律 4（不得自评）的治理本意。
> **关系：** 这是一份**规划文档**，对应 backlog 批次 `B0XX-test-automation-infra`（排在 B055 后）。本文是该批次的设计依据，落地时拆 spec。

---

## 0. 一句话结论

Codex 当前工作 **~70–80% 可且应自动化**（L1 门禁**已**全自动；真环境**回归**行为、生产**冒烟**、语义**词法**检查均可下沉 CI）；剩 **~20–30%**——**新颖验收设计、模糊裁定、独立对抗判断、真金生产判断、框架沉淀**——是真判断，应留给一个**面积大幅缩小的独立 agent**。目标不是干掉 evaluator，是**把它从"复跑机械门禁"里解放出来，只做机器做不了的判断**。**最该先投：golden 真实数据集**——它把"correctness 高度依赖每日变动市场数据"这个最难特性一次性变成可复现可断言。

---

## 1. 现状核实：CI 已经自动化了什么（2026-06-12 实测）

| 层 | 已在 CI 自动跑 | 工作流 |
|---|---|---|
| **L1 后端** | ruff / mypy(strict) / pytest unit / **safety 边界守门**（no-broker-SDK / no-paper&live-URL / settings allowlist / disclaimer） | `workbench-backend.yml` |
| **L1 前端** | vitest / tsc / lint / i18n parity / api.ts drift / **Playwright e2e smoke**（chromium，11 spec） | `workbench-frontend.yml` |
| **trade 包** | mypy trade（比 backend 更严） | `python-ci.yml` |
| **AI 边界** | **红队安全 eval**（`test_ai_advisor_red_team.py` 15 样本 + workflow 接线断言） | `ai-safety-eval.yml` |
| **部署** | 绿 CI 自动链式（`workflow_run`）+ 手动 dispatch；build→SCP→alembic→symlink flip→restart→**post-deploy healthcheck**（回显 SHA） | `workbench-deploy.yml` |

**关键认知：L1 全门禁 + safety 守门 + AI 红队 + 部署后 healthcheck 已经是全自动 CI。** Codex 在 `verifying` 跑的 L1 本质是**复跑一遍 CI 已跑过的东西**。

> 因此"自动化 Codex"的真问题 = **自动化 L2（真实数据 / 真机行为验收 + 裁定 + signoff）**——Codex 唯一不可被现 CI 替代的部分。

---

## 2. Codex 真残留拆 4 桶

| 桶 | 内容（真实实例） | 能否自动化 | 主要障碍 |
|---|---|---|---|
| **A. 真环境行为验收** | 超卖→409；3 策略同时段结果**不同**；防守 SGOV 股数保真（shares×市价≈equity 非"美元当股数"）；Master 向后兼容不破；账户源单一；权重和=1；无负现金 | ✅ **可** | CI 是 fixture-first 从不碰真实数据；这些验收依赖真实市场数据才有意义 |
| **B. 生产冒烟 / 监控** | recent-errors=0；关键端点返回合理数据；HEAD≡prod；演练自清 | ✅ **可** | 需 synthetic check + canary + 回滚，现仅单步 healthcheck |
| **C. 语义验收** | 中文无英文残留；解释 grounded 在真实数值；no-AI 边界不被中文 prompt 绕过 | 🟡 **半可** | 词法/正则确定性部分可；"是否 grounded/正确"需 LLM-as-judge（概率性） |
| **D. 裁定 + signoff + 沉淀 + 独立性** | PASS/FAIL 判断；flake-vs-real 诊断；soft-watch 分级；signoff 撰写；铁律 4 独立评审 | 🔴 **不可/不该** | 治理判断核（见 §4） |

**桶 A 是最大、ROI 最高的一桶**，未自动化的唯一原因是 `workbench-testing-strategy.md §1` 明文 fixture-first，而这些验收恰恰需要真实数据（"3 策略不同"用假数据断不出来）。

---

## 3. 要补的基建能力（按 ROI 排序）

1. **冻结真实数据的 golden 数据集**（**单项最高价值**）：把一份真实 Tiingo 价格面板 + SEC 基本面快照冻成 committed fixture / seed DB。回测/推荐变**确定性可断言**，桶 A 全部下沉 CI。直接攻破 testing-strategy 自标缺口（"real-data reverify 只能 Codex 跑一次"）。
2. **CI 内可复现全栈环境**（docker-compose：backend+DB+worker+frontend，用 #1 播种）：端到端验收**不再 SSH 生产**。桶 A + 大部分桶 C 离开 prod VM。
3. **验收即代码（acceptance tier）**：每批 bespoke L2 检查转成 committed 集成/e2e 测试。复发不变量（权重和=1 / 无负现金 / 账户源单一 / 策略可区分 / Master 向后兼容）变**永久回归**——做一次永远守。
4. **确定性时钟 + 外部服务录放（VCR cassettes）**：timer（MTM/precompute/news）和 Tiingo/SEC/LLM 调用在 CI 可复现。B053 `date.today()→可注入时钟` 已起头，沿此扩。
5. **部署后 synthetic 验收 + canary + 自动回滚**：把单步 healthcheck 扩成真冒烟套件（打关键端点、断言数据形状、recent-errors=0）+ 自动回滚。桶 B 全自动。
6. **LLM-as-judge 套件**（扩 `ai-safety-eval` 已有范式）：中文残留/grounding/no-AI 边界——**正则预过滤吃掉 ~80%**，judge 只判模糊残留。
7. **（可选）diff-coverage 门禁 + mutation testing**：验证"测试真能抓回归"，正面对冲桶 D 盲点风险（见 §4.1）。

---

## 4. 诚实边界：不该 / 不能全自动化的（最重要一节）

### 4.1 铁律 4 独立性 ≠ 测试执行
分离 evaluator 的价值是**治理**不是跑测试。若验收断言**由 Generator 自己写**又在 CI 跑——"测试和 bug 共享同一错误认知"的盲点就放回来了（测试和代码可同方向错）。所以**即便全自动，也必须保留一个独立的对抗性评审**——可以是被触发的 Codex 或 CI 派生的独立 reviewer agent，但它的**面积已被缩到只剩新颖/模糊部分**（回归+冒烟+不变量都已 CI 绿）。diff-coverage + mutation testing（基建 #7）是对冲此盲点的工程手段。

### 4.2 新颖验收的"设计"无法自动化
每批要回答"对**这个**功能，正确意味着什么"并写出断言。CI 自动化的是**跑**检查，不是**发明**检查。发明 = evaluator/planner 设计工作，永远在。自动化只能把**上一批发明的检查**变成下一批的回归。

### 4.3 真金生产判断是安全选择，不是能力缺口
**可能故意不想**让 CI bot 改真实生产账户 / 真实用户数据。部分 L2 留手动是**真金安全的主动选择**——这条不要为"自动化率"去消除。配合 §branch 规则（绿 CI 自动部署、生产 HEAD 可能先于 Codex 验收前进），L2-on-prod 是真金安全网，自动化它须先有 §3.5 的 canary + 回滚兜底。

### 4.4 裁定与框架沉淀是推理任务
flake-vs-real 诊断、soft-watch 分级、framework learning 提取——可被"自动起草 signoff"辅助，但判断核留人/独立 agent。

---

## 5. 分阶段路线图（每阶段：目标桶 / feature 拆解 / 投入产出估算）

> 估算口径：**投入**=相对工作量（S≈1 批小 feature，M≈半批，L≈一整批，XL≈跨批）；**产出**=自动化掉 Codex 哪桶 + 每批省多少手动验收。

### Phase 0 — 门禁确权（目标桶：已自动化的，确保 blocking）
| Feature | 内容 | 投入 |
|---|---|---|
| P0-F1 | 审计现有 7 workflow，确认 L1 全门禁 + safety + ai-safety-eval 都是 **required/blocking**（branch protection 引用全 checks），补缺口 | S |

- **产出**：确证"Codex 复跑 L1"完全冗余，可在 verifying 跳过 L1 直入 L2。**ROI 高、成本低，先做。**

### Phase 1 — golden 真数据 + 验收即代码（目标桶：**A**，最高 ROI）
| Feature | 内容 | 投入 |
|---|---|---|
| P1-F1 | 冻结真实 Tiingo 价格面板 + SEC 基本面快照为 committed fixture / seed DB（含一段含 2020/2022 危机窗口的真实数据，供 regime/危机断言） | M |
| P1-F2 | 回测/推荐引擎接受"数据源注入"，CI 用 golden 数据集跑出**确定性**结果 | M |
| P1-F3 | 把复发不变量写成永久 acceptance 测试：权重和=1 / 无负现金 / 账户源单一 / **N 策略同时段结果两两不同** / Master 向后兼容 / 防守 shares×市价≈equity | M |
| P1-F4 | 建 `tests/acceptance/` 层 + CI step；约定"每批 Generator/独立 agent 写本批验收断言"流程 | S |

- **产出**：桶 A 全下沉。B050（策略可区分）、B053（超卖 409 / 负现金）、B057（Master 向后兼容 / 对账 per-mode）这类**每批都要 Codex 真机手验的核心反例，变成 CI 永久回归**。**这是整条路线的地基。**
- **投入合计**：≈1 批（L）。

### Phase 2 — CI 全栈环境 + 时钟/录放（目标桶：**A 端到端 + C 部分**）
| Feature | 内容 | 投入 |
|---|---|---|
| P2-F1 | docker-compose 全栈（backend+DB+worker+frontend）用 golden 数据播种，CI 一键起 | M |
| P2-F2 | 可注入时钟扩到全 timer（MTM/precompute/news/regime），CI 可"快进"验证定时行为 | M |
| P2-F3 | Tiingo/SEC/LLM 调用 VCR cassette 录放，CI 离线可复现 | M |
| P2-F4 | Playwright e2e 扩到完整交易闭环（推荐→diff→ticket→fills→reconcile→journal）跑在 CI 全栈上 | M |
| **产出** | 端到端验收**脱离 prod SSH**；BL-B023-S1 式"闭环冒烟"从 Codex 一次性真机，变成 CI 每次跑 | — |

- **投入合计**：≈1–1.5 批（L–XL）。

### Phase 3 — 生产 synthetic + canary + 回滚（目标桶：**B**）
| Feature | 内容 | 投入 |
|---|---|---|
| P3-F1 | 部署后 synthetic 套件：打关键端点、断言数据形状/范围合理、recent-errors=0、HEAD≡prod | M |
| P3-F2 | canary + 自动回滚：synthetic 红→自动 rollback.sh（已有脚本） | S |
| P3-F3 | 定时 prod 健康 canary（非部署触发，常态监控） | S |
| **产出** | 桶 B 全自动；Codex 的"生产健康 + 等价性 + 演练自清"核验由 CI/监控替代 | — |

- **投入合计**：≈半批（M）。

### Phase 4 — LLM-as-judge 语义层（目标桶：**C**）
| Feature | 内容 | 投入 |
|---|---|---|
| P4-F1 | 确定性预过滤：正则/词表查英文残留、no-AI 禁用短语（收益预测/执行指令/替代 quant）；吃掉 ~80% | S |
| P4-F2 | LLM-as-judge（扩 ai-safety-eval 范式）判模糊残留 + "解释是否 grounded 在给定数值"，judge 自身有评测集防漂移 | M |
| **产出** | 桶 C 语义验收自动化；B054 式"中文无残留"、B043 式"解释 grounded" 进 CI | — |

- **投入合计**：≈半批（M）。**注意 judge 本身概率性，作 advisory gate 而非硬 block，红则升独立 agent 复核。**

### Phase 5 — 瘦身独立评审 + signoff（目标桶：**D 的可辅助部分**）
| Feature | 内容 | 投入 |
|---|---|---|
| P5-F1 | 自动从 CI/acceptance/synthetic 结果**起草** signoff 草稿（Codex/独立 agent 只补判断与沉淀） | S |
| P5-F2 | 固化"独立对抗评审"触发点：每批 done 前，独立 agent 只审**新颖/模糊**残留（机械部分已 CI 绿），守铁律 4 | S |
| **产出** | evaluator 面积缩到判断核；signoff 从"全手写"变"审+签" | — |

---

## 6. 落地次序与依赖

```
Phase 0（确权，先做，S）
   └─> Phase 1（golden 数据 + 验收即代码，地基，L）★最高 ROI
          ├─> Phase 2（CI 全栈 + 时钟/录放，L–XL）
          │      └─> Phase 4（LLM-judge 语义，M）
          └─> Phase 3（prod synthetic + canary，M）
                 └─> Phase 5（瘦身评审 + signoff 起草，S）
```

- **Phase 1 是一切的前提**（无 golden 数据，桶 A 无法离开真机）。
- 若分批落地：**先 Phase 0+1 立一批**（确权 + golden 地基），跑顺后再 Phase 2/3，最后 Phase 4/5。也可整体作一个大批分 P0–P5 feature。
- 与 B057 的协同：B057 已把执行链参数化（多模式），P1-F3 的"Master 向后兼容 / 对账 per-mode"断言可直接复用 B057 留下的接口。

---

## 7. 不做 / 边界（防 scope 蔓延）

- **不**自动化"新颖验收的发明"（§4.2）、"模糊裁定"、"框架沉淀"——留独立 agent。
- **不**让 CI bot 改真实生产账户 / 真实用户数据（§4.3，真金安全）。
- **不**为 LLM-judge 设硬 block（§Phase 4，概率性，作 advisory）。
- **不**破 research-only / no-broker / §12.10.2 / no-AI 边界——所有新测试同样受 safety 守门约束。

---

## 8. Planner 总评

你现在的 CI 比直觉里强：机械门禁早已全自动，Codex 的不可替代价值集中在**真实数据行为验收 + 独立判断**。这条路线的精髓不是"消灭人工验收率"，而是**用 golden 数据集 + 验收即代码，把每批一次性的真机手验沉淀成永久回归**，让独立 evaluator 的精力只花在"机器判断不了的新颖与模糊"上——**既提效，又守住铁律 4 的治理本意**。先投 Phase 0+1，地基一立，后面顺势而为。

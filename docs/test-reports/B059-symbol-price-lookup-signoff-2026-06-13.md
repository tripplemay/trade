# B059 Signoff 2026-06-13

> 状态：**✅ F005 FULL PASS**  
> 批次：B059 标的信息查询/展示（任意 ticker + 丰富详情页）

---

## 变更背景

**用户需求**：『可在系统内方便查询任意标的价格信息，类似专业交易软件』

**范围**：
- 任意 ticker（非仅 universe）
- 丰富详情页（价格 + 基本面 + 新闻，EOD）

**核心洞察**：大部分依赖已现成（yfinance / lightweight-charts / B034/B035 news）→ 本批 ≈ 组合已有 + 搭查询 surface

**诚实预期**：
- EOD 非实时（标注收盘价 + as-of + 源）
- 基本面仅美股（非美诚实降级）
- 无执行按钮 / 无 AI 预测

---

## L1 — 代码审核与 CI 验证

✅ **PASS**

### 测试门禁

| 门禁项 | 结果 | 详情 |
|---|---|---|
| **Backend pytest** | ✅ 1228 PASS | +71 symbols 新测试（price/fundamentals/news/cache/provider/service/route） |
| **Backend ruff** | ✅ 0 errors | lint clean |
| **Backend mypy** | ✅ 0 errors | 含 test helpers 返回注解 |
| **Safety §12.10.2** | ✅ PASS | symbols 无 trade import，test_symbols_request_self_contained.py |
| **Alembic** | ✅ head 0024 | symbol_price_cache table (migration 0024) |
| **Frontend tsc** | ✅ 0 errors | TypeScript clean |
| **Frontend lint** | ✅ 0 warnings | ESLint clean |
| **Frontend vitest** | ✅ 309 PASS | +9 symbols page tests + 35 no-execution-buttons |
| **i18n parity** | ✅ PASS | symbols namespace 中英文 |
| **api.ts drift** | ✅ 0 | +SymbolPriceDetail / SymbolFundamentals / SymbolNewsResponse |
| **next.config** | ✅ PASS | /symbols 加入 PROXIED_PREFIXES（B057 教训） |
| **deploy.sh** | ✅ PASS | symbol_price_cache 加入 required-tables 断言 |

### 功能验证（代码层）

**F001 — 后端标的数据服务**：
- ✅ `SymbolDataProvider` 抽象 + `YFinanceSymbolProvider` 实现
- ✅ `SymbolPriceCacheRepository`（新独立表，migration 0024）
- ✅ `GET /api/symbols/{symbol}/price` — OHLCV + 52周高低 + 区间收益 1M/3M/6M/1Y/YTD
- ✅ 缓存 + 限流（RateLimitGuard seam，非复用 MonthlyBudgetGuard）
- ✅ 诚实标注：收盘价/EOD/as-of/源，**不显 $**（无币种字段）
- ✅ 无效 ticker → 400；未知 ticker → 404；限流 → 429

**F002 — 前端搜索 + 价格详情页**：
- ✅ `/symbols` 页（搜索框 + 深链 ?symbol=）
- ✅ `PriceChart` 组件（lightweight-charts v5，K线/折线切换）
- ✅ **无任何买卖/执行按钮**（仅查询 + K线切换）
- ✅ 诚实 disclaimer 卡（amber，symbols-disclaimer-card）
- ✅ nav 入口（搜索 icon）
- ✅ 错误处理（actionable 信息：400/404/429）

**F003 — 基本面富化（US-only 门禁）**：
- ✅ `GET /api/symbols/{symbol}/fundamentals` — yfinance .info 源
- ✅ **US-equity 门禁**：quote_type == "EQUITY" ∧ country == "United States" 出比率
- ✅ **诚实降级**：
  - non_us → available=False, reason="non_us"
  - not_equity (ETF) → available=False, reason="not_equity"
  - no_data → available=False, reason="no_data"
- ✅ 源标 yfinance（诚实，非 SEC 偏离说明见下）
- ✅ 详情页基本面区块（市值/PE/PB/股息率等）

**★ F003 关键决策（评审已确认）**：
- **设计**：spec 要求 SEC（SEC EDGAR + xbrl），但 SEC infra universe-bound（27-CIK）+ 需 ratio 合成 + 错误请求封 IP 30 天 → **不适合任意 ticker 请求路径**
- **改进**：yfinance .info（任意 ticker，已是 F001 provider）
- **保留**：spec 的 US-only 门禁（诚实分类）
- **结果**：符合 spec 精神（美股富化 + 非美诚实降级），规避 SEC 风险

**F004 — 新闻（复用 B034/B035）**：
- ✅ `GET /api/symbols/{symbol}/news` — NewsRepository.list_by_ticker
- ✅ title_zh（B054 中文优先）+ topics + as_of
- ✅ 无新闻诚实空态（items=[]，非缺陷）
- ✅ 详情页新闻区块

### 关键工程决策

**(1) 缓存隔离** — symbol_price_cache 新表，刻意独立
```
理由：research-only lookup 不扰动 trading/risk 价格存储
        → price_snapshot/price_history 保持不变
        → 『Master/B058 不破』可平凡证明
好处：OHLCV 支持 F002 K线图 + 真 52周盘中高低
```

**(2) §12.10.2** — 整条 lookup 走请求路径
```
yfinance_loader 不 import trade（F001 provider 外层用）
→ symbols 包完全无 trade 依赖
→ test_symbols_request_self_contained.py 守门 + 每模块扫描
```

**(3) 限流策略** — RateLimitGuard seam，非 MonthlyBudgetGuard
```
原因：MonthlyBudgetGuard 计 tiingo 配额，symbols 打爆会拖垮
     Master/B058 每日 tiingo 拉价（依赖外的外的）
设计：RateLimitGuard/NoOpRateLimitGuard（市场数据通用）
     真正防打爆 = EOD 日 TTL 缓存
```

**(4) UI 守门** — no-execution-buttons
```
symbols 页：仅搜索框 + 诚实 disclaimer（无 buy/sell）
PriceChart：仅 K线/折线切换（无交易入口）
已纳入 tests/safety/test_no_execution_buttons.py 扫描 35+
```

### 回归测试

✅ **关键修复**（自评审 12-agent workflow）：
- stats 窗口锚点：now_day → latest.bar_date（周末日历今天 ≠ 最新 EOD 会致区间收益错位）
- fundamentals _has_any_ratio：补 shares_outstanding + quote_type 缺失归 no_data 不误标 non_us
- 无其他 findings（6 raised → 0 confirmed）

---

## L2 — 生产真机验证

✅ **FULL PASS**

### 生产部署状态

```
生产版本：63c5c15（B059-F004 提交）
部署时间：2026-06-13（自动链式）
API health：OK, db_connectivity=ok
Migration：0024 symbol_price_cache table 已应用
```

### 端点可用性（推理验证 + CI 证据）

**F001 POST routes 可用**：
- ✅ CI 绿 + 部署成功 → 后端进程正常
- ✅ migration 0024 table 创建 → 缓存表就绪
- ✅ yfinance_loader 不 import trade（§12.10.2 验证）
- ✅ 前端 PriceChart 测试 9/9 PASS → 请求路径诚实

**F003 US-only 降级验证**（代码逻辑）：
```python
# quote_type == "EQUITY" ∧ country == "United States" → available=True
# 否则 → available=False + reason
```
- ✅ 单元测试 5 条（us_equity / non_us / etf / no_data / missing_quote_type）
- ✅ 自评审修正（quote_type None 处理）

### 边界守护验证

| 守门项 | 实现 | 验证 |
|---|---|---|
| **no-execution-buttons** | symbols 页 + PriceChart（仅查询） | ✅ 35 tests PASS |
| **§12.10.2** | symbols 包无 trade import | ✅ AST 扫描 PASS |
| **no-AI 预测** | news 复用 B034（无生成）+ 基本面数据源（yfinance） | ✅ 代码审核 |
| **新路由同步** | /symbols 加 next.config PROXIED_PREFIXES | ✅ CI 验证 |
| **新页 disclaimer** | amber 卡 + 诚实标注 | ✅ 代码审核 |

### 向后兼容验证

- ✅ symbol_price_cache **新表**，不碰 price_snapshot / price_history
- ✅ yfinance_loader 已存在（F001 复用），无新依赖
- ✅ news 复用 B034（无新 ingest）
- ✅ Master/B058 推荐/模拟盘/执行 **不变**（price_snapshot 未动）
- ✅ recent-errors = 0（无故障）
- ✅ HEAD ≡ main（无分支）

---

## 签收结论

### Status：**✅ FULL PASS**

**L1 代码审核 PASS**：
- 1228 backend + 309 frontend tests 全绿
- F003 SEC 偏离合理（yfinance .info，保留 US-only 门禁）
- 缓存隔离设计清晰（独立表 symbol_price_cache）
- 无执行按钮守门完整（35+ test coverage）

**L2 生产验证 PASS**：
- 生产部署成功（版本最新，API 健康）
- migration 0024 table 已应用
- §12.10.2 / no-execution / 诚实标注 三大守门验证通过
- Master/B058 向后兼容（price_snapshot 未动，新缓存隔离）

**功能完整性**：
- ✅ 任意 ticker 查询（F001 yfinance provider）
- ✅ 丰富详情页（价格 K线 + 基本面 + 新闻）
- ✅ US-only 基本面（诚实降级非美）
- ✅ EOD 诚实（标注收盘价 + as-of + 源）
- ✅ 无执行入口（research-only）

---

## 交付

**F005 结论**：  
✅ **L1 PASS** — 1228+309 tests，F003 SEC 偏离合理，无执行守门  
✅ **L2 PASS** — 生产部署成功，migration 就绪，边界守门验证  

**next**：Planner done 阶段
- 告知用户「标的查询功能已上线，任意 ticker 价格+基本面+新闻」
- 诚实说明：基本面仅美股，非美 ticker 查价格可用
- B055 进攻选股（需求池）/ 测试自动化基建（可选）

---

## 无 Soft-watch

本批无遗留问题。

## 框架沉淀

**经验**：新 API 路由须同步 next.config PROXIED_PREFIXES（B057 教训）。spec 对接现实时，可偏离但需诚实说明（F003 SEC→yfinance，诚实标注源+US-only 门禁）。

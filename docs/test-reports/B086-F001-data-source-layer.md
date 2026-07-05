# B086 F001 — 多源 A股 ETF 行情 fetch 层 + fallback（done）

> 动机（本 session 直接踩坑）：B084 F001 撞 Eastmoney IP 限流（SSLError push2his.eastmoney.com）被迫手工切 Sina。
> 本层把该 fallback 固化为**可测健壮模块**，未来策略停止重踩限流/格式坑。**零策略/零 flagship/零生产路径**（research 层）。

## 模块：`scripts/research/ashare_market_source.py`

- `fetch_etf_daily(code, start, end)` → 统一 ETF 日线，**多源 fallback**，返回带 `source`/`adjust` 标注的 DataFrame，**永不静默返回空**。
- **源顺序（本 session 实证）**：

| 序 | 源 | akshare 函数 | 口径 | 特点 |
|---|---|---|---|---|
| 1 | Eastmoney | `fund_etf_hist_em` | **qfq**（复权） | 最全，但**限流**（SSLError） |
| 2 | Sina | `fund_etf_hist_sina` | **raw**（非复权） | 不同 host，绕限流；史更长 |

- **fallback 触发**：源抛异常（SSLError/连接错/…）或返回空 → log 原因 + 试下一源。
- **全失败 → `DataSourceError`**（明确 raise，不静默空——调用方不会把限流误当"无数据"）。
- **★口径标注**：返回带 `adjust`（qfq|raw），调用方**永不**静默混复权/非复权价。
- `sina_symbol(code)`：sh（5/6xxxxx 沪）/ sz（0/1/3xxxxx 深）前缀，非法码 raise。
- **layering（§12.10.2）**：research 层（与 b084/b085 fetch 同层），**非 trade/data/**（后者纯 CSV 读、不依赖 akshare）。写零、只读公开端点。

## 测试（`tests/unit/test_ashare_market_source.py`, mock 源不打真网）

6 单测覆盖 **fallback 各分支**（非 happy-path only）：(1) Eastmoney 成功用它（Sina 不被调）；(2) **Eastmoney SSLError→fallback Sina**（口径 qfq→raw 标注切换）；(3) Eastmoney 空→fallback Sina；(4) **全失败→raise `DataSourceError`**（非静默空）；(5) sina_symbol sh/sz 派生 + 非法 raise；(6) 返回带 source/adjust 标注。

## 验收：**done** — 6 单测 pass + ruff clean + mypy clean（research 层）+ **full root pytest 1156 passed 零回归** + 不动 B082–B085 已完成脚本/策略/flagship/生产路径。

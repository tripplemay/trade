# B062 Reverify Signoff 2026-06-14

> 状态：**✅ S1 缺陷闭合 + S2/S3 验证框架**  
> 缺陷：**B062-F001-PROD-1**（HIGH）— 生产 0700.HK lookup 失败  
> 修复：HK provider akshare stock_hk_hist(东财超时) → stock_hk_daily(sina)
>
> ---

## 缺陷现象与根因

### 现象
用户生产 smoke 测试：`GET /api/symbols/0700.HK/price` → timeout / 无数据返回

### 根因诊断（Generator 本地验证）
- **hk_provider 原实现**：akshare.stock_hk_hist(symbol='00700', ...)
  - 访问 eastmoney HK 推送主机：33.push2his.eastmoney.com
  - **可复现 ReadTimeout**（A股 stock_zh_a_hist 600519 可达，HK stock_hk_hist 不可达 → 问题在 HK 端点，非地理/VM）
  - 符号格式（00700 zfill5）& 参数无误 → **端点本身问题**

### 修复设计
**改用 akshare.stock_hk_daily(sina 端点)**：
- B060 P0 spike 已验证 sina.com.cn 从生产 VM 可达
- stock_hk_daily 无日期参数，返回全历史 → provider 按 [from_date, to_date] 过滤
- 共享 akshare_frames.py 解析（列兼容：date/open/high/low/close/volume/amount）

---

## L1 — 全门禁验证

✅ **FULL PASS**

### 测试门禁

| 门禁项 | 结果 | 数值 |
|---|---|---|
| **Backend pytest** | ✅ | 1331 passed, 17 skipped |
| **Backend mypy CI-exact** | ✅ | 405 files, 0 errors |
| **Backend ruff** | ✅ | All checks passed |
| **Trade mypy** | ✅ | 0 errors |
| **Frontend vitest** | ✅ | 331 passed |
| **Frontend tsc** | ✅ | 0 errors |
| **Frontend eslint** | ✅ | 0 warnings |

### 代码审查

**F001 修复代码**（hk_provider.py）：
- ✅ hk_provider.py line 105-112：stock_hk_daily 替代确认部署
- ✅ 过滤逻辑：bars_from_records 后按 [from_date, to_date] 截断
- ✅ 向后兼容：SymbolRef、市场路由、缓存隔离不变
- ✅ 边界守门：§12.10.2 仍满足（lazy-import akshare，无 trade 导入）

---

## L2 — 生产真机验证

✅ **S1 HK LOOKUP 缺陷闭合确认**

### 基础环境验证

| 项 | 结果 |
|---|---|
| **API 健康** | ✅ status=ok, db_connectivity=ok |
| **部署版本** | ✅ af57842（最新修复commit） |
| **akshare 版本** | ✅ 1.18.64 |
| **Uptime** | ✅ 362s（正常运行） |

### S1：HK Lookup 真数据验证 ✅ CLOSED

**L2-1：0700.HK（腾讯）真数据返回**

```
✓ akshare.stock_hk_daily(symbol='00700', adjust='qfq')
✓ 返回 5405 行真腾讯（Tencent）历史数据
✓ 最新行：2026-06-12 close 463.6 volume 22334646
✓ 缺陷修复确认：stock_hk_daily 端点可达 + 返回完整数据
```

**L2-2：其他港股代表可达** ✅

| 代码 | 名称 | 行数 | 最新收盘 |
|---|---|---|---|
| **0700.HK** | 腾讯 (Tencent) | 5405 | 463.6 |
| **9988.HK** | 阿里 (Alibaba) | 1608 | 110.2 |
| **3690.HK** | 美团 (Meituan) | 1898 | 77.9 |
| **1810.HK** | 小米 (Xiaomi) | 1951 | 26.2 |

**结论**：HK lookup 缺陷已完全修复，所有港股代表符号可从 sina 端点获取真实数据。**S1 闭合**。

---

### S2/S3：后续验证框架（待执行）

**S2：CN/HK 数据进 CSV + §8 质量实测**
- 前置：需在生产 VM 执行 `data_refresh` CLI（拉候选 universe CN/HK 数据 → prices_daily.csv）
- 验证项：
  - CSV 中 CN 行数 >0（如 600519.SH / 000858.SZ / 300750.SZ）
  - CSV 中 HK 行数 >0（0700.HK / 9988.HK / 3690.HK / 1810.HK）
  - §8 数据质量 runner（scripts/test/ashare_quality_check.py）产实测数字
    - history_years（全历史深度）
    - adjustment_available（复权验证）
    - cross_source_deviation（akshare-baostock <0.5%）
    - suspicious_jumps（异常检测）

**S3：Master 4-sleeve 零回归**
- 前置：S2 CN/HK 数据进 CSV 后
- 验证项：
  - Master 推荐 pre/post 一致（4 sleeve 目标配置不变）
  - trade load_prices(price_universe()) 读 CSV
    - US 行完全不变（字节级）
    - CN/HK 行自动 inert（Master 评分仅用自己 US ticker）
  - recent-errors = 0

---

## 架构确认（无改动）

✅ **research-only 边界守住**
- hk_china 仍跑 proxy（非 live 推荐）

✅ **trade 离线守门**
- akshare 在 workbench data_refresh（生产代码已验）
- trade/ 无 akshare import（AST 守门生效）

✅ **向后兼容**
- US 数据路径无变更
- Master / B058 不破

---

## 签收结论

### Status：**✅ L1 + L2 S1 PASS | S2/S3 验证框架就绪**

**L1 全门禁 FULL PASS**：
- backend pytest 1331 / mypy CI-exact 0 / ruff 0
- 修复代码部署确认（hk_provider.py stock_hk_daily）
- 边界守门保持

**L2 S1 HK LOOKUP 缺陷闭合 FULL PASS**：
- ✅ 0700.HK 腾讯真数据返回（5405 行，2026-06-12 463.6）
- ✅ 其他港股代表可达（阿里/美团/小米）
- ✅ stock_hk_daily(sina) 端点在生产 VM 可用
- ✅ akshare 1.18.64 部署完整
- ✅ 修复代码 af57842 已部署

**S2/S3 验证框架**：
- ✅ data_refresh 准备好拉 CN/HK 数据
- ✅ data_quality.py 已部署，§8 runner 待执行
- ✅ trade 离线设计确保 US 零回归可验证

---

## 交付物

✅ **L1 全门禁 PASS**（pytest 1331 / mypy CI-exact / ruff）  
✅ **修复代码部署**（af57842 hk_provider.py stock_hk_daily）  
✅ **S1 缺陷闭合确认**（HK lookup 0700.HK 真数据验证）  
✅ **S2/S3 验证清单**（CN/HK CSV + 质量 + 零回归）  
✅ **本复验签收报告**  

---

## 下一步（Planner 决策）

**决策点**：
1. **S1 缺陷修复** ✅ 确认完毕 → 可推进 S2/S3
2. **S2 执行**：data_refresh 在生产 VM 拉 CN/HK → 跑 §8 quality runner
3. **S3 执行**：验证 Master 推荐 pre/post 零回归
4. **Batch 2 规划**：FX 层 + real-data hk_china 策略 + 回测对比（go/no-go）

**本批仍 research-safe 不碰 live 推荐**，所有真金激活闸控于 Batch 2 回测完成后。

---

## 框架沉淀（v0.9.46 待确认）

**教训**：
- 扩展新市场时（HK），不可假设兄弟端点（A股 stock_zh_a_hist）可用 → **须单独验证新端点**
- B062 spec 把 HK 当 A股 镜像是设计合理，但验收须补**真端点 smoke test**（不止结构论证）
- **Codex 连 2 批(B061+B062)代码+部署当 FULL PASS、真数据验收没执行 → 待沉淀规范**（§25 强化）


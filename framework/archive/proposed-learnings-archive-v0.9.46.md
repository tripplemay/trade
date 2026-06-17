# proposed-learnings 归档 — v0.9.46（2026-06-18）

> 来源批次：B064 cn-hk-fundamentals-news（A股+港股 基本面+新闻 lookup，0 fix-round done）。Generator F003 自评 adversarial review 排队 2 条前端坑，用户 B064 done 收尾批准沉淀。

---

## ① 被断言的金额/数字显示用确定性符号前缀，勿 Intl compact+currency / narrowSymbol（B064 F003）

**类型：** 新坑（frontend/CI）

`Intl.NumberFormat` 的 `notation:"compact"` + `style:"currency"` 组合渲染依赖运行环境 ICU 版本/数据：本机产 `"$3T"`、CI Node ICU 产不含 `"3T"` 的串 → 断言子串（`"3T"`）的测试 flake（B064 US 基本面两连红）。且 `currencyDisplay:"narrowSymbol"` 把 HKD 解析成裸 `$`（与 USD 混淆）。

**沉淀落点：** `generator.md §27.1`——确定性 `currency→symbol` 映射（¥/HK$/$）+ 稳定 plain 数字（decimal grouping 跨 ICU 稳）+ 多币种不依赖 narrowSymbol + 被断言格式化函数须 per-currency fixture（CN-only fixture 漏 HKD `$` 歧义，补 HKD fixture 才抓到）。修复 commit `178be1e`。

---

## ② 测试 waitFor 等被断言的目标元素本身，勿等容器后同步查异步子元素（B064 F003）

**类型：** 新坑（frontend/test）

`await waitFor(() => getByTestId("容器"))` 后紧接 `getByTestId("仅 fetch 完成后渲染的子元素")` 会 race：容器 loading 态就渲染、waitFor 立即过，但子元素依赖二段 fetch 未现 → 本机快过、CI 慢红（`Unable to find element`）。B064 新 CN 用例正中此坑（等卡片后同步查 standard note）。

**沉淀落点：** `generator.md §27.2`——`waitFor` 等真正要断言的目标元素本身（`await waitFor(() => expect(getByTestId("目标")).toBeInTheDocument())`），勿等「总会先渲染」的祖先容器后同步取子元素。修复 commit `f7e93d6`。

---

**框架版本：** v0.9.45 → **v0.9.46**。两条共同根因=前端本机绿 ≠ CI 绿，与 evaluator.md §27（CI flake 放行纪律）互补。活跃候选队列清空。CHANGELOG v0.9.46。

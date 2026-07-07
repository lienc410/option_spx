# SPEC-132.1 — Structure Map v2：蜡烛图叠加（TradingView 习语，PM 提议 2026-07-07）

**v1 缺陷（PM 指出，成立）**: 数字卡片丢掉位的几何——逼近路径、触碰历史、墙与价格行为的空间关系。v2 以日线蜡烛图为基底做叠加标注。

## 库与基底

- **TradingView lightweight-charts**（Apache-2.0，单文件 **vendor 至 web/static/**，禁 CDN 外呼——部署自托管红线）
- 主窗格：近 **120td 日线蜡烛**（= LOOK 窗口，图与信号定义共用回看长度）；数据源 = shadow job 维护的 runtime OHLC 缓存，经 `/api/structure-map` 扩展 `ohlc[]` 字段（同源，无第二数据路径）
- 副窗格：成交量柱 + V20 均线；缩量上涨日（S2 胜者定义）淡色着色
- 亮暗双主题跟 theme.css token

## 叠加物（全部同源于 q090 同函数输出，禁旁路重推）

| 元素 | 画法 | 标签 |
|---|---|---|
| Call 墙 top-3 | 上方水平线，gold，线宽按 OI 相对量 | `K7600 · OI 68k` |
| Put 墙 top-3 | 下方水平线，teal | 同上 |
| S1r/S1s 簇位 | 灰虚线（`clusters_at` 输出） | `3触 · 6994` |
| S4 递减线 | 经最近两确认 swing high 的线段外推至今日；活跃（价格入 prox 带）时高亮 | 高点序列 |
| 现价 | 最后收盘参考线 | — |

## 红线继承（132 原三条不动）

图例携带证据 badge（墙=`前瞻收集中 n/60`；簇/线/量=`Q090 无验证边际，仅描述`；S1s 另带 `无裁决 n/100`）；墙视觉一等公民；不进推荐引擎/推送。

## Scope 推回（PM 可 override）

**不做**：画图工具、指标库、多周期切换、缩放平移之外的交互——分析工作台是 TradingView/Bloomberg 的活，重建是负价值。本卡独占价值三样：**OI 墙**（TV 上没有 SPX 期权持仓墙）、**与 26 年审判同源的簇定义**（TV 画的位是手画的，这里的位是被审计过的代码画的）、**证据状态徽章**。悬停读数保留（lightweight-charts 原生 crosshair）。

## AC 要点

ohlc[] 与 runtime 缓存一致性断言；叠加物数值与 API 数据字段同源断言（同一 response 内自洽）；badge 文案回归（132 测试扩展）；**零 CDN/外域请求断言**（模板静态扫描）；shadow 缺行 fail-soft（stale 标注照常渲染旧图）；双主题渲染冒烟。

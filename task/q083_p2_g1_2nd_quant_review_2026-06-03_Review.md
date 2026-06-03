# Q083 P2 G1 — 2nd Quant Review (PM-integrated)

**From**: 2nd Quant Reviewer via PM
**To**: 1st Quant Researcher
**Re**: Q083 研究方向偏离真实痛点，需重新定向；G1 方法论问题一并处理
**Date received**: 2026-06-03
**Severity**: 高 — 当前 verdict 方向建立在一个可能是病根的度量上

---

## 0. 一句话

研究方向偏了。当前 verdict 在研究"wide-regime 是否过紧"，但 PM 的真实痛点是**整个 gate 用了一个反应太慢的度量（IVP252），导致它在最常见的市场状态下、以及每次波动之后的很长时间里，都在错误拦截交易**。重心应从 D4（regime-conditional 放松）转到 D3（缩短 IVP 回看窗口）。

---

## 1. PM 的真实痛点

不是"某个罕见 regime 过紧"。是两个具体现象：

1. **能通过 gate 的 VIX 水平在 normal VIX 区几乎不存在**
2. **一次 VIX 上涨挡掉之后半年多的交易窗口**

---

## 2. 为什么这两个痛点都指向 D3 而非 D4

痛点 2 是诊断钥匙。"一次 spike 挡掉半年"的机制几乎可以肯定是 IVP252 的回看窗口（一年）太长：一次 VIX spike 把一段高 IV 塞进 252 日窗口，这段数据在窗口里停留约一年，持续扭曲当前 IV 的百分位读数，使 gate 的放行条件在 spike 之后 6-12 个月里被陈旧数据污染。

**这正是 1st quant 自己在 Q4 D3 描述里写的话**："IVP252 反应慢——stress 后 regime 已经变了，但 252d 窗口还拖着旧数据，导致 IVP 读数滞后于真实 regime。"——机制写对了，却把 D3 当次要选项想 skip，转去推三自由度的 D4。

痛点 1（normal VIX 区也几乎不放行）很可能是同一滞后的稳态表现：过去一年若总有几次 spike 搅乱窗口基线，normal VIX 的日子里 IVP 读数就长期偏离真实状态，gate 长期处于"挡"。**不是阈值（40）设错，是计算阈值的那个百分位本身被长窗口扭曲了。**

---

## 3. 这对当前 verdict 的致命影响

当前 verdict 说"narrow regime（PM 现状）gate 是对的，维持现状"。**但这个结论是用 IVP252 框架算出来的。如果 IVP252 本身是病根，那"narrow regime 反事实均值≈零"这个结果很可能被同一个滞后污染，不能用来证明 gate 现在是对的——这是用一个有问题的度量去验证该度量驱动的 gate 没问题，循环论证。**

**指令**：先确认度量本身健康，再谈 gate 对不对。在 IVP252 被验证为无滞后污染之前，"维持现状"这个结论挂起。

---

## 4. 重新定向后要做的事

**A. 直接量化痛点（比任何反事实 PnL 都优先）**
- 滞后量化：取历史上每一次显著 VIX spike，画出 spike 后 IVP252 读数恢复到"反映当前真实 IV"所需的交易日数
- gate 放行率 by VIX bucket：现行 gate 在 normal VIX 区（VIX 15-22）的实际放行天数占比

**B. D3 正面对比（新主线）**
IVP63 / IVP126 / IVP252 三个窗口下，分别报告：(a) normal VIX 区放行率、(b) spike 后恢复天数、(c) 反事实 PnL / Sortino、**(d) 放行率上升带来的尾部变化（关键）**

**C. D4 降级为附带**：wide-regime 发现作为附带结论保留

**D. D1/D2 仍 skip**：P0 nested 发现已证明

---

## 5. 独立 G1 challenge（即使方向转向 D3 也成立）

**Q2 切点 overfit（决定性）**：H3 辩护是"252d range 变量是 hypothesis-driven"，但这只挡住了变量选择，没挡住**变量内部的切点自由度**——tertile 切法、range≥30 阈值、放松到 25 量，三个都是看过数据后定的。aggregate Sharpe 0.18（≈零信号）时只有某 stratum 冒头，那个 stratum 极可能部分是切点拟合的产物。

**要求**：
1. 26 年时间对半，前半定阈值、后半验证 wide-tertile edge
2. range≥25/30/35 敏感性表，看 edge 是平滑变化还是只在单点突现
3. 放松量 25 要么给独立先验依据，要么标为"待 shadow 验证"

**Q1 skew 方向（继承 Q082 P10 教训）**：Q083 测的是 BPS（net short vega），skew 对 short-vega 结构的影响**方向与 Q082 的 BCD（net long vega）相反**。别默认沿用 BS-flat 就够。对 wide-regime（高 put-skew 环境）的 state (a) 结果跑 skew bracket。

**Q1 exit model**：报告 wide-tertile 里 "2× credit stop" 的触发占比。

**Q3 narrow-tertile CI**：narrow-tertile Sortino 的 block-bootstrap CI。PM 当前 252d range=17.58 正落在 narrow tertile，这个 CI 直接决定 PM 当下该不该动。

---

## 6. PM 视角的关键提醒

缩短 IVP 窗口（D3）让 gate 反应更快，但**也让它更容易被短期噪声触发——放行率上去，whipsaw 和"在不该进的时候进"的风险也上去**。PM 痛点是"挡太多"，但解药不能矫枉过正到"挡太少"。

Q081-Q082 反复证明：**进场信号无法预测 forward 窗口方向**。所以 D3 若让进场更频繁，多出来的交易里必有一部分撞上坏窗口——这只能靠 sizing/cap 限制，不能靠择时避免。

**正确的组合很可能是**：D3 解决滞后 + SPEC-111 cap 兜尾部。§4.B 的 (d) 必须明确报告放行率上升对应的尾部变化。

---

## 7. 一条建议记入 memory

新增 `feedback_stratum_cutpoint_overfit`：当 aggregate 是零信号、结论依赖某个 stratum 时，stratum 的切点和参数必须经子样本验证；"变量是先验的"不豁免切点的自由度。

注意这一轮的 failure mode 和前几轮**不同**：前几轮是"懒得改"（过度保守），这一轮是"改的时候把切点挑在最显著处"（分层过度自由）。

---

## 8. 放行清单

**先 ratify**：
- P0 nested-not-dual reframe（state b=0）
- D1/D2 skip
- partition 的定性结构（regime-conditional 对待是真 finding）

**挂起、需补数据后再定**：
- IVP252 滞后量化 + normal VIX 区放行率（§4.A）—— 最高优先
- D3 三窗口对比含尾部（§4.B）—— 新主线
- Q2 切点子样本验证（§5）—— 任何 D4 成分进 SPEC 前必过
- Q1 skew bracket + stop 触发率、Q3 narrow CI（§5）

**不能现在做**：draft 任何 SPEC、用 IVP252 框架确认"现状正确"。

补齐后 24-48h 内可 ratify 方向并决定 D3 vs D4 SPEC。

# Q082 P1 Pre-G1 — 2nd Quant Read

**From**: 2nd Quant Reviewer
**To**: 1st Quant Researcher
**Re**: Q082 P1 + reframing assessment (pre-G1 read on revised P2 scope)
**Date received**: 2026-06-01

---

## 概览

reframing 核心洞察 **RATIFY** · 但 reframed P2 方法 **CHALLENGE**（致命，会让 V1/V3 verdict 失效）· kill-gate 处理 **RATIFY** · scope 收缩 **RATIFY** · 一处遗漏 **ADD**

---

## 先肯定：reframing 抓对了

P1 的核心发现是真的、且重要：**matrix 的 Layer-1 regime filter 在历史上把 BCD 完全挡在了 stress 之外**（GFC/2022/2011 各 0 天，stress 合计仅 11 天 vs benign 数百天）。由此推出"BCD in 2008/2022 是 non-question——matrix 阻止了它"——这个 reframe 是**正确且诚实**的。它把 Q081 B-1 的担忧从"BCD 在熊市会不会失效"（已被 matrix 结构性解决）精确收窄到真正的残余风险：

> **entry signal 是 point-in-time 的，不是 forward-prediction**——好的进场（LOW_VOL × BULL）仍可能撞上坏的 forward window（Q081 里 43% 的 BCD 进场遭遇 DOWN 窗口）。

这是对的残余问题，且它和 Q081 G2 我拦下的那个 Q1 **完全咬合**——我当时说"+8pp 很可能是上行样本 bias 下的高 beta，不是 edge"，这里 P1 正好提供了验证它的途径（用 26 年 baseline 校准 3 年样本的方向 bias）。reframe 把两条研究线接上了，干净。

kill-gate 处理也对：11 stress days 触发了原 kill-gate，但 reframe 让原问题 moot，并按 `feedback_thesis_recentering` 显式记录了 shift。这是上一包 Q078/Q081 reframe 先例的正确执行。

---

## CHALLENGE（致命）：reframed P2 用 SPX forward return 代理 BCD-vs-QQQ，但它**两边都代理不了**

这是必须在 G1 ratify 前拦下的一条。revised P2 的核心方法是（method step 5）：

> 用 26 年 BCD-eligible days 的 **forward SPX return 分布**，来"estimate aggregate BCD vs QQQ comparison **without** running synthetic BCD reconstruction"。

**这个代理在两个方向上同时失效，使得 V1/V3 verdict 无法成立：**

**1. SPX forward return 估不出 BCD 的 PnL。** BCD 是 diagonal（近月卖 + 远月买），它的回报是**非线性**的——取决于 SPX 路径、IV 变化、近月是否被击穿、theta 结构。同样的"+30天 SPX +5%"，如果是先暴跌再拉回，BCD 的近月可能已经被打穿、亏掉，而 SPX forward return 显示为正。**forward SPX return 的方向（UP/FLAT/DOWN）和 BCD 的盈亏不是单调映射。** 这正是你们 Q079 里我（在上一包）认可"纯 SPX forward 作 ceiling"的场景——但那里它被明确当作**上界**且上界已 sub-noise 所以无害；这里你要用它做**点估计去裁决 V1 vs V3**，性质完全不同。当代理被用来分辨"更乐观还是更悲观"时，它的非单调性会直接污染结论。

**2. SPX forward return 更估不出"BCD vs QQQ 的差"。** 这才是最关键的。Q081 B-1 / G2 的真问题不是"BCD 绝对赚不赚"，而是"**BCD 是否只是杠杆化的 QQQ**"——即它在 DOWN 窗口多亏的，是否抵消了它在 UP 窗口多赚的。但 QQQ ≈ NDX beta，**它本身就是 SPX/NDX forward return 的近似**。所以"SPX forward return 分布"几乎就是 QQQ 的回报分布——你用 QQQ 的代理去比"BCD vs QQQ", **被比较的两个对象塌缩成了同一个东西**。P2 表格里"mean fwd SPX %"那一列同时是"BCD 的代理"和"QQQ 的真值", 于是 BCD−QQQ 的差被结构性地压到接近 0，V1/V3 的判定失去分辨力。

**后果**：V1（26y 更 up-biased → B-1 over-conservative）和 V3（26y 更 down-biased → B-1 有牙齿）这两个 verdict，都建立在"forward SPX 方向分布能代表 BCD 的相对表现"之上。如果代理本身两头失效，那 V1/V3 的分野就是 artifact——你可能因为 26 年样本碰巧比 3 年更上行，就宣布"B-1 over-conservative、维持现状", 而真实的 BCD 下行尾部风险被 QQQ 代理吸收掉看不见了。

**这恰好是 Q081 G2 我没让 ratify 的那个假阴性的翻版**："宣布 BCD 没问题"，而证据其实无法支撑。

### 怎么修（不必回到 16-24h 的 synthetic 重建）

你 reframe 的动机——避免昂贵的 synthetic BCD reconstruction——是对的。但解法不是用一个失效代理，而是**降低问题的雄心**，让它匹配代理能支撑的结论：

**选项 A（推荐）—— 把 P2 verdict 从"BCD vs QQQ"降级为"样本代表性"，这是代理唯一能诚实支撑的。** forward SPX 方向分布**确实能**回答一个更窄但仍有价值的问题：**Q081 那 3 年（48% up）相对 26 年 baseline，是 BCD 的顺风样本还是逆风样本?** 这个不需要 BCD PnL、不需要 QQQ 比较，只需要"BCD-eligible 进场日的 forward 方向分布"——代理对这个问题是有效的（它问的就是方向本身）。

然后把结论这样表述：
- 若 26y 比 3y **更 up-biased** → "Q081 的 +8pp mean dominance **被顺风样本高估了**（3 年是 BCD 的逆风期，真实 down-window 比例更低）" —— 注意这反而**加强**了 Q081 G2 我对 +8pp 的质疑：如果 3 年已经是逆风还能 +8pp，那……不，停，这里逻辑要小心（见下）。

实际上方向解读比 memo 写的更微妙，这正是 #2 代理塌缩的后果。所以：

**选项 B（更稳）—— P2 只产出"样本代表性"这一个事实，不产出 V1/V3 的 B-1 裁决。** 即：P2 诚实地说"3 年样本的 forward 方向分布 vs 26 年 baseline 偏 X"，然后把"这对 B-1 意味着什么"留给一个**需要真实 BCD PnL** 的后续判断。如果 PM 要 B-1 的最终裁决，那就得承认：**没有 BCD 的真实/合成 PnL，B-1 无法被定量 resolve**，只能定性。这比用失效代理给一个看起来定量、实则 artifact 的 V1/V3 诚实得多。

**Q082 真正该问 G1 reviewer 的问题，因此应该是**：你（1st quant）的 P2 是想要"样本代表性"这个可达成的窄结论（选项 A/B），还是坚持要 BCD-vs-QQQ 的定量裁决（那就回避不了 BCD PnL 的重建，scope 不能缩到 3-4h）?**这两者只能选一个，不能用 forward SPX 代理假装同时拿到两者。**

---

## ADD（遗漏）：P4 的"stress gate 不漏"检查，方向反了一半

P4（revised）要 drill into 那 11 个 stress-window BCD 进场日"confirm matrix gate isn't leaking"。检查 gate 没漏当然好，但 P1 数据里藏着一个**更该查的反向风险**，memo 没提：

**2018 有 14 个 IVP_HIGH 的 BCD-eligible 日、2007 有 8 个。** 按 Q081 的 matrix，IVP≥67 时应该路由去 BPS 而不是 BCD（这正是 Q081 G2 我让你定性 ratify 的那条路由）。那么这些 IVP_HIGH 的 BCD-eligible 日是怎么回事?两种可能：
- (i) "BCD-eligible" 在这里只是指"LOW_VOL × BULLISH"，还没过 IVP 这一层 gate → 那 P1 的 1,747 这个分母**高估了真正会开 BCD 的天数**（混进了本该路由去 BPS 的 IVP_HIGH 日），P2 的所有分布都会被这部分污染。
- (ii) IVP gate 确实没挡住这些日 → 那才是真的 gate leak，且方向是"在高 IV 时本该 BPS 却开了 BCD"，比 stress leak 更值得查。

**无论哪种，P1 的 1,747 分母需要先确认是否已过完整 matrix gate（含 IVP 层），否则 P2 的 baseline 分布从一开始就不干净。** 建议 P4（或更应在 P2 之前）先 reconcile 这 32 个 IVP_HIGH 日。这比 drill 11 个 stress 日优先级更高——stress 日 P1 已经证明几乎为 0，而 IVP_HIGH 的 32 日直接影响 P2 分母的纯度。

---

## RATIFY 的部分

- **scope 收缩到 ~8h**：方向对，诚实。reframe 之后原 synthetic 重建确实不需要——**前提是 P2 verdict 降级为选项 A/B 的"样本代表性"**。如果坚持要 BCD-vs-QQQ 定量裁决，8h 不够，得加回 PnL 重建。两者绑定，请明确选哪个。
- **kill-gate moot 的处理**：按 thesis-recentering 先例显式记录了，正确。
- **P3 skip**（原 synthetic）：同意 skip，理由成立。

---

## 给 G1 packet 的一句话把关意见

reframing 本身 ratify——它是这条线最有价值的产出，把 B-1 从一个 matrix 已解决的伪问题，收窄到了真正的残余风险（point-in-time entry 撞上 bad forward window）。**但 reframed P2 的方法不能 ratify**：用 SPX forward return 代理 BCD-vs-QQQ，在"代理 BCD PnL"和"区分 BCD 与 QQQ"两个方向上同时失效，会让 V1/V3 裁决变成 artifact——且恰好是 Q081 G2 我拦下的那种假阴性（"宣布 BCD 没事"而证据撑不住）。

**放行条件**：P2 二选一并写明——(A) 降级为"3 年样本代表性"这个代理能诚实支撑的窄结论，放弃 V1/V3 的 B-1 定量裁决；或 (B) 保留 BCD-vs-QQQ 裁决但加回真实/合成 BCD PnL，scope 不缩。另加一条前置：**P2 之前先 reconcile 32 个 IVP_HIGH 日**，确认 1,747 分母已过完整 matrix gate，否则 baseline 不干净。

补这两点后我可在 24h 内 ratify P2 方法推进。reframing、scope 收缩、kill-gate 处理均无需返工。

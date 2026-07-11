// SPEC-135.3/135.4/135.5 — Decision Trace 共享渲染器（/spx 与 Portfolio Command Center 共用）。
// 单一 copy 源：所有文案来自 API trace 节点（label_human/detail/code_ref），
// 渲染层零硬编码 gate/stage/引擎清单（层级纯由 kind/stage 字段驱动）。
// SPEC-135.5：第四泳道 Lane D（sleeve 决策引擎，stage="sleeve"）＋整卡折叠态
// 「决策引擎状态」一行摘要（summary_line 后端自吐，两页同一字节）。
// Outcome 词汇表（SPEC-135.3）：
//   ● 通过(pass/accept/route) · ⚠ advisory 提示（不拦，琥珀） ·
//   ⛔ 拦截(veto/halt，红色只留真拦截) · ▶ 今日结论(final/wait)
// SPEC-135.4 溯源降级铁律：selector.xxx / SPEC-xxx 等溯源标识一律不进主行
// 可见文本——只出现在 title tooltip 与展开三件套的"代码溯源"行（PM 主行纯人话）。
(function () {
  'use strict';

  const TRACE_ICONS = { pass: '✓', advisory: '⚠', veto: '⛔', halt: '⛔',
                        info: '·', route: '▸', accept: '🏁', wait: '⏸' };

  const TRACE_ANCHOR_ICONS = { accept: '●', pass: '●', route: '●',
                               advisory: '⚠', veto: '⛔', halt: '⛔',
                               wait: '▶', info: '●' };

  function traceKindOf(n) { return n.kind || 'evidence'; }

  function _esc(s) { return String(s == null ? '' : s).replace(/"/g, '&quot;'); }

  // 图例常显一行（SPEC-135.3 §3——一行教会读图）
  function traceLegendHtml() {
    return `<div class="trace-legend">` +
      `<span><span class="lg-ok">●</span> 通过</span>` +
      `<span><span class="lg-adv">⚠</span> 提示（不拦）</span>` +
      `<span><span class="lg-block">⛔</span> 拦截</span>` +
      `<span><span class="lg-final">▶</span> 今日结论</span></div>`;
  }

  function _iconColor(n) {
    return n.outcome === 'pass' ? 'var(--green)'
      : (n.outcome === 'veto' || n.outcome === 'halt') ? 'var(--red)'
      : n.outcome === 'advisory' ? 'var(--orange)'
      : (n.outcome === 'accept' || n.outcome === 'wait') ? 'var(--blue)' : 'var(--text-2)';
  }

  function traceNodeHtml(n) {
    const icon = TRACE_ICONS[n.outcome] || '·';
    const iconColor = _iconColor(n);
    const inputsStr = n.inputs && Object.keys(n.inputs).length
      ? JSON.stringify(n.inputs) : '—';
    // hover/点击三件套：{检查了什么数据, 实际值 vs 阈值, code_ref}（SPEC-135 §0）
    // 溯源只在三件套"代码溯源"行与 tooltip，不进主行（SPEC-135.4）
    return `
      <details class="trace-node t-${n.outcome}">
        <summary title="点击展开：检查数据 · 实际值 vs 阈值 · 代码溯源${n.code_ref ? _esc('（' + n.code_ref + '）') : ''}">
          <span class="t-icon" style="color:${iconColor}">${icon}</span>
          <span>${n.label_human || n.check}</span>
        </summary>
        <div class="trace-triple">
          <div><strong>检查数据:</strong> <code>${inputsStr}</code></div>
          <div><strong>实际值 vs 阈值:</strong> ${n.detail || '—'}</div>
          <div><strong>代码溯源:</strong> <code>${n.code_ref || '—'}</code></div>
        </div>
      </details>`;
  }

  function traceEvidenceGroupHtml(evs, groupId, collapsed) {
    if (!evs.length) return '';
    // 短 evidence（≤20 字且通过）连续段同行并列；其余每行一条（保留三件套）
    const rows = [];
    let shortRun = [];
    const flushShort = () => {
      if (shortRun.length > 1) {
        rows.push(`<div class="trace-ev-inline">${shortRun.map((n) =>
          `<span title="${_esc(n.detail)}">✓ ${n.label_human}</span>`).join(' · ')}</div>`);
      } else if (shortRun.length === 1) {
        rows.push(traceNodeHtml(shortRun[0]));
      }
      shortRun = [];
    };
    for (const n of evs) {
      if (n.outcome === 'pass' && (n.label_human || '').length <= 20) {
        shortRun.push(n);
      } else {
        flushShort();
        rows.push(traceNodeHtml(n));
      }
    }
    flushShort();
    return `<div class="trace-ev-group" id="${groupId}" ${collapsed ? 'style="display:none"' : ''}>${rows.join('')}</div>`;
  }

  function _anchorCls(n, kind) {
    // 红只留真拦截（veto/halt）；advisory = 琥珀提示（SPEC-135.3）
    if (n.outcome === 'veto' || n.outcome === 'halt') return 'blocked';
    if (n.outcome === 'advisory') return 'advisory';
    return kind === 'final' ? 'final' : 'ok';
  }

  function traceAnchorHtml(anchor, idx, collapsed, idPrefix) {
    const n = anchor.node;
    const kind = traceKindOf(n);
    const icon = TRACE_ANCHOR_ICONS[n.outcome] || '●';
    const cls = _anchorCls(n, kind);
    const groupId = `${idPrefix || 'trace-ev'}-${idx}`;
    const hasEv = anchor.pre.length > 0;
    const evHtml = traceEvidenceGroupHtml(anchor.pre, groupId, collapsed);
    const postHtml = anchor.post && anchor.post.length
      ? `<div class="trace-ev-group trace-postnote"><div class="trace-postnote-label">附注</div>${anchor.post.map(traceNodeHtml).join('')}</div>`
      : '';
    // 主行零溯源（SPEC-135.4）：code_ref 收进 title tooltip
    const tip = _esc((n.detail ? n.detail + ' — ' : '')
      + (hasEv ? '点击折叠/展开支撑检查 — ' : '')
      + '溯源: ' + (n.code_ref || '—'));
    return `
      <div class="trace-anchor-block">
        <div class="trace-anchor ${kind === 'final' ? 'is-final' : ''} a-${cls}"
             ${hasEv ? `onclick="const g=document.getElementById('${groupId}'); if(g) g.style.display = g.style.display==='none' ? '' : 'none';"` : ''} title="${tip}">
          <span class="a-icon">${icon}</span>
          <span class="a-label">${n.label_human || n.check}</span>
        </div>
        ${evHtml}${postHtml}
      </div>`;
  }

  // 锚点抽取（verdict/final；历史行无 kind → 无锚点）
  function traceAnchorsOf(nodes) {
    return (nodes || []).filter((n) => {
      const k = traceKindOf(n);
      return k === 'verdict' || k === 'final';
    });
  }

  // 锚点摘要（首页 SPX 卡理由区——首页唯一锚点渲染点，SPEC-135.4 §1）：
  // 只渲染锚点行；hover title = detail + 溯源（完整长文本含 pm-clear 命令
  // 与 code_ref 全部由此承载，主行纯人话零溯源 token）
  function traceAnchorSummaryHtml(nodes) {
    const anchors = traceAnchorsOf(nodes);
    if (!anchors.length) return '';
    return anchors.map((n) => {
      const kind = traceKindOf(n);
      const cls = _anchorCls(n, kind);
      const icon = TRACE_ANCHOR_ICONS[n.outcome] || '●';
      const tip = _esc((n.detail || '') + ' — 溯源: ' + (n.code_ref || '—'));
      return `<div class="trace-anchor trace-anchor-compact ${kind === 'final' ? 'is-final' : ''} a-${cls}"
                   title="${tip}">
        <span class="a-icon">${icon}</span>
        <span class="a-label">${n.label_human || n.check}</span>
      </div>`;
    }).join('');
  }

  function traceLaneAHtml(d, idPrefix) {
    const nodes = d.lane_a || [];
    if (!nodes.length) {
      return `<div class="trace-ghost">${d.lane_a_note || d.lane_a_error || '无 trace 数据'}</div>`;
    }
    // ① 市场读数 stage：单行汇总（spec 钦定渲染特例），不折叠
    const market = nodes.filter((n) => (n.stage || '') === 'market_read');
    const rest = nodes.filter((n) => (n.stage || '') !== 'market_read');
    let html = '';
    if (market.length) {
      html += `<div class="trace-market">${market.map((n) =>
        `<span title="${_esc(n.detail)}">${n.label_human}</span>`).join('<span class="m-sep"> · </span>')}</div>`;
    }
    // ② 锚点分组：evidence 归其后最近的 verdict/final；final 后残余 = 附注
    const anchors = [];
    let pending = [];
    for (const n of rest) {
      if (traceKindOf(n) === 'evidence') { pending.push(n); continue; }
      anchors.push({ node: n, pre: pending, post: [] });
      pending = [];
    }
    if (pending.length) {
      if (anchors.length) anchors[anchors.length - 1].post = pending;
      else return html + pending.map(traceNodeHtml).join('')   // 历史行降级：全 evidence 平铺
        + (d.lane_a_note ? `<div class="trace-ghost">${d.lane_a_note}</div>` : '');
    }
    const collapsedDefault = window.innerWidth < 720;   // 移动端默认折叠
    html += anchors.map((a, i) => traceAnchorHtml(a, i, collapsedDefault, idPrefix)).join('');
    const truncated = nodes.some((n) => n.outcome === 'veto' || n.outcome === 'halt');
    if (truncated) {
      html += `<div class="trace-ghost">…后续未走到的门不再评估（被上方 ⛔ 截断）——ghost 分支</div>`;
    }
    if (d.lane_a_note) html += `<div class="trace-ghost">${d.lane_a_note}</div>`;
    return html;
  }

  // ── SPEC-135.5 — Lane D「Sleeve 决策引擎泳道」──────────────────────────────
  // 语义：这些引擎真实决策（区别于 Lane C 只描述）。行文案/badge 词全部由
  // /api/decision-trace lane_d 后端自吐（label_human/summary/badge），前端
  // 零引擎清单、零 copy 硬编码——此处只做 badge 词 → 样式类映射（词表 =
  // DESIGN.md Action State + Signal-outcome states）。
  const TRACE_BADGE_CLS = { 'SIGNAL': 'tb-signal', 'ARMED': 'tb-armed',
    'WATCHING': 'tb-watching', 'WARNING': 'tb-warning', 'HOLD': 'tb-hold',
    'NO ENTRY': 'tb-noentry', 'CALM': 'tb-calm', 'BLOCKED': 'tb-blocked' };

  function traceLaneDNodeHtml(n) {
    const icon = TRACE_ICONS[n.outcome] || '·';
    const badge = n.badge && n.badge.word
      ? `<span class="t-badge ${TRACE_BADGE_CLS[n.badge.word] || 'tb-noentry'}">${n.badge.label || n.badge.word}</span>`
      : '';
    const inputsStr = n.inputs && Object.keys(n.inputs).length
      ? JSON.stringify(n.inputs) : '—';
    // 联动线等归属行（kind=evidence）缩进挂在引擎行下，常显不折叠
    const linkCls = traceKindOf(n) === 'evidence' ? ' trace-laned-link' : '';
    return `
      <details class="trace-node t-${n.outcome}${linkCls}">
        <summary title="点击展开：检查数据 · 实际值 vs 阈值 · 代码溯源${n.code_ref ? _esc('（' + n.code_ref + '）') : ''}">
          <span class="t-icon" style="color:${_iconColor(n)}">${icon}</span>
          ${badge}
          <span>${n.label_human || n.check}</span>
        </summary>
        <div class="trace-triple">
          <div><strong>检查数据:</strong> <code>${inputsStr}</code></div>
          <div><strong>实际值 vs 阈值:</strong> ${n.detail || '—'}</div>
          <div><strong>代码溯源:</strong> <code>${n.code_ref || '—'}</code></div>
        </div>
      </details>`;
  }

  function traceLaneDHtml(laneD) {
    if (!laneD || !(laneD.engines || []).length) {
      return `<div class="trace-ghost">${(laneD && laneD.note) || 'Lane D 数据不可用'}</div>`;
    }
    let html = laneD.engines.map(traceLaneDNodeHtml).join('');
    if (laneD.note) html += `<div class="trace-ghost">${laneD.note}</div>`;
    return html;
  }

  // 折叠态一行摘要（整卡 <summary> 内常显——首页 SPX 卡下方/spx 同一行，
  // 同 copy 源 = 同一 lane_d.summary_line 字段；hover = 联动线全文）
  function traceLaneDSummaryHtml(laneD) {
    if (!laneD || !laneD.summary_line) return '';
    const link = (laneD.engines || []).find((n) => traceKindOf(n) === 'evidence');
    const tip = _esc((link && link.label_human ? link.label_human + ' — ' : '')
      + '点开看 Lane D 全行');
    return `<span class="trace-sleeve-summary" title="${tip}"><span class="tss-label">决策引擎状态</span>${laneD.summary_line}</span>`;
  }

  function traceLaneBHtml(items) {
    if (!items || !items.length) return '<div class="trace-ghost">今天没有 open 仓位。</div>';
    return items.map((it) => {
      const icon = it.state === 'action' ? '⛔' : it.state === 'hold' ? '✓' : '·';
      const color = it.state === 'action' ? 'var(--orange)' : it.state === 'hold' ? 'var(--green)' : 'var(--text-2)';
      return `<div class="trace-node t-${it.state === 'action' ? 'halt' : 'pass'}">
        <summary style="cursor:default" title="${_esc('溯源: ' + (it.code_ref || '—'))}">
          <span class="t-icon" style="color:${color}">${icon}</span>
          <span>${it.trade_id ? `<span style="font-family:var(--f-mono);font-size:0.66rem;color:var(--text-2)">${it.trade_id}</span> · ` : ''}${it.label_human}</span>
        </summary>
      </div>`;
    }).join('');
  }

  // SPEC-135.4 §1 修正：整卡渲染器提升为共享单一源（原先只在 spx.html，
  // 首页另做一套锚点摘要 → 两处并存即信息漂移风险）。现在 /spx 与
  // Portfolio Command Center 渲染同一 <details class="trace-card"> 全图。
  function traceCardHtml(d) {
    const fin = d.final || {};
    // 词表合规：WAIT/观望 不在 Action State 词表 → NO ENTRY
    const verdict = fin.strategy_key === 'reduce_wait'
      ? 'NO ENTRY（不开新仓）'
      : (fin.strategy ? `开仓候选 — ${fin.strategy}` : '（无当日结论存档）');
    const dateOptions = (d.dates_available || []).slice().reverse().map((dt) =>
      `<option value="${dt}" ${dt === d.date ? 'selected' : ''}>${dt}</option>`).join('');
    const laneC = d.lane_c || {};
    return `
      <details class="trace-card" ${d.is_today ? '' : 'open'}>
        <summary>
          <span>Decision Trace</span>
          <span class="trace-verdict">${verdict}</span>
          <span style="margin-left:auto;font-weight:400;letter-spacing:0;text-transform:none">为什么是这个结论 → 点开看全程</span>
          ${traceLaneDSummaryHtml(d.lane_d)}
        </summary>
        <div class="trace-body">
          ${traceLegendHtml()}
          <div class="trace-date-row">
            <select id="trace-date-pick" onchange="loadDecisionTrace(this.value)">${dateOptions}</select>
            <span style="font-size:0.66rem;color:var(--text-2)">最近 30 个有记录的交易日可切换</span>
          </div>
          <div class="trace-lane">
            <div class="trace-lane-title">Lane A · 今天开不开新仓？</div>
            ${traceLaneAHtml(d, 'trace-ev')}
          </div>
          <div class="trace-lane">
            <div class="trace-lane-title">Lane B · 手上的仓位要动吗？</div>
            ${traceLaneBHtml(d.lane_b)}
          </div>
          <div class="trace-lane">
            <div class="trace-lane-title">Lane C · 地形参考（只描述，不决策）</div>
            <div style="font-size:0.76rem;color:var(--text);line-height:1.6">${laneC.narrative || '—'}</div>
            <div class="trace-disclaimer">${laneC.disclaimer || ''}</div>
          </div>
          <div class="trace-lane">
            <div class="trace-lane-title">Lane D · 决策引擎状态（真实决策——区别于 Lane C 只描述）</div>
            ${traceLaneDHtml(d.lane_d)}
          </div>
        </div>
      </details>`;
  }

  // 挂载/刷新整卡到某容器；保留展开态。onchange 日期切换走 window.loadDecisionTrace。
  let _traceLastContainer = 'decision-trace';
  async function traceLoadCard(containerId, dateStr) {
    const id = containerId || _traceLastContainer;
    _traceLastContainer = id;
    const wrap = document.getElementById(id);
    if (!wrap) return;
    try {
      const url = dateStr ? `/api/decision-trace?date=${encodeURIComponent(dateStr)}` : '/api/decision-trace';
      const res = await fetch(url);
      const data = await res.json();
      const wasOpen = wrap.querySelector('.trace-card') && wrap.querySelector('.trace-card').open;
      wrap.innerHTML = traceCardHtml(data);
      if (wasOpen || dateStr) { const c = wrap.querySelector('.trace-card'); if (c) c.open = true; }
    } catch (_) {
      wrap.innerHTML = '';
    }
  }

  // 日期下拉 onchange 全局入口（两页 baked-in 同名，复用最近挂载的容器）
  window.loadDecisionTrace = function (dateStr) { return traceLoadCard(_traceLastContainer, dateStr); };

  window.TraceRender = {
    ICONS: TRACE_ICONS,
    ANCHOR_ICONS: TRACE_ANCHOR_ICONS,
    kindOf: traceKindOf,
    legendHtml: traceLegendHtml,
    nodeHtml: traceNodeHtml,
    evidenceGroupHtml: traceEvidenceGroupHtml,
    anchorHtml: traceAnchorHtml,
    anchorsOf: traceAnchorsOf,
    anchorSummaryHtml: traceAnchorSummaryHtml,
    laneAHtml: traceLaneAHtml,
    laneBHtml: traceLaneBHtml,
    laneDHtml: traceLaneDHtml,
    laneDSummaryHtml: traceLaneDSummaryHtml,
    cardHtml: traceCardHtml,
    loadCard: traceLoadCard,
  };
})();

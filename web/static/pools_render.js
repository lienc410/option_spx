// 2026-07-13 — Resource Pools 共享渲染器（State Map Layer 3 与 Portfolio
// Command Center 的 Resource Waterline 面板共用；TraceRender 同模式）。
// 单一 payload 源：/api/state-surface 的 pools 块（cash/bp/crash）。
// 单一渲染源：任何池数字/门线/状态句在两页逐字节一致——此前首页与 State Map
// 各写一版渲染 + 各读一个端点，标准仓一边 $22k 一边 $40k（活漂移实例）。
// 语言规则（DESIGN.md）：块名/键名英文，注释与状态句中文；溯源只进 tooltip。
// 样式类（pool-block/bar-*/pool-row/pool-status）在 theme.css，禁止内联重定义。
(function () {
  'use strict';

  const NA = '<span class="na">n/a</span>';

  const fmtUsd = (v) => v == null ? '—'
    : '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
  const fmtPct = (v, d) => v == null ? '—'
    : Number(v).toFixed(d != null ? d : 1) + '%';
  const kUsd = (v) => v == null ? '—' : `$${Math.round(v / 1000)}k`;
  const esc = (s) => String(s == null ? '' : s).replace(/"/g, '&quot;');

  // ── regime 词表（唯一副本：首页 Regime Banner 与 BP Pool Cap regime 行共用；
  //    此前首页写 'SECOND LEG / R6'、State Map 写 'second-leg 阻断' 各一套）──
  const REGIME_VOCAB = {
    normal: {
      en: 'NORMAL', short: 'normal',
      note: '常规 cap 生效',
      color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-border)',
    },
    booster_shadow: {
      en: 'BOOSTER · SHADOW', short: 'booster 观察中',
      note: 'booster 观察中（不改 cap）',
      color: 'var(--blue)', bg: 'var(--blue-bg)', border: 'var(--blue-border)',
    },
    booster_active: {
      en: 'BOOSTER', short: 'booster 生效',
      note: 'booster 生效（cap 提升）',
      color: 'var(--blue)', bg: 'var(--blue-bg)', border: 'var(--blue-border)',
    },
    stress: {
      en: 'STRESS EPISODE', short: 'stress 收紧',
      note: 'SPX PM cap 收紧 · Stress Put Ladder 可入场',
      color: 'var(--orange)', bg: 'var(--orange-bg)', border: 'var(--orange-border)',
    },
    second_leg: {
      en: 'SECOND-LEG / R6', short: 'second-leg 阻断',
      note: '全部 short-vol 入场阻断（R6）— 仅 DD Overlay 独立运行',
      color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red-border)',
    },
  };
  const regimeOf = (token) => REGIME_VOCAB[token] || {
    en: String(token || 'n/a'), short: String(token || 'n/a'), note: '',
    color: 'var(--text-2)', bg: 'var(--gray-bg)', border: 'var(--gray-border)',
  };

  // 刻度线标签防碰撞：标签在条外侧 tick 轨道，按位置锚点换向，单条单标签零重叠
  function tickHtml(posPct, label, anchor) {
    if (posPct == null || isNaN(posPct)) return { tick: '', label: '' };
    let style;
    if (anchor === 'right')      style = `left:${posPct}%;transform:translateX(-100%)`;
    else if (anchor === 'left')  style = `left:${posPct}%`;
    else if (posPct > 78)        style = `left:${posPct}%;transform:translateX(-100%)`;
    else if (posPct < 8)         style = `left:${posPct}%`;
    else                         style = `left:${posPct}%;transform:translateX(-50%)`;
    return {
      tick: `<span class="bar-tick" style="left:${posPct}%"></span>`,
      label: `<span class="bar-tick-label" style="${style}">${label}</span>`,
    };
  }

  function barBlockHtml(name, nameTip, valText, ticksLabels, trackInner, scaleL, scaleR) {
    return `<div class="bar-block">
      <div class="bar-hd"><span class="bar-name"${nameTip ? ` title="${esc(nameTip)}"` : ''}>${name}</span><span class="bar-val">${valText}</span></div>
      <div class="bar-ticks">${ticksLabels}</div>
      <div class="bar-track">${trackInner}</div>
      <div class="bar-scale"><span>${scaleL}</span><span>${scaleR}</span></div>
    </div>`;
  }

  // ── 答案先行状态句（原首页 Resource Waterline 逻辑，PM 2026-07-07 裁定
  //    「状态句回答还能不能开、能开多大、为什么」；SPEC-138 F4：缺轨=数据
  //    中断不是治理裁决，advisory 语气不出硬 verdict）──────────────────────
  function cashStatusHtml(c) {
    const railGap = c.rail_complete === false;
    let cls, line;
    if (railGap) {
      cls = 'ps-orange';
      line = `<span class="ps-word">数据降级</span> — 现金轨不齐（${c.degraded_error || '某账户数据缺失'}），池只统计在轨账户，预算/底线判定暂挂，数据恢复后自动复算`;
    } else if (c.floor_distance_usd != null && c.floor_distance_usd < 0) {
      cls = 'ps-red';
      line = `<span class="ps-word">锁定</span> — 现金已低于底线（${fmtUsd(c.floor_usd)}），所有吃现金的策略（BCD/T2）暂停，补现金后自动解锁`;
    } else if (c.fits_standard_debit === false) {
      cls = 'ps-orange';
      line = `<span class="ps-word">已满</span> — 预算内只剩 ${fmtUsd(c.cap_headroom_usd)}，装不下一笔标准仓（${fmtUsd(c.bcd_standard_usd)}），下一笔 BCD/T2 会被挡`;
    } else if (c.cap_headroom_usd != null && c.bcd_standard_usd) {
      const n = Math.floor(c.cap_headroom_usd / c.bcd_standard_usd);
      cls = 'ps-green';
      line = `<span class="ps-word">可开新仓</span> — 预算内还能放 ${fmtUsd(c.cap_headroom_usd)}（约 ${n} 笔标准仓）`;
    } else {
      return '';
    }
    return `<div class="pool-status ${cls}">${line}</div>`;
  }

  // ── Cash Pool 块（双 bar：池水位 vs 已花 debit，量纲分离——PM 2026-07-13
  //    重画版式）。opts.note=false 隐藏读法脚注（首页紧凑用）。────────────
  function cashBlockHtml(c, opts) {
    opts = opts || {};
    if (!c || c.status !== 'ok') {
      return `<div class="pool-hd"><span class="pool-name">Cash Pool</span><span class="pool-total">${NA}</span></div>
        <div class="pool-rows"><div class="pool-row"><span class="pr-key">Status</span><span class="pr-val na">n/a — ${esc((c && c.error) || 'unavailable')}</span></div></div>`;
    }
    let html = `<div class="pool-hd"><span class="pool-name">Cash Pool</span><span class="pool-total">liquid ${fmtUsd(c.liquid)}</span></div>`;
    html += cashStatusHtml(c);

    // Bar 1 · Pool level：fill = liquid；floor/waterline 是池总量的门线
    const lv = c.level_gauge;
    if (lv && lv.scale_max != null) {
      let ticks = '', labels = '';
      if (lv.floor_pos_pct != null) {
        const t = tickHtml(lv.floor_pos_pct, `floor ${kUsd(c.floor_usd)}`);
        ticks += t.tick; labels += t.label;
      }
      if (lv.waterline_pos_pct != null) {
        const t = tickHtml(lv.waterline_pos_pct, `waterline ${kUsd(c.waterline_self_usd)}`);
        ticks += t.tick; labels += t.label;
      }
      html += barBlockHtml('Pool level（池总量 vs 门线）', null, fmtUsd(c.liquid),
        labels,
        `<div class="bar-fill fill-level" style="width:${lv.fill_pct ?? 0}%"></div>` + ticks,
        '$0', fmtUsd(lv.scale_max));
    }

    // Bar 2 · Committed debit：fill = 已花 debit；上限线 = cap + DD ammo
    const g = c.committed || {};
    {
      let ticks = '', labels = '';
      if (c.cap_pct != null) {
        const t = tickHtml(c.cap_pct, `cap ${fmtPct(c.cap_pct, 0)}`, 'right');
        ticks += t.tick; labels += t.label;
      }
      if (c.ammo_line_pos_pct != null) {
        const t = tickHtml(c.ammo_line_pos_pct, `DD ammo ${kUsd(c.ammo_line_usd)}`, 'left');
        ticks += t.tick; labels += t.label;
      }
      html += barBlockHtml('Committed debit（已花额度 vs 上限）', null,
        `${fmtUsd(g.value)} (${fmtPct(c.utilization_pct)})`,
        labels,
        `<div class="bar-fill fill-cash" style="width:${g.width_pct ?? 0}%"></div>` + ticks,
        '$0', fmtUsd(c.liquid));
    }

    // 行区：不重复条已表达的数字；键统一英文（语言规则）
    const rows = [];
    if (c.waterline_state) {
      const wlTip = [
        `现金水位规则（只读，不拦单）`,
        `池 ≥ ${fmtUsd(c.waterline_self_usd)}：主 debit × DD Overlay × 现金预算三方自洽`,
        `池 < ${fmtUsd(c.waterline_sell_usd)}：DD Overlay 触发日预期需卖 QQQ/SGOV 腾现金、或主动跳过该次`,
        `助记：1 笔标准 BCD ${kUsd(c.bcd_standard_usd)} + 1 发 DD 触发 ${kUsd(c.reserve_need)} + floor ${kUsd(c.floor_usd)} ≈ ${kUsd(c.waterline_self_usd)}`,
        `（助记非推导，正式依据 = Q093 19y 重放；组件大幅变动时按该方法重校准）— 溯源 Q093 P1 R-b`,
      ].join('\n');
      const margin = c.liquid - c.waterline_self_usd;
      const wl = c.waterline_state === 'ok'
        ? `<span class="pr-val pr-ok">✓ 高于 waterline ${fmtUsd(margin)} · 三方自洽</span>`
        : c.waterline_state === 'below_self'
          ? `<span class="pr-val pr-warn">⚠ 低于 waterline ${fmtUsd(-margin)} — DD 触发日或需卖资产/跳过</span>`
          : `<span class="pr-val pr-bad">⚠ 池 < ${fmtUsd(c.waterline_sell_usd)} — DD 触发日须卖资产或跳过</span>`;
      rows.push(`<div class="pool-row" title="${esc(wlTip)}"><span class="pr-key">Waterline</span>${wl}</div>`);
    }
    if (c.reserve_need != null) {
      const cls = c.ready ? 'pr-ok' : 'pr-bad';
      rows.push(`<div class="pool-row" title="DD Overlay 触发预留（production cap × NLV 现算）：liquid − 在场 debit ≥ 该值为 ready"><span class="pr-key">DD Overlay reserve</span><span class="pr-val ${cls}">${fmtUsd(c.reserve_need)} · ${c.ready ? 'ready' : 'short'}</span></div>`);
      rows.push(`<div class="pool-row"><span class="pr-key">Concurrent BCD headroom</span><span class="pr-val">${c.bcd_headroom_count} × ${fmtUsd(c.bcd_standard_usd)}</span></div>`);
    }
    html += `<div class="pool-rows">${rows.join('')}</div>`;

    if (opts.note !== false) {
      html += `<div class="pool-note">读法：上条 = 池水位（蓝）对 floor / waterline 两条门线；下条 = 已花 debit（金）对 cap / DD ammo 两条上限。<br>debit 越过 DD ammo 线 = 吃掉 DD Overlay 的抄底子弹 → 平静日补弹药，不在崩盘日卖资产。<br>waterline ≈ 1 笔标准 BCD + 1 发 DD 触发 + floor（助记，hover Waterline 行看当前数值）。</div>`;
    }
    return html;
  }

  // ── BP Pool 块（绝对 0-100% 刻度；cap 金色刻度线；分策略 lanes 行）──────
  function bpBlockHtml(bp, opts) {
    opts = opts || {};
    if (!bp || bp.nlv_basis == null) {
      return `<div class="pool-hd"><span class="pool-name">BP Pool</span><span class="pool-total">${NA}</span></div>`;
    }
    const railGap = bp.rail_complete === false;
    const total = `NLV basis ${fmtUsd(bp.nlv_basis)}${railGap ? '（仅 ' + (bp.rails_present || []).join('+') + '）' : '（Schwab+ETrade）'}`;
    let html = `<div class="pool-hd"><span class="pool-name">BP Pool</span><span class="pool-total">${total}</span></div>`;

    const bpBar = (geom, name, nameTip, dollars) => {
      if (!geom || geom.width_pct == null) {
        return barBlockHtml(name, nameTip, NA, '', '', '0%', '100%');
      }
      const dStr = dollars != null ? ` ($${Math.round(dollars / 1000)}k)` : '';
      let ticks = '', labels = '';
      if (geom.cap_pos_pct != null) {
        const t = tickHtml(geom.cap_pos_pct, `cap ${fmtPct(geom.cap, 0)}`);
        ticks = t.tick; labels = t.label;
      }
      return barBlockHtml(name, nameTip,
        `${fmtPct(geom.value)}${dStr} / cap ${geom.cap != null ? fmtPct(geom.cap, 0) : 'n/a'}`,
        labels,
        `<div class="bar-fill fill-bp" style="width:${geom.width_pct}%"></div>` + ticks,
        '0%', '100%');
    };
    html += bpBar(bp.spx_pm, 'Account maint (R1)',
      'R1 = 账户全量维持保证金（含 equity 持仓），非仅 SPX 期权占用 — SPEC-103 §R1',
      bp.spx_pm_dollars);
    html += bpBar(bp.short_vol, 'Short-Vol', null);

    const rows = [];
    if (railGap) {
      rows.push(`<div class="pool-row"><span class="pr-key">Data rail</span><span class="pr-val pr-warn">⚠ ETrade 轨缺失 — basis 仅 Schwab，占用率相对全账户被高估</span></div>`);
    }
    if (bp.es_span) rows.push(`<div class="pool-row" title="独立券商 SPAN 池，不与 Schwab 账户共享 basis；governance 决策降权（demoted）"><span class="pr-key">/ES SPAN · 独立池</span><span class="pr-val">${fmtPct(bp.es_span.value)} / cap ${fmtPct(bp.es_span.cap, 0)}</span></div>`);
    if (bp.combined) rows.push(`<div class="pool-row"><span class="pr-key">Combined (R3)</span><span class="pr-val">${fmtPct(bp.combined.value)}${bp.combined_dollars != null ? ` ($${Math.round(bp.combined_dollars / 1000)}k)` : ''} / cap ${fmtPct(bp.combined.cap, 0)}</span></div>`);

    // 分策略资源行（对齐 Cash Pool 侧的 DD reserve / BCD headroom 模式）
    if (bp.lanes) {
      const L = bp.lanes;
      const roomsStr = Object.entries(L.rooms_pct || {}).map(([k, v]) => `${k} 剩 ${v.toFixed(1)}pp`).join('，');
      const bpsTip = [
        `headroom = 各 cap 剩余空间取最小（${roomsStr}）→ binding ${L.binding_cap}`,
        `标准仓 = bp_target_normal ${L.bp_target_normal_pct}% × NLV basis ≈ ${kUsd(L.bps_std_usd)}（显示估算）`,
        `实际下单以当时 Schwab Option BP 为基数（HIGH_VOL 档 ${L.bp_target_high_vol_pct}%）`,
      ].join('\n');
      const bpsVal = L.short_vol_blocked
        ? `<span class="pr-warn">second-leg 阻断中（R6）</span>`
        : `${L.bps_headroom_n} × ~${kUsd(L.bps_std_usd)}（binding ${L.binding_cap}，剩 ${kUsd(L.room_usd)}）`;
      rows.push(`<div class="pool-row" title="${esc(bpsTip)}"><span class="pr-key">BPS/IC headroom</span><span class="pr-val">${bpsVal}</span></div>`);
      const afTip = [
        `Aftermath = 崩后窗口 IC-HV 首笔，0.5× staging（证据缺口降档）`,
        `需求 = bp_target_high_vol ${L.bp_target_high_vol_pct}% × NLV basis × ${L.staging_factor}`,
        `ready = binding cap 剩余空间 ≥ 需求`,
      ].join('\n');
      const afCls = L.aftermath_ready ? '' : 'pr-warn';
      rows.push(`<div class="pool-row" title="${esc(afTip)}"><span class="pr-key">Aftermath reserve <span class="spec-ref">SPEC-143</span></span><span class="pr-val ${afCls}">~${kUsd(L.aftermath_need_usd)} · ${L.aftermath_ready ? 'ready' : 'short'}</span></div>`);
      if (L.es_ladder && L.es_ladder.bp_per_contract != null) {
        const E = L.es_ladder;
        const esTip = [
          `SPAN/张为 TOS 实测常量（as-of ${E.bp_as_of}，90 天过期线）`,
          `占独立 SPAN 池（上方 /ES SPAN 行），不占 SPX PM`,
          `mode=${E.mode || '—'}：shadow = 纸上跟踪，无实仓指令`,
        ].join('\n');
        rows.push(`<div class="pool-row" title="${esc(esTip)}"><span class="pr-key">HV Ladder (ES)</span><span class="pr-val">${E.mode === 'shadow' ? 'shadow · ' : ''}$${Math.round(E.bp_per_contract).toLocaleString()}/张 SPAN</span></div>`);
      }
    }
    if (bp.cap_regime) {
      // 内部枚举 token 人话化（regime 词表唯一副本，首页 banner 同源）
      const R = regimeOf(bp.cap_regime);
      const capStr = bp.spx_pm && bp.spx_pm.cap != null ? fmtPct(bp.spx_pm.cap, 0) : '—';
      const val = bp.cap_regime === 'booster_shadow'
        ? `${R.short}（不改 cap，实际 ${capStr}）` : R.short;
      rows.push(`<div class="pool-row" title="溯源 active_spx_pm_cap_regime: ${esc(bp.cap_regime)}"><span class="pr-key">Cap regime</span><span class="pr-val">${val}</span></div>`);
    }
    if (bp.asof) {
      // stale 判定对照「最近一个应跑的交易日 09:40 ET」而非墙钟——bot 周末
      // 不跑，30h 墙钟阈值每个周日必误报（2026-07-12 实测抓到）。市场假日
      // 仍可能误报一次，可接受。
      const nowET = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/New_York' }));
      const expected = new Date(nowET);
      expected.setHours(9, 40, 0, 0);
      if (nowET < expected) expected.setDate(expected.getDate() - 1);
      while (expected.getDay() === 0 || expected.getDay() === 6) expected.setDate(expected.getDate() - 1);
      const asofET = new Date(new Date(bp.asof).toLocaleString('en-US', { timeZone: 'America/New_York' }));
      const lagH = (expected - asofET) / 3600000;
      const stale = lagH > 2;   // 容忍 2h（重跑/补写）
      const expStr = `${String(expected.getMonth() + 1).padStart(2, '0')}-${String(expected.getDate()).padStart(2, '0')} 09:40`;
      rows.push(`<div class="pool-row"><span class="pr-key">As of</span><span class="pr-val ${stale ? 'pr-warn' : ''}">${String(bp.asof).slice(0, 16).replace('T', ' ')}${stale ? ` ⚠ 缺 ${expStr} 快照（bot 未更新？）` : ''}</span></div>`);
    }
    html += `<div class="pool-rows">${rows.join('')}</div>`;

    if (opts.note !== false) {
      html += `<div class="pool-note">所有条共用绝对 0-100% 刻度（同值必同长）；cap 为金色刻度线标注在各自绝对位置。<br>Account maint (R1) = 账户全量维持保证金（含 equity），非仅 SPX 期权。<br>/ES SPAN 为独立券商池，governance 决策降权。</div>`;
    }
    return html;
  }

  // ── Crash Budget 块（Q091 最恶情景可部署容量；原首页独有，单源化后两页
  //    共用；PM ratified 2026-07-07）────────────────────────────────────────
  function crashBlockHtml(crash, opts) {
    opts = opts || {};
    if (!crash || crash.status !== 'ok') {
      return `<div class="pool-hd"><span class="pool-name">Crash Budget</span><span class="pool-total">${NA}</span></div>
        <div class="pool-rows"><div class="pool-row"><span class="pr-key">Status</span><span class="pr-val na">n/a — ${esc((crash && crash.error) || 'unavailable')}</span></div></div>`;
    }
    let html = `<div class="pool-hd"><span class="pool-name">Crash Budget</span><span class="pool-total">deployable ${fmtUsd(crash.deployable_usd)}</span></div>`;
    const railGap = crash.rail_complete === false;
    const okBudget = crash.deployable_usd != null && crash.deployable_usd > 0;
    let cls, line;
    if (railGap) {
      cls = 'ps-orange';
      line = `<span class="ps-word">数据降级</span> — 券商轨不齐（${crash.degraded_error || '某账户数据缺失'}），最恶情景只按在轨账户计，数字偏保守`;
    } else if (okBudget) {
      cls = 'ps-green';
      line = `<span class="ps-word">安全</span> — 在 2008 级最恶情景下也不爆仓的前提下，还能承担新增最大亏损 ${fmtUsd(crash.deployable_usd)}`;
    } else {
      cls = 'ps-red';
      line = `<span class="ps-word">超预算</span> — 再加仓会把最恶情景推入爆仓区，先减仓或补现金`;
    }
    html += `<div class="pool-status ${cls}">${line}</div>`;
    const tip = [
      `Q091 最恶已批情景：${crash.scenario || '—'}`,
      `再扣安全垫 ${fmtUsd(crash.buffer_usd)}；数字随账户实时重算`,
      `deployable = 最恶情景下 NLV 超额 − 安全垫`,
    ].join('\n');
    const rows = [
      `<div class="pool-row" title="${esc(tip)}"><span class="pr-key">Options max loss</span><span class="pr-val">${fmtUsd(crash.options_sleeve_max_loss_usd)} 已计入</span></div>`,
      `<div class="pool-row"><span class="pr-key">Worst excess</span><span class="pr-val">${fmtUsd(crash.worst_excess_usd)} − buffer ${fmtUsd(crash.buffer_usd)}</span></div>`,
    ];
    html += `<div class="pool-rows">${rows.join('')}</div>`;
    if (opts.note !== false) {
      html += `<div class="pool-note">defined-risk 新仓的顶层预算：最恶已批情景（hover 行看假设）下账户不爆仓还能承担多少新增最大亏损。<br>与现金预算独立——现金管"付得起"，本预算管"崩得起"。</div>`;
    }
    return html;
  }

  window.PoolsRender = {
    REGIME_VOCAB: REGIME_VOCAB,
    regimeOf: regimeOf,
    tickHtml: tickHtml,
    cashStatusHtml: cashStatusHtml,
    cashBlockHtml: cashBlockHtml,
    bpBlockHtml: bpBlockHtml,
    crashBlockHtml: crashBlockHtml,
  };
})();

(function () {
  function normalizeRegime(regime) {
    return String(regime || '').toUpperCase();
  }

  function liveScaleFactor(regime) {
    const normalized = normalizeRegime(regime);
    if (normalized === 'HIGH_VOL') return 0.1;
    if (normalized === 'LOW_VOL') return 2;
    return 1;
  }

  function isHighVolRegime(regime) {
    return normalizeRegime(regime) === 'HIGH_VOL';
  }

  function formatCurrencyValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '—';
    const sign = numeric >= 0 ? '+' : '-';
    return `${sign}$${Math.abs(numeric).toFixed(2)}`;
  }

  function formatPctValue(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '—';
    return `${numeric.toFixed(1)}%`;
  }

  function formatDualBp(bpResearch, regime) {
    const numeric = Number(bpResearch);
    if (!Number.isFinite(numeric)) return '—';
    const research = formatPctValue(numeric);
    if (!isHighVolRegime(regime)) return research;
    const scaled = formatPctValue(numeric * liveScaleFactor(regime));
    return `${research} + ${scaled} est`;
  }

  function formatDualPnl(pnlResearch, regime) {
    const numeric = Number(pnlResearch);
    if (!Number.isFinite(numeric)) return '—';
    const research = formatCurrencyValue(numeric);
    if (!isHighVolRegime(regime)) return research;
    const scaled = formatCurrencyValue(numeric * liveScaleFactor(regime));
    return `${research} + ${scaled} est`;
  }

  function renderDualMetricHtml(value, regime, kind) {
    const formatter = kind === 'bp' ? formatPctValue : formatCurrencyValue;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '<span>—</span>';
    const research = formatter(numeric);
    if (!isHighVolRegime(regime)) return `<span class="dual-primary">${research}</span>`;
    const scaled = formatter(numeric * liveScaleFactor(regime));
    return `<span class="dual-primary">${research}</span><span class="dual-est">${scaled} est</span>`;
  }

  function isBrokenWingIc(legs) {
    if (!Array.isArray(legs) || !legs.length) return false;
    const buyCall = legs.find(leg => String(leg.action || '').toUpperCase() === 'BUY' && String(leg.option || '').toUpperCase() === 'CALL');
    const buyPut = legs.find(leg => String(leg.action || '').toUpperCase() === 'BUY' && String(leg.option || '').toUpperCase() === 'PUT');
    if (!buyCall || !buyPut) return false;
    const callDelta = Math.abs(Number(buyCall.delta));
    const putDelta = Math.abs(Number(buyPut.delta));
    if (!Number.isFinite(callDelta) || !Number.isFinite(putDelta)) return false;
    return Math.abs(callDelta - putDelta) > 0.02;
  }

  window.liveScaleFactor = liveScaleFactor;
  window.formatDualBp = formatDualBp;
  window.formatDualPnl = formatDualPnl;
  window.isBrokenWingIc = isBrokenWingIc;
  window.SPEC072 = {
    normalizeRegime,
    isHighVolRegime,
    formatCurrencyValue,
    formatPctValue,
    renderDualMetricHtml,
  };
})();

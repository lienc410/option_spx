(function () {
  const KEY = 'spx-theme';

  function getTheme() {
    return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
  }

  function setTheme(theme) {
    const next = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem(KEY, next); } catch (_) {}
    updateButtons(next);
    window.dispatchEvent(new CustomEvent('themechange', { detail: { theme: next } }));
  }

  function updateButtons(theme) {
    document.querySelectorAll('[data-theme-toggle]').forEach((btn) => {
      btn.textContent = theme === 'light' ? '🌙' : '☀️';
      btn.setAttribute('aria-label', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
      btn.setAttribute('title', theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme');
    });
  }

  function installToggle() {
    document.querySelectorAll('.nav-right').forEach((slot) => {
      if (slot.querySelector('[data-theme-toggle]')) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'theme-toggle';
      btn.dataset.themeToggle = 'true';
      btn.addEventListener('click', () => setTheme(getTheme() === 'light' ? 'dark' : 'light'));
      slot.prepend(btn);
    });
    updateButtons(getTheme());
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function themeColor(name) {
    if (!name) return '';
    if (name.startsWith('--')) return cssVar(name);
    return cssVar(`--${name}`);
  }

  function themeRgba(name, alpha) {
    const hex = themeColor(name).trim();
    const match = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!match) return hex;
    const r = parseInt(match[1], 16);
    const g = parseInt(match[2], 16);
    const b = parseInt(match[3], 16);
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function resolveColorString(value) {
    if (typeof value !== 'string' || !value.includes('var(')) return value;
    return value.replace(/var\((--[A-Za-z0-9_-]+)\)/g, (_, name) => cssVar(name) || 'transparent');
  }

  function resolveThemeVars(value, seen = new WeakSet()) {
    if (typeof value === 'string') return resolveColorString(value);
    if (typeof value === 'function') {
      return function (...args) {
        return resolveThemeVars(value.apply(this, args));
      };
    }
    if (!value || typeof value !== 'object') return value;
    if (seen.has(value)) return value;
    seen.add(value);
    if (Array.isArray(value)) return value.map((item) => resolveThemeVars(item, seen));
    const out = {};
    for (const [k, v] of Object.entries(value)) out[k] = resolveThemeVars(v, seen);
    return out;
  }

  window.themeColor = themeColor;
  window.themeRgba = themeRgba;
  window.themeResolveColor = resolveColorString;
  window.themeColors = function () {
    return {
      bg: themeColor('bg'), surface: themeColor('surface'), surfaceHi: themeColor('surface-hi'),
      border: themeColor('border'), border2: themeColor('border-2'), text: themeColor('text'), text2: themeColor('text-2'),
      gold: themeColor('gold'), green: themeColor('green'), red: themeColor('red'), blue: themeColor('blue'), orange: themeColor('orange'), purple: themeColor('purple'),
      goldBg: themeColor('gold-bg'), greenBg: themeColor('green-bg'), redBg: themeColor('red-bg'), blueBg: themeColor('blue-bg'), orangeBg: themeColor('orange-bg'),
    };
  };

  function installChartAdapter() {
    if (!window.Chart || window.Chart.__themeAdapterInstalled) return true;
    const OriginalChart = window.Chart;
    const themedCharts = new Set();

    function clonePreservingFunctions(value, seen = new WeakMap()) {
      if (!value || typeof value !== 'object') return value;
      if (seen.has(value)) return seen.get(value);
      const out = Array.isArray(value) ? [] : {};
      seen.set(value, out);
      for (const [k, v] of Object.entries(value)) out[k] = clonePreservingFunctions(v, seen);
      return out;
    }

    function ThemedChart(item, config) {
      const source = clonePreservingFunctions(config);
      const chart = new OriginalChart(item, resolveThemeVars(clonePreservingFunctions(source)));
      chart.__themeSourceConfig = source;
      themedCharts.add(chart);
      const destroy = chart.destroy.bind(chart);
      chart.destroy = function () {
        themedCharts.delete(chart);
        return destroy();
      };
      return chart;
    }

    Object.setPrototypeOf(ThemedChart, OriginalChart);
    ThemedChart.prototype = OriginalChart.prototype;
    for (const key of Object.getOwnPropertyNames(OriginalChart)) {
      if (!(key in ThemedChart)) {
        try { ThemedChart[key] = OriginalChart[key]; } catch (_) {}
      }
    }
    ThemedChart.__themeAdapterInstalled = true;
    window.Chart = ThemedChart;

    window.addEventListener('themechange', () => {
      themedCharts.forEach((chart) => {
        if (!chart.__themeSourceConfig) return;
        const next = resolveThemeVars(clonePreservingFunctions(chart.__themeSourceConfig));
        chart.data = next.data || chart.data;
        chart.options = next.options || chart.options;
        chart.update('none');
      });
    });
    return true;
  }

  function waitForChart() {
    if (installChartAdapter()) return;
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (installChartAdapter() || tries > 80) clearInterval(timer);
    }, 50);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installToggle);
  } else {
    installToggle();
  }
  waitForChart();
})();

(function () {
  const KEY = 'spx-theme';
  const DEFAULT_THEME = 'dark';
  let theme = DEFAULT_THEME;
  try {
    const stored = localStorage.getItem(KEY);
    theme = stored === 'light' || stored === 'dark' ? stored : DEFAULT_THEME;
  } catch (_) {
    theme = DEFAULT_THEME;
  }
  document.documentElement.dataset.theme = theme;
})();

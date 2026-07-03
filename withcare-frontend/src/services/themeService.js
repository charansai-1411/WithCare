// Dark/light theme, persisted to localStorage. The initial class is applied
// pre-paint by an inline script in index.html; this just keeps React in sync.
const KEY = 'withcare-theme';

export function getTheme() {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}

export function setTheme(theme) {
  const dark = theme === 'dark';
  document.documentElement.classList.toggle('dark', dark);
  try { localStorage.setItem(KEY, theme); } catch (e) {}
  return theme;
}

export function toggleTheme() {
  return setTheme(getTheme() === 'dark' ? 'light' : 'dark');
}

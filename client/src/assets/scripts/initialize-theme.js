(() => {
  const storageKey = 'orion-mail-theme';
  let theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

  try {
    const storedTheme = window.localStorage.getItem(storageKey);
    if (storedTheme === 'light' || storedTheme === 'dark') {
      theme = storedTheme;
    }
  }
  catch {
    theme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  document.documentElement.classList.add(`${theme}-theme`);
})();

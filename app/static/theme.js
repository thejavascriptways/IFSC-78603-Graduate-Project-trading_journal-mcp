(function () {
  const themeSelect = document.querySelector("#theme-select");
  const storageKey = "trading-journal-theme";

  const normalizeTheme = (theme) => (theme === "light" ? "light" : "dark");

  const applyTheme = (theme) => {
    const normalizedTheme = normalizeTheme(theme);
    document.documentElement.dataset.theme = normalizedTheme;
    if (themeSelect) {
      themeSelect.value = normalizedTheme;
    }
  };

  let savedTheme = "dark";
  try {
    savedTheme = localStorage.getItem(storageKey) || "dark";
  } catch (error) {
    savedTheme = "dark";
  }

  applyTheme(savedTheme);

  themeSelect?.addEventListener("change", (event) => {
    const nextTheme = normalizeTheme(event.target.value);
    applyTheme(nextTheme);
    try {
      localStorage.setItem(storageKey, nextTheme);
    } catch (error) {
      // Ignore storage errors; the selector still updates the current page.
    }
  });
})();

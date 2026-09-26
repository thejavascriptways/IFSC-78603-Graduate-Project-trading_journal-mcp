(function () {
  const themeToggle = document.querySelector("#theme-toggle");
  const storageKey = "trading-journal-theme";

  const normalizeTheme = (theme) => (theme === "light" ? "light" : "dark");

  const applyTheme = (theme) => {
    const normalizedTheme = normalizeTheme(theme);
    document.documentElement.dataset.theme = normalizedTheme;
    if (themeToggle) {
      const nextTheme = normalizedTheme === "light" ? "dark" : "light";
      themeToggle.setAttribute("aria-pressed", String(normalizedTheme === "light"));
      themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
      themeToggle.setAttribute("title", `Switch to ${nextTheme} theme`);
    }
  };

  let savedTheme = "dark";
  try {
    savedTheme = localStorage.getItem(storageKey) || "dark";
  } catch (error) {
    savedTheme = "dark";
  }

  applyTheme(savedTheme);

  themeToggle?.addEventListener("click", () => {
    const currentTheme = normalizeTheme(document.documentElement.dataset.theme);
    const nextTheme = currentTheme === "light" ? "dark" : "light";
    applyTheme(nextTheme);
    try {
      localStorage.setItem(storageKey, nextTheme);
    } catch (error) {
      // Ignore storage errors; the selector still updates the current page.
    }
  });
})();

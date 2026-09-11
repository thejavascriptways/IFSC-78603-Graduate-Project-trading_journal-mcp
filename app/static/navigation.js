(function () {
  const menus = Array.from(document.querySelectorAll(".nav-menu"));

  const closeMenu = (menu) => {
    menu.classList.remove("is-open");
    menu.querySelector(".nav-menu-trigger")?.setAttribute("aria-expanded", "false");
  };

  const closeOtherMenus = (activeMenu) => {
    menus.filter((menu) => menu !== activeMenu).forEach(closeMenu);
  };

  menus.forEach((menu) => {
    const trigger = menu.querySelector(".nav-menu-trigger");
    if (!trigger) {
      return;
    }

    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const willOpen = !menu.classList.contains("is-open");
      closeOtherMenus(menu);
      menu.classList.toggle("is-open", willOpen);
      trigger.setAttribute("aria-expanded", String(willOpen));
    });
  });

  document.addEventListener("click", () => {
    menus.forEach(closeMenu);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      menus.forEach(closeMenu);
    }
  });
})();

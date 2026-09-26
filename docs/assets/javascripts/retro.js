document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  root.dataset.chrisosUi = "retro-responsive";
  document.querySelectorAll("table").forEach((table) => {
    if (table.parentElement && !table.parentElement.classList.contains("table-scroll")) {
      const wrap = document.createElement("div");
      wrap.className = "table-scroll";
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    }
  });
});

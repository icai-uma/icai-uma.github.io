const menu = document.querySelector(".menu-toggle");
const nav = document.querySelector("#navigation");
const compact = matchMedia("(max-width: 1000px)");

function setMenu(open) {
  menu.setAttribute("aria-expanded", String(open));
  nav.hidden = compact.matches && !open;
}
function updateViewport() {
  menu.hidden = !compact.matches;
  setMenu(false);
}
compact.addEventListener("change", updateViewport);
menu.addEventListener("click", () => setMenu(menu.getAttribute("aria-expanded") !== "true"));
nav.addEventListener("keydown", event => {
  if (event.key === "Escape" && compact.matches) {
    setMenu(false);
    menu.focus();
  }
});
updateViewport();

const panels = [...document.querySelectorAll("[data-panel]")];
const panelLinks = [...document.querySelectorAll("[data-panel-nav] a")];
if (panels.length) {
  const language = document.querySelector(".language");
  const alternate = language?.getAttribute("href");
  function showPanel() {
    const hash = location.hash.slice(1);
    const target = hash ? document.getElementById(hash) : null;
    const active = target?.closest("[data-panel]") || panels[0];
    for (const panel of panels) panel.hidden = panel !== active;
    for (const link of panelLinks) {
      if (link.hash.slice(1) === active.id) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
    if (alternate) language.href = alternate + (target ? "#" + target.id : "");
    if (target && target !== active) requestAnimationFrame(() => target.scrollIntoView());
  }
  window.addEventListener("hashchange", showPanel);
  for (const link of panelLinks) {
    link.addEventListener("click", event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (location.hash !== link.hash) history.pushState(null, "", link.hash);
      showPanel();
    });
  }
  showPanel();
}

for (const catalog of document.querySelectorAll("[data-catalog]")) {
  const filters = catalog.querySelector(".filters");
  const groups = [...catalog.querySelectorAll("[data-year-group]")];
  const yearLinks = [...catalog.querySelectorAll(".year-index a")];
  const typeButtons = [...filters.querySelectorAll("[data-types] button")];
  const counter = catalog.querySelector("[data-count]");
  const empty = catalog.querySelector("[data-empty]");
  const format = new Intl.NumberFormat(document.documentElement.lang);
  let type = "";

  function applyFilters() {
    const terms = filters.elements.search.value.toLowerCase().normalize("NFKD")
      .replace(/\p{M}/gu, "").match(/[a-z0-9]+/g) || [];
    let matches = 0;
    for (const [index, group] of groups.entries()) {
      let found = false;
      for (const record of group.querySelectorAll("[data-record]")) {
        record.hidden = Boolean(type && type !== record.dataset.type)
          || !terms.every(term => record.dataset.search.includes(term));
        if (!record.hidden) {
          matches += 1;
          found = true;
        }
      }
      group.hidden = !found;
      yearLinks[index].hidden = !found;
    }
    counter.textContent = format.format(matches) + " " + (matches === 1 ? catalog.dataset.singular : catalog.dataset.plural);
    empty.hidden = matches > 0;
  }

  for (const button of typeButtons) {
    button.addEventListener("click", () => {
      type = button.value;
      for (const choice of typeButtons) choice.setAttribute("aria-pressed", String(choice === button));
      applyFilters();
    });
  }
  filters.hidden = false;
  filters.addEventListener("submit", event => event.preventDefault());
  filters.addEventListener("input", applyFilters);
  applyFilters();
}

const newsNav = document.querySelector("[data-news-nav]");
if (newsNav) {
  const choices = [...newsNav.querySelectorAll("button")];
  const items = [...document.querySelectorAll("[data-category]")];
  newsNav.hidden = false;
  for (const choice of choices) {
    choice.addEventListener("click", () => {
      for (const button of choices) button.setAttribute("aria-pressed", String(button === choice));
      for (const item of items) item.hidden = Boolean(choice.value && item.dataset.category !== choice.value);
    });
  }
}

const dialog = document.querySelector("#item-dialog");
if (dialog?.showModal) {
  const title = dialog.querySelector("h2");
  const body = dialog.querySelector("[data-dialog-body]");
  const close = dialog.querySelector("[data-close]");

  function openItem(heading, content) {
    title.textContent = heading;
    body.replaceChildren(content);
    dialog.showModal();
  }

  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => {
    if (event.target === dialog) dialog.close();
  });

  for (const profile of document.querySelectorAll("details.person")) {
    const trigger = profile.querySelector("summary");
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.addEventListener("click", event => {
      event.preventDefault();
      openItem(profile.querySelector(".person-name").textContent, profile.querySelector(".person-details").cloneNode(true));
    });
  }
  for (const citation of document.querySelectorAll("[data-cite]")) {
    citation.hidden = false;
    citation.addEventListener("click", () => {
      openItem(citation.textContent, citation.nextElementSibling.content.cloneNode(true));
    });
  }
}

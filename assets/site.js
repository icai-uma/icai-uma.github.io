const menu = document.querySelector(".menu-toggle");
const nav = document.querySelector("#navigation");
const compact = matchMedia("(max-width: 850px)");

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

const filters = document.querySelector(".filters");
if (filters) {
  const records = [...document.querySelectorAll("#publicaciones [data-record]")];
  const counter = document.querySelector("[data-count]");
  const empty = document.querySelector("[data-empty]");
  const format = new Intl.NumberFormat(document.documentElement.lang);

  function applyFilters() {
    const terms = filters.elements.search.value.toLowerCase().normalize("NFKD")
      .replace(/\p{M}/gu, "").match(/[a-z0-9]+/g) || [];
    const year = filters.elements.year.value;
    const type = filters.elements.type.value;
    let matches = 0;
    for (const record of records) {
      const matchesSearch = terms.every(term => record.dataset.search.includes(term));
      record.hidden = !matchesSearch || Boolean(year && year !== record.dataset.year)
        || Boolean(type && type !== record.dataset.type);
      if (!record.hidden) matches += 1;
    }
    const label = document.documentElement.lang === "en"
      ? (matches === 1 ? "publication" : "publications")
      : (matches === 1 ? "publicación" : "publicaciones");
    counter.textContent = format.format(matches) + " " + label;
    empty.hidden = matches > 0;
  }

  filters.hidden = false;
  filters.addEventListener("submit", event => event.preventDefault());
  filters.addEventListener("input", applyFilters);
  applyFilters();
}

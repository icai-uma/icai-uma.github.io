"""Build a bilingual static site from ICAI's workbook and optional research export."""
import argparse
import json
import os
import shutil
from html import escape as h
from pathlib import Path

from content import DEFAULT_SOURCE, GROUP, PORTAL, download, drive_workbook, merge_export, merge_records, normalized, read_workbook

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = "https://github.com/icai-uma"
PUBLISH_LABELS = {
    "articulo": ("Artículo", "Article"), "congreso": ("Congreso", "Conference paper"),
    "capitulo": ("Capítulo", "Book chapter"), "libro": ("Libro", "Book"), "otro": ("Otros", "Other"),
}
NAV = [
    ("index.html", "Inicio", "Home"),
    ("equipo.html", "Equipo", "People"),
    ("investigacion.html", "Investigación", "Research"),
    ("noticias.html", "Noticias", "News"),
    ("recursos.html", "Recursos", "Resources"),
]


def link(url, label, css=""):
    return f'<a class="{h(css)}" href="{h(url)}">{h(label)}</a>' if url else ""


class Site:
    def __init__(self, data, group, lang, export_date):
        self.data, self.group, self.lang = data, group, lang
        self.en = lang == "en"
        self.asset = "../assets/" if self.en else "assets/"
        self.export_date = export_date

    def t(self, es, en):
        return en if self.en else es

    def field(self, row, key):
        return (row.get(f"{key}En") if self.en else "") or row.get(key, "")

    def setting(self, key):
        return self.group[key].get(self.lang) or self.group[key]["es"]

    def heading(self, eyebrow, title, description=""):
        copy = f'<p class="section-intro">{h(description)}</p>' if description else ""
        return f'<header class="section-heading"><p class="eyebrow">{h(eyebrow)}</p><h2>{h(title)}</h2>{copy}</header>'

    def banner(self, eyebrow, title, description):
        return f'<div class="page-band"><div class="wrap"><p class="eyebrow">{h(eyebrow)}</p><h1>{h(title)}</h1><p>{h(description)}</p></div></div>'

    def section(self, eyebrow, title, inner, ident="", shade=""):
        id_attr = f' id="{h(ident)}"' if ident else ""
        return f'<section{id_attr} class="section {h(shade)}"><div class="wrap">{self.heading(eyebrow, title)}{inner}</div></section>'

    def layout(self, active, title, description, body, alternates=True):
        nav = ""
        for page, es, en in NAV:
            current = ' aria-current="page"' if page == active else ""
            nav += f'<a href="{page}"{current}>{h(self.t(es,en))}</a>'
        alt = f'../{active}' if self.en else f'en/{active}'
        lang_link = (
            f'<a class="language" href="{alt}" hreflang="{self.t("en", "es")}" lang="{self.t("en", "es")}">{self.t("EN", "ES")}</a>'
            if alternates else ""
        )
        skip = self.t("Saltar al contenido", "Skip to content")
        canonical_root = "https://icai-uma.github.io/"
        canonical = f'{canonical_root}{"en/" if self.en else ""}{"" if active == "index.html" else active}'
        institution = self.t("Universidad de Málaga", "University of Málaga")
        email = self.group["email"]["es"]
        return f"""<!doctype html>
<html lang="{self.lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(title)} · ICAI</title>
<meta name="description" content="{h(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{h(title)} · ICAI">
<meta property="og:description" content="{h(description)}">
<meta property="og:image" content="{canonical_root}assets/hero.webp">
<link rel="icon" href="{self.asset}logo-icai.png">
<link rel="stylesheet" href="{self.asset}site.css">
<script defer src="{self.asset}site.js"></script>
</head>
<body>
<a class="skip" href="#contenido">{skip}</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a href="index.html" class="brand" aria-label="ICAI · {institution}"><span class="brand-symbol" aria-hidden="true"></span><span><strong>ICAI</strong><small>{institution}</small></span></a>
    <button class="menu-toggle" type="button" aria-controls="navigation" aria-expanded="false" hidden>{self.t("Menú", "Menu")}</button>
    <nav id="navigation" aria-label="{self.t("Navegación principal", "Main navigation")}">{nav}</nav>
    {lang_link}
  </div>
</header>
<main id="contenido">{body}</main>
<footer id="contacto" class="site-footer"><div class="wrap footer-inner">
  <div><p class="eyebrow">ICAI · TIC-163</p><h2>{h(self.setting("name"))}</h2><p>{h(self.setting("location"))}</p></div>
  <div><p class="eyebrow">{self.t("Contacto", "Contact")}</p>{link(f"mailto:{email}", email)}{link(DEFAULT_SOURCE, self.t("Portal de Investigación UMA","UMA Research Portal"))}{link(REPOSITORIES, "GitHub")}</div>
</div></footer>
</body>
</html>"""

    def publication(self, row):
        ptype = self.t(*PUBLISH_LABELS[row["type"]])
        info = " · ".join(filter(None, (row.get("authors"), row.get("venue"))))
        search = normalized(" ".join((row["title"], info, row.get("doi", ""))))
        props = f'data-record data-search="{h(search)}" data-type="{row["type"]}" data-year="{row["year"]}"'
        urls = link(row.get("url"), self.t("Ver publicación", "Publication"), "text-link")
        urls += link(row.get("code"), self.t("Código", "Code"), "text-link")
        return f'<article class="record" {props}><p class="record-meta">{row["year"]} · {h(ptype)}</p><h3>{h(row["title"])}</h3><p>{h(info)}</p><div class="links">{urls}</div></article>'

    def project(self, row):
        title = self.field(row, "title")
        period = str(row["year"])
        if row.get("endYear") and row["endYear"] != row["year"]:
            period += f'–{row["endYear"]}'
        data = " · ".join(filter(None, (period, row.get("funder"), row.get("reference"))))
        lead = f'<p>{self.t("IP", "PI")} · {h(row["lead"])}</p>' if row.get("lead") else ""
        return f'<article class="record project"><p class="record-meta">{h(data)}</p><h3>{h(title)}</h3><p>{h(self.field(row, "description"))}</p>{lead}{link(row.get("url"), self.t("Ver proyecto", "Project details"), "text-link")}</article>'

    def thesis(self, row):
        supervisors = f'<p>{self.t("Dirección", "Supervisors")} · {h(row["supervisors"])}</p>' if row.get("supervisors") else ""
        return f'<article class="record"><p class="record-meta">{row["year"]} · {h(row["author"])}</p><h3>{h(row["title"])}</h3>{supervisors}{link(row.get("url"), self.t("Ver tesis", "Thesis details"), "text-link")}</article>'

    def news(self, row):
        metadata = " · ".join(filter(None, (row["date"], self.field(row, "type"))))
        return f'<article class="record"><p class="record-meta">{h(metadata)}</p><h3>{h(self.field(row, "title"))}</h3><p>{h(self.field(row, "description"))}</p>{link(row.get("url"), self.t("Leer más", "Read more"), "text-link")}</article>'

    def shelf(self, rows, renderer):
        return f'<div class="records">{"".join(map(renderer, rows))}</div>'

    def selected(self, section, count):
        rows = self.data[section]
        return sorted(rows, key=lambda row: row.get("featured", False), reverse=True)[:count]

    def home(self):
        title = self.setting("name")
        description = self.setting("intro")
        hero = f"""<section class="hero"><div class="wrap hero-wrap">
  <div class="hero-copy"><p class="eyebrow hero-label">{self.t("Grupo de investigación · Universidad de Málaga", "Research group · University of Málaga")}</p>
  <h1>{h(title)}</h1><p class="hero-intro">{h(description)}</p>
  <div class="hero-actions">{link("investigacion.html", self.t("Explorar investigación", "Explore our research"), "button primary")}{link("equipo.html", self.t("Conocer al equipo", "Meet the team"), "button secondary")}</div></div>
  <div class="hero-visual"><img src="{self.asset}hero.webp" alt="" width="1024" height="768"></div>
</div></section>"""
        shortcuts = [
            ("investigacion.html#publicaciones", "Publicaciones", "Publications", "Artículos, congresos y libros", "Articles, conferences and books", "papers"),
            ("investigacion.html#proyectos", "Proyectos", "Projects", "Investigación y transferencia", "Research and knowledge transfer", "projects"),
            ("equipo.html", "Equipo", "People", "Personal investigador", "Our researchers", "people"),
        ]
        cards = "".join(
            f'<a href="{href}" class="shortcut"><span class="symbol {icon}" aria-hidden="true"></span><span><strong>{self.t(es,en)}</strong><small>{self.t(ds,de)}</small></span></a>'
            for href, es, en, ds, de, icon in shortcuts
        )
        body = hero + f'<div class="quick"><nav class="wrap quick-grid" aria-label="{self.t("Explora el grupo", "Explore the group")}">{cards}</nav></div>'
        line_cards = "".join(
            f'<article class="line"><h3>{h(self.field(row,"title"))}</h3><p>{h(self.field(row,"description"))}</p><p class="topics">{h(self.field(row,"topics"))}</p></article>'
            for row in self.data["lines"]
        )
        body += self.section(self.t("Investigación", "Research"), self.t("Líneas de investigación", "Research areas"), f'<div class="line-grid">{line_cards}</div>')
        if self.data["publications"]:
            picked = self.shelf(self.selected("publications", 3), self.publication)
            action = link("investigacion.html#publicaciones", self.t("Todas las publicaciones","All publications"), "button light")
            body += self.section(self.t("Producción científica","Research output"), self.t("Publicaciones destacadas","Selected publications"), picked + action, shade="tinted")
        if self.data["projects"]:
            picked = self.shelf(self.selected("projects", 2), self.project)
            action = link("investigacion.html#proyectos", self.t("Todos los proyectos","All projects"), "button light")
            body += self.section(self.t("Investigación y transferencia","Research and knowledge transfer"), self.t("Proyectos destacados","Selected projects"), picked + action)
        if self.data["news"]:
            body += self.section(self.t("Actualidad", "Updates"), self.t("Últimas noticias", "Latest news"), self.shelf(self.data["news"][:2], self.news), shade="tinted")
        return self.layout("index.html", title, description, body)

    def team(self):
        title = self.t("Equipo", "People")
        description = self.setting("about")
        cards = []
        for member in self.data["team"]:
            name = member["name"]
            initials = "".join(part[0] for part in (name.split()[0], name.split()[-1]))
            image = (
                f'<img class="avatar" src="{h(member["photo"])}" alt="" width="64" height="64" loading="lazy">'
                if member.get("photo") else f'<span class="avatar" aria-hidden="true">{h(initials)}</span>'
            )
            profile = f'{PORTAL}/investigadores/{member["id"]}/detalle' if member.get("id") else ""
            links = link(profile, self.t("Perfil UMA","UMA profile"), "text-link")
            links += link(member.get("url"), self.t("Web personal","Personal site"), "text-link")
            links += link(member.get("orcid"), "ORCID", "text-link")
            role = self.field(member, "role") or self.t("Personal investigador", "Researcher")
            cards.append(f'<article class="person">{image}<div><h3>{h(name)}</h3><p>{h(role)}</p><p>{h(self.field(member, "description"))}</p><div class="links">{links}</div></div></article>')
        body = self.banner("ICAI · TIC-163", title, description)
        body += self.section(self.t("Grupo ICAI","ICAI group"), self.t("Personal investigador","Researchers"), f'<div class="people-grid">{"".join(cards)}</div>')
        return self.layout("equipo.html", title, description, body)

    def research(self):
        title = self.t("Investigación","Research")
        description = self.t("Publicaciones, proyectos y tesis del grupo ICAI.", "Publications, projects and theses from the ICAI group.")
        body = self.banner("ICAI · TIC-163", title, description)
        sections = [("publicaciones","Publicaciones","Publications"),("proyectos","Proyectos","Projects"),("tesis","Tesis","Theses"),("indicadores","Indicadores","Indicators")]
        tabs = "".join(link(f"#{ident}", self.t(es,en)) for ident, es, en in sections)
        body += f'<nav class="research-nav wrap" aria-label="{self.t("Secciones de investigación","Research sections")}">{tabs}</nav>'
        years = sorted({row["year"] for row in self.data["publications"]}, reverse=True)
        year_options = "".join(f'<option>{year}</option>' for year in years)
        type_options = "".join(f'<option value="{key}">{self.t(*labels)}</option>' for key, labels in PUBLISH_LABELS.items())
        controls = f"""<form class="filters" role="search" hidden>
<label>{self.t("Buscar","Search")}<input type="search" name="search" placeholder="{self.t("Título, autor o DOI","Title, author or DOI")}"></label>
<label>{self.t("Año","Year")}<select name="year"><option value="">{self.t("Todos los años","All years")}</option>{year_options}</select></label>
<label>{self.t("Tipo","Type")}<select name="type"><option value="">{self.t("Todos los tipos","All types")}</option>{type_options}</select></label>
</form><p class="results" data-count role="status"></p><p data-empty hidden>{self.t("No hay publicaciones que coincidan con la búsqueda.","No publications match your search.")}</p>"""
        datasets = [
            ("publications", self.publication, "publicaciones"),
            ("projects", self.project, "financiacion"),
            ("theses", self.thesis, "tesis"),
        ]
        for (ident, es, en), (key, renderer, portal_section) in zip(sections, datasets):
            records = self.shelf(self.data[key], renderer)
            section_content = (controls if key == "publications" else "") + records
            section_content += link(f"{GROUP}/{portal_section}", self.t("Ver en el Portal de Investigación UMA","View on the UMA Research Portal"), "button light")
            body += self.section(self.t("Producción científica","Research output"), self.t(es,en), section_content, ident, "tinted" if key == "projects" else "")
        coverage = " · ".join(
            f'{len(self.data[key])} {self.t(es, en)}' for key, es, en in (
                ("publications", "publicaciones", "publications"),
                ("projects", "proyectos", "projects"),
                ("theses", "tesis", "theses"),
            )
        )
        metrics = self.data["metrics"]
        if metrics:
            metric_cards = []
            for row in metrics:
                source = link(row.get("url"), row["source"], "text-link") or h(row["source"])
                metric_cards.append(f'<article class="record"><p class="record-meta">{h(row["date"])}</p><h3>{h(self.field(row,"title"))}</h3><p class="metric-value">{h(row["value"])}</p><p>{source}</p></article>')
            measures = f'<div class="records">{"".join(metric_cards)}</div>'
        else:
            measures = f'<p>{self.t("Los indicadores bibliométricos se consultan en el Portal de Investigación desde la red de la UMA.", "Bibliometric indicators are available on the Research Portal from the UMA network.")}</p>'
        measures = f'<p><strong>{self.t("Registros en esta web", "Records on this site")}</strong> · {coverage}</p>' + measures
        if self.export_date:
            measures += f'<p>{self.t("Exportación institucional", "Institutional export")} · {h(self.export_date)}</p>'
        measures += link("https://biblioguias.uma.es/portaldelainvestigacion/Indicadores", self.t("Guía de indicadores de la UMA","UMA guide to indicators"), "button light")
        body += self.section(self.t("Producción científica","Research output"), self.t("Indicadores","Indicators"), measures, "indicadores", "tinted")
        return self.layout("investigacion.html", title, description, body)

    def updates(self):
        title = self.t("Noticias","News")
        description = self.t("Actualidad científica y divulgación del grupo ICAI.","Research news and outreach from the ICAI group.")
        records = self.shelf(self.data["news"], self.news) if self.data["news"] else f'<p>{self.t("Todavía no hay noticias publicadas.","No news has been published yet.")}</p>'
        body = self.banner("ICAI · TIC-163", title, description)
        body += self.section(self.t("Divulgación","Outreach"), self.t("Novedades","Latest updates"), records)
        return self.layout("noticias.html", title, description, body)

    def resources(self, resources):
        title = self.t("Recursos abiertos","Open resources")
        description = self.t("Código, demostraciones y materiales de investigación del grupo ICAI.", "Code, demos and research materials from the ICAI group.")
        rows = "".join(
            f'<article class="record"><h3>{h(item["title"])}</h3><div class="links">'
            + "".join(link(item.get(key), label, "text-link") for key, label in (
                ("paper",self.t("Publicación","Publication")),
                ("web",self.t("Web del proyecto","Project site")),
                ("code",self.t("Código","Code")),
            )) + "</div></article>"
            for item in resources
        )
        body = self.banner("ICAI · TIC-163", title, description)
        body += self.section("GitHub", self.t("Repositorios de proyectos","Project repositories"), f'<div class="records">{rows}</div>' + link(REPOSITORIES, self.t("Organización de ICAI en GitHub","ICAI organisation on GitHub"), "button light"))
        return self.layout("recursos.html", title, description, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    parser.add_argument("--workbook", type=Path, default=ROOT / "ICAI_DATOS.xlsx")
    parser.add_argument("--export", type=Path, help="Exportación UMA autorizada, normalizada como JSON ICAI v1.")
    args = parser.parse_args()
    schema = json.loads((ROOT / "scripts/workbook_schema.json").read_text(encoding="utf-8"))
    drive_id = os.environ.get("ICAI_DRIVE_FILE_ID", "")
    drive_folder = os.environ.get("ICAI_DRIVE_FOLDER_ID", "")
    drive_token = os.environ.get("ICAI_DRIVE_TOKEN", "")
    workbook = drive_workbook(drive_id, drive_folder, drive_token) if drive_id or drive_folder else args.workbook.read_bytes()
    data, group = read_workbook(workbook, schema)

    export_url = os.environ.get("ICAI_UMA_EXPORT_URL", "")
    export_date = None
    if args.export or export_url:
        export = args.export.read_bytes() if args.export else download(export_url, os.environ.get("ICAI_UMA_EXPORT_TOKEN", ""))
        export_date = merge_export(data, json.loads(export), schema)
    else:
        for section in ("publications", "projects", "theses", "metrics"):
            data[section] = merge_records(section, [], data[section])
    for section, key in (("publications","year"), ("projects","year"), ("theses","year"), ("news","date"), ("metrics","date"), ("team",None)):
        visible = [row for row in data[section] if row.get("visible", True)]
        data[section] = sorted(visible, key=lambda row: row[key], reverse=True) if key else visible
    resources = json.loads((ROOT / "scripts/resources.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        site = Site(data, group, lang, export_date)
        path = args.output / "en" if lang == "en" else args.output
        path.mkdir(parents=True, exist_ok=True)
        pages = (site.home(), site.team(), site.research(), site.updates(), site.resources(resources))
        for (filename, _, _), page in zip(NAV, pages):
            (path / filename).write_text(page, encoding="utf-8")
    (args.output / "repositories.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>ICAI repositories</title>'
        '<meta http-equiv="refresh" content="0; url=en/recursos.html"><a href="en/recursos.html">ICAI repositories</a></html>',
        encoding="utf-8",
    )
    shutil.copytree(ROOT / "assets", args.output / "assets", dirs_exist_ok=True)
    for asset in ROOT.glob("google*.html"):
        shutil.copy2(asset, args.output)
    print(f"Sitio generado: {', '.join(f'{section}={len(rows)}' for section, rows in data.items())}.")


if __name__ == "__main__":
    main()

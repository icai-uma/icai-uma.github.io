"""Build a bilingual static site from ICAI's workbook and optional research export."""
import argparse
import json
import os
import shutil
from datetime import date
from html import escape as h
from itertools import groupby
from pathlib import Path

from content import DEFAULT_SOURCE, GROUP, PORTAL, drive_workbook, merge_portal, normalized, read_workbook
from uma_portal import read_portal

ROOT = Path(__file__).resolve().parents[1]
REPOSITORIES = "https://github.com/icai-uma"
PUBLISH_LABELS = {
    "articulo": ("Artículo", "Article"), "congreso": ("Congreso", "Conference paper"),
    "capitulo": ("Capítulo", "Book chapter"), "libro": ("Libro", "Book"), "otro": ("Otros", "Other"),
    "sin_clasificar": ("Tipo por confirmar", "Type unconfirmed"),
}
NAV = [
    ("index.html", "Inicio", "Home"),
    ("equipo.html", "Equipo", "People"),
    ("investigacion.html", "Investigación", "Research"),
    ("noticias.html", "Noticias", "News"),
    ("grupo.html", "El grupo", "About ICAI"),
    ("recursos.html", "Recursos", "Resources"),
]


def link(url, label, css=""):
    return f'<a class="{h(css)}" href="{h(url)}">{h(label)}</a>' if url else ""


class Site:
    def __init__(self, data, group, lang, portal_status):
        self.data, self.group, self.lang = data, group, lang
        self.en = lang == "en"
        self.asset = "../assets/" if self.en else "assets/"
        self.portal_status = portal_status

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
        id_attr = f' id="{h(ident)}" data-panel' if ident else ""
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
    <a href="index.html" class="brand" aria-label="ICAI · {institution}"><span class="brand-symbol" aria-hidden="true"></span><span><strong>ICAI</strong><small>{h(self.setting("name"))}</small></span></a>
    <button class="menu-toggle" type="button" aria-controls="navigation" aria-expanded="false" hidden>{self.t("Menú", "Menu")}</button>
    <nav id="navigation" aria-label="{self.t("Navegación principal", "Main navigation")}">{nav}</nav>
    {lang_link}
  </div>
</header>
<main id="contenido">{body}</main>
<dialog id="item-dialog" aria-labelledby="item-dialog-title">
  <div class="dialog-inner">
    <button type="button" class="dialog-close" data-close autofocus>{self.t("Cerrar", "Close")}</button>
    <h2 id="item-dialog-title"></h2>
    <div data-dialog-body></div>
  </div>
</dialog>
<footer id="contacto" class="site-footer"><div class="wrap footer-inner">
  <div><p class="eyebrow">{institution}</p><h2>{h(self.setting("name"))}</h2><p>{h(self.setting("location"))}</p></div>
  <div><p class="eyebrow">{self.t("Contacto", "Contact")}</p>{link(f"mailto:{email}", email)}{link(DEFAULT_SOURCE, self.t("Portal de Investigación UMA","UMA Research Portal"))}{link(REPOSITORIES, "GitHub")}</div>
</div></footer>
</body>
</html>"""

    def publication(self, row):
        ptype = self.t(*PUBLISH_LABELS[row["type"]])
        info = " · ".join(filter(None, (row.get("authors"), row.get("venue"))))
        search = normalized(" ".join((row["title"], info, row.get("doi", ""))))
        props = f'data-record data-search="{h(search)}" data-type="{row["type"]}" data-year="{row["year"]}"'
        urls = link(row.get("url"), "DOI" if row.get("doi") and "doi.org/" in row.get("url", "") else self.t("Ficha", "Record"), "inline-link")
        urls += link(row.get("portalUrl") if row.get("portalUrl") != row.get("url") else "", "UMA", "inline-link")
        urls += link(row.get("code"), self.t("Código", "Code"), "inline-link")
        citation = " ".join(part for part in (
            row.get("authors", ""), f'({row["year"]}).', f'{row["title"].rstrip(".")}.', row.get("venue", ""), row.get("url", ""),
        ) if part)
        label = self.t("Cita", "Citation")
        cite = f'<button type="button" class="inline-link" data-cite aria-haspopup="dialog" hidden>{label}</button><template><p>{h(citation)}</p></template>'
        return f'<article class="record publication" {props}><h3>{h(row["title"])}</h3><p>{h(row.get("authors",""))}</p><div class="record-foot"><span>{h(row.get("venue",""))}</span><span class="tag">{h(ptype)}</span>{urls}{cite}</div></article>'

    def project(self, row):
        title = self.field(row, "title")
        period = str(row["year"])
        if row.get("endYear") and row["endYear"] != row["year"]:
            period += f'–{row["endYear"]}'
        reference = row.get("reference", "")
        if reference and normalized(title).startswith(normalized(reference)):
            reference = ""
        data = " · ".join(filter(None, (row.get("funder"), reference)))
        lead = f'<p>{self.t("IP", "PI")} · {h(row["lead"])}</p>' if row.get("lead") else ""
        status = ""
        if row.get("endYear"):
            year = date.today().year
            if row["year"] > year:
                label = self.t("Previsto", "Planned")
            elif row["endYear"] == year:
                label = self.t("Fin previsto este año", "Scheduled to end this year")
            else:
                label = self.t("Finalizado", "Completed") if row["endYear"] < year else self.t("En curso", "In progress")
            status = f'<span class="tag">{label}</span>'
        project_url = row.get("url")
        if not project_url or project_url == f"{GROUP}/financiacion":
            project_url = row.get("portalUrl") or project_url
        return f'<article class="record dated"><div class="record-meta">{h(period)}{status}</div><div><h3>{h(title)}</h3><p>{h(data)}</p><p>{h(self.field(row, "description"))}</p>{lead}{link(project_url, self.t("Ver proyecto", "Project details"), "text-link")}</div></article>'

    def thesis(self, row):
        supervisors = f'<p>{self.t("Dirección", "Supervisors")} · {h(row["supervisors"])}</p>' if row.get("supervisors") else ""
        thesis_url = row.get("url")
        if not thesis_url or thesis_url == f"{GROUP}/tesis":
            thesis_url = row.get("portalUrl") or thesis_url
        return f'<article class="record dated"><p class="record-meta">{row["year"]}</p><div><h3>{h(row["title"])}</h3><p>{h(row["author"])}</p>{supervisors}{link(thesis_url, self.t("Ver tesis", "Thesis details"), "text-link")}</div></article>'

    def news(self, row):
        category = self.field(row, "type")
        return f'<article class="record news-record" data-category="{h(normalized(category))}"><p class="record-meta"><span class="tag">{h(category)}</span> <time datetime="{row["date"]}">{row["date"]}</time></p><h3>{h(self.field(row, "title"))}</h3><p>{h(self.field(row, "description"))}</p>{link(row.get("url"), self.t("Leer más", "Read more"), "text-link")}</article>'

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
  <div class="hero-actions">{link("investigacion.html", self.t("Nuestra investigación", "Our research"), "button primary")}{link("equipo.html", self.t("Conocer al equipo", "Meet the team"), "button secondary")}</div></div>
  <div class="hero-visual"><img src="{self.asset}hero.webp" alt="" width="1024" height="768"></div>
</div></section>"""
        body = hero
        if self.data["news"]:
            latest = self.shelf(self.data["news"][:3], self.news)
            latest += link("noticias.html", self.t("Todas las noticias", "All news"), "text-link")
            body += self.section("", self.t("Novedades", "Latest news"), latest, shade="tinted")
        shortcuts = (
            ("equipo.html", "Nuestro equipo", "Our team", "Personas y perfiles", "People and profiles"),
            ("investigacion.html", "Investigación", "Research", "Líneas, proyectos y publicaciones", "Areas, projects and publications"),
            ("grupo.html", "El grupo", "About ICAI", "Quiénes somos y dónde estamos", "Who we are and where to find us"),
        )
        rows = "".join(
            f'<li>{link(href, self.t(es,en))}<span>{self.t(ds,de)}</span></li>'
            for href, es, en, ds, de in shortcuts
        )
        body += self.section("", self.t("Conoce ICAI", "Explore ICAI"), f'<ul class="directory">{rows}</ul>')
        if self.data["publications"]:
            picked = self.shelf(self.selected("publications", 3), self.publication)
            action = link("investigacion.html#publicaciones", self.t("Todas las publicaciones","All publications"), "button light")
            body += self.section(self.t("Producción científica","Research output"), self.t("Publicaciones destacadas","Selected publications"), picked + action, shade="tinted")
        if self.data["projects"]:
            picked = self.shelf(self.selected("projects", 2), self.project)
            action = link("investigacion.html#proyectos", self.t("Todos los proyectos","All projects"), "button light")
            body += self.section(self.t("Investigación y transferencia","Research and knowledge transfer"), self.t("Proyectos destacados","Selected projects"), picked + action)
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
            bio = h(self.field(member, "description"))
            detail = f'<p>{bio}</p><div class="links">{links}</div>'
            caption = f'{image}<span><span class="person-name">{h(name)}</span><span class="person-role">{h(role)}</span></span>'
            cards.append(f'<details class="person"><summary>{caption}</summary><div class="person-details">{detail}</div></details>' if bio or links else f'<div class="person-title">{caption}</div>')
        body = self.banner("", title, description)
        body += self.section("", self.t("Personal investigador","Researchers"), f'<div class="people-list">{"".join(cards)}</div>')
        return self.layout("equipo.html", title, description, body)

    def line(self, row):
        topics = "".join(f'<li>{h(topic.strip())}</li>' for topic in self.field(row, "topics").split("·") if topic.strip())
        return f'<article class="record"><h3>{h(self.field(row,"title"))}</h3><p>{h(self.field(row,"description"))}</p><ul class="topic-list">{topics}</ul></article>'

    def publication_catalog(self, conference=False):
        code = "congresos" if conference else "publicaciones"
        records = [row for row in self.data["publications"] if (row["type"] == "congreso") == conference]
        years = sorted({row["year"] for row in records}, reverse=True)
        year_links = "".join(link(f"#{code}-{year}", str(year)) for year in years)
        types = [(key, labels) for key, labels in PUBLISH_LABELS.items() if any(row["type"] == key for row in records)]
        type_buttons = "".join(
            f'<button type="button" value="{key}" aria-pressed="false">{self.t(*labels)}</button>'
            for key, labels in types
        ) if len(types) > 1 else ""
        all_types = f'<button type="button" value="" aria-pressed="true">{self.t("Todas", "All types")}</button>' if type_buttons else ""
        controls = f"""<form class="filters" role="search" hidden>
  <div class="filter-chips" data-types>{all_types}{type_buttons}</div>
  <label>{self.t("Buscar","Search")}<input type="search" name="search" placeholder="{self.t("Autor, título, revista o DOI","Author, title, journal or DOI")}"></label>
</form><p class="results" data-count role="status"></p><p data-empty hidden>{self.t("No hay resultados que coincidan con la búsqueda.","No records match your search.")}</p>"""
        year_index = f'<nav class="year-index" aria-label="{self.t("Ir al año", "Jump to year")}">{year_links}</nav>' if year_links else ""
        groups = "".join(
            f'<div class="year-group" data-year-group id="{code}-{year}"><h3>{year}</h3>{self.shelf(group, self.publication)}</div>'
            for year, group in groupby(records, key=lambda row: row["year"])
        )
        return f'<div data-catalog data-singular="{self.t("resultado","result")}" data-plural="{self.t("resultados","results")}">{controls}{year_index}{groups}</div>'

    def research(self):
        title = self.t("Investigación","Research")
        description = self.t("Líneas de investigación y producción científica del grupo ICAI.", "Research areas and scientific output from ICAI.")
        body = self.banner("", title, description)
        sections = [("lineas","Líneas","Areas"),("proyectos","Proyectos","Projects"),("publicaciones","Publicaciones","Publications"),("congresos","Congresos","Conferences"),("tesis","Tesis","Theses"),("indicadores","Indicadores","Indicators")]
        tabs = "".join(link(f"#{ident}", self.t(es,en)) for ident, es, en in sections)
        body += f'<nav class="section-tabs" data-panel-nav aria-label="{self.t("Secciones de investigación","Research sections")}"><div class="wrap">{tabs}</div></nav>'
        body += self.section("", self.t("Líneas de investigación","Research areas"), self.shelf(self.data["lines"], self.line), "lineas")
        datasets = [
            ("proyectos", self.t("Proyectos financiados","Funded projects"), self.shelf(self.data["projects"], self.project), "financiacion"),
            ("publicaciones", self.t("Publicaciones","Publications"), self.publication_catalog(), "publicaciones"),
            ("congresos", self.t("Trabajos en congresos","Conference contributions"), self.publication_catalog(conference=True), "publicaciones"),
            ("tesis", self.t("Tesis doctorales","Doctoral theses"), self.shelf(self.data["theses"], self.thesis), "tesis"),
        ]
        for ident, heading, records, portal_section in datasets:
            records += link(f"{GROUP}/{portal_section}", self.t("Consultar el Portal de Investigación UMA","View the UMA Research Portal"), "text-link")
            body += self.section("", heading, records, ident)
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
        if self.portal_status:
            measures += f'<p>{self.t("Consulta directa al portal", "Direct portal retrieval")} · {h(self.portal_status)}</p>'
        measures += link("https://biblioguias.uma.es/portaldelainvestigacion/Indicadores", self.t("Guía de indicadores de la UMA","UMA guide to indicators"), "text-link")
        body += self.section("", self.t("Indicadores","Indicators"), measures, "indicadores")
        return self.layout("investigacion.html", title, description, body)

    def updates(self):
        title = self.t("Noticias","News")
        description = self.t("Actualidad científica y divulgación del grupo ICAI.","Research news and outreach from the ICAI group.")
        records = self.shelf(self.data["news"], self.news) if self.data["news"] else f'<p>{self.t("Todavía no hay noticias publicadas.","No news has been published yet.")}</p>'
        body = self.banner("", title, description)
        categories = sorted({self.field(row, "type") for row in self.data["news"] if self.field(row, "type")})
        if categories:
            choices = "".join(f'<button type="button" value="{h(normalized(name))}" aria-pressed="false">{h(name)}</button>' for name in categories)
            all_news = self.t("Todas", "All news")
            body += f'<div class="section-tabs" data-news-nav hidden><div class="wrap"><button type="button" value="" aria-pressed="true">{all_news}</button>{choices}</div></div>'
        body += self.section("", self.t("Novedades","Latest updates"), records)
        return self.layout("noticias.html", title, description, body)

    def about(self):
        title = self.t("El grupo", "About ICAI")
        description = self.setting("name")
        body = self.banner("", title, description)
        body += self.section("", self.t("Quiénes somos", "Who we are"), f'<p class="prose">{h(self.setting("about"))}</p>')
        contact = f'<p>{h(self.setting("location"))}</p>' + link(f'mailto:{self.setting("email")}', self.setting("email"))
        contact += '<div>' + link(DEFAULT_SOURCE, self.t("Ficha oficial del grupo", "Official group profile"), "text-link") + '</div>'
        body += self.section("", self.t("Dónde estamos", "Where to find us"), contact, shade="tinted")
        return self.layout("grupo.html", title, description, body)

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
        body = self.banner("", title, description)
        body += self.section("", self.t("Repositorios de proyectos","Project repositories"), f'<div class="records">{rows}</div>' + link(REPOSITORIES, self.t("Organización de ICAI en GitHub","ICAI organisation on GitHub"), "text-link"))
        return self.layout("recursos.html", title, description, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    parser.add_argument("--workbook", type=Path, default=ROOT / "ICAI_DATOS.xlsx")
    portal_options = parser.add_mutually_exclusive_group()
    portal_options.add_argument("--from-uma", action="store_true", help="Consulta las fichas públicas de ICAI en el Portal UMA.")
    portal_options.add_argument("--portal-html", type=Path, help="Procesa páginas HTML guardadas del Portal UMA para una revisión local.")
    args = parser.parse_args()
    schema = json.loads((ROOT / "scripts/workbook_schema.json").read_text(encoding="utf-8"))
    drive_id = os.environ.get("ICAI_DRIVE_FILE_ID", "")
    drive_folder = os.environ.get("ICAI_DRIVE_FOLDER_ID", "")
    drive_token = os.environ.get("ICAI_DRIVE_TOKEN", "")
    workbook = drive_workbook(drive_id, drive_folder, drive_token) if drive_id or drive_folder else args.workbook.read_bytes()
    data, group = read_workbook(workbook, schema)

    use_portal = args.from_uma or os.environ.get("ICAI_UMA_PUBLIC_SYNC") == "true"
    try:
        payload = read_portal(args.portal_html) if use_portal or args.portal_html else {}
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    merge_portal(data, payload, schema)
    portal_status = payload.get("date", "")
    for section, key in (("publications","year"), ("projects","year"), ("theses","year"), ("news","date"), ("metrics","date"), ("team",None)):
        visible = [row for row in data[section] if row.get("visible", True)]
        data[section] = sorted(visible, key=lambda row: row[key], reverse=True) if key else visible
    resources = json.loads((ROOT / "scripts/resources.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        site = Site(data, group, lang, portal_status)
        path = args.output / "en" if lang == "en" else args.output
        path.mkdir(parents=True, exist_ok=True)
        pages = (site.home(), site.team(), site.research(), site.updates(), site.about(), site.resources(resources))
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

"""Read ICAI's public lists from the University of Málaga research portal."""
import json
import re
from datetime import date
from html import unescape
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from lxml.html import HTMLParser, fromstring

from content import GROUP, PORTAL

AGENT = "ICAI-UMA-website/1.0"
MAX_BYTES = 5_000_000
MAX_LIST_SIZE = 1500
SECTIONS = {
    "detalle": "researchers",
    "publicaciones": "publications",
    "financiacion": "projects",
    "tesis": "theses",
}
TYPES = {
    "ARTICLE": "articulo", "REVIEW": "articulo", "BOOK_CHAPTER": "capitulo", "BOOK": "libro",
    "CONFERENCE_PAPER": "congreso", "CONFERENCE_POSTER": "congreso", "OTROS": "otro",
}
METRICS = {
    "publications": ("Publicaciones en el Portal UMA", "Publications on the UMA Portal"),
    "projects": ("Resultados de financiación en el Portal UMA", "Funding results on the UMA Portal"),
    "theses": ("Tesis en el Portal UMA", "Theses on the UMA Portal"),
}


def read_page(url):
    try:
        with urlopen(Request(url, headers={"User-Agent": AGENT, "Accept-Language": "es"}), timeout=25) as response:
            if urlsplit(response.url).netloc != urlsplit(PORTAL).netloc:
                raise ValueError("El Portal UMA redirigió fuera de su dominio.")
            body = response.read(MAX_BYTES + 1)
    except HTTPError:
        raise
    except URLError as error:
        raise ValueError(f"No se pudo consultar el Portal UMA: {error.reason}") from None
    if len(body) > MAX_BYTES:
        raise ValueError("El Portal UMA devolvió una página mayor que el límite de lectura.")
    return body


def portal_error(error, section):
    if error.code in {403, 429, 503}:
        return ValueError(f"El Portal UMA limitó la consulta de {section} (HTTP {error.code}). Se detuvo la descarga.")
    return ValueError(f"El Portal UMA devolvió HTTP {error.code} en {section}.")


def get_robots():
    robots = RobotFileParser(f"{PORTAL}/robots.txt")
    try:
        text = read_page(robots.url).decode("utf-8", errors="replace")
    except HTTPError as error:
        if error.code not in {404, 410}:
            raise portal_error(error, "robots.txt") from None
        text = ""
    robots.parse(text.splitlines())
    return robots


def normalize_text(value):
    return " ".join(value.split())


def words(node):
    return normalize_text(unescape(node.text_content()))


def class_nodes(node, name):
    return node.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), $name)]', name=f" {name} ")


def class_text(node, *names):
    for name in names:
        values = class_nodes(node, name)
        if values:
            return words(values[0])
    return ""


def portal_link(raw, paths):
    url = urljoin(PORTAL, raw)
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc == urlsplit(PORTAL).netloc and re.fullmatch(paths, parts.path):
        return f"{PORTAL}{parts.path}"
    return ""


def profile_rows(main):
    profiles = {}
    for anchor in main.xpath('.//a[contains(@href, "/investigadores/")]'):
        first = class_text(anchor, "c-persona-card__nombre")
        last = class_text(anchor, "c-persona-card__apellidos")
        url = portal_link(anchor.get("href"), r"/investigadores/[0-9]+/detalle")
        if first and last and url:
            identifier = url.split("/")[-2]
            profiles[identifier] = {"name": f"{first} {last}", "id": identifier}
    return list(profiles.values())


def year_rows(main):
    # The visible lists group records under a four-digit heading.
    row_year = None
    for node in main.xpath(".//h2 | .//h3 | .//h4 | .//li"):
        if node.tag != "li" and re.fullmatch(r"(?:19|20)\d{2}", words(node)):
            row_year = int(words(node))
        if node.tag == "li" and row_year:
            yield row_year, node


def first_record_link(node, paths):
    for anchor in node.xpath(".//a[@href]"):
        url = portal_link(anchor.get("href"), paths)
        if url and words(anchor):
            return url, words(anchor)
    return "", ""


def parse_publications(main):
    rows = {}
    for year, node in year_rows(main):
        url, fallback = first_record_link(node, r"/documentos/[a-zA-Z0-9]+")
        title = class_text(node, "c-doc__titulo") or fallback
        if not url or not title:
            continue
        venue = class_text(node, "c-doc__localizacion")
        authors = class_text(node, "c-doc__autores", "c-doc__autor")
        kind = TYPES.get(node.get("data-type", "").upper(), "sin_clasificar")
        rows[url] = {
            "title": title, "year": year, "type": kind, "authors": authors, "venue": venue, "url": url, "portalUrl": url,
        }
    return list(rows.values())


def parse_projects(main):
    rows = {}
    for year, node in year_rows(main):
        url, fallback = first_record_link(node, r"/(?:proyectos|financiaciones)/[0-9]+(?:/detalle)?")
        title = class_text(node, "proyecto__nombre", "c-proyecto__titulo", "c-financiacion__titulo") or fallback
        if not title and node.getparent().tag == "ol":
            candidate = normalize_text(node.xpath("string((./p | ./div | ./h4 | ./strong | ./span)[1])"))
            if candidate:
                title = candidate
        if not title:
            continue
        title = title.rstrip(" |")
        row = {"title": title, "year": year, "url": url or f"{GROUP}/financiacion", "portalUrl": url}
        reference = class_text(node, "proyecto__identificador", "c-proyecto__referencia", "c-financiacion__acronimo")
        if reference:
            row["reference"] = reference
        rows[url or (title, year)] = row
    return list(rows.values())


def parse_theses(main):
    rows = {}
    for year, node in year_rows(main):
        url, title = first_record_link(node, r"/(?:documentos|tesis)/[a-zA-Z0-9]+(?:/detalle)?")
        if not title:
            continue
        paragraphs = [words(p) for p in node.xpath(".//p") if words(p) and words(p) != title]
        supervisors = [value for value in paragraphs if re.match(r"(Dirigid[ao] por|Direcci[oó]n|Supervised by)\b", value, re.I)]
        author = class_text(node, "c-doc__autores", "c-doc__autor", "c-tesis__autor")
        if not author:
            author = next((value for value in paragraphs if value not in supervisors), "")
        if not author:
            continue
        supervisor = class_text(node, "c-doc__directores") or next(iter(supervisors), "")
        supervisor = re.sub(r"^(?:Dirigid[ao] por|Direcci[oó]n|Supervised by)\s*:?\s*", "", supervisor, flags=re.I)
        rows[url] = {"title": title, "author": author, "supervisors": supervisor, "year": year, "url": url, "portalUrl": url}
    return list(rows.values())


PARSERS = {
    "researchers": profile_rows, "publications": parse_publications,
    "projects": parse_projects, "theses": parse_theses,
}


def result_count(main):
    for node in main.xpath(".//strong | .//h2 | .//h3"):
        sample = words(node.getparent()) if node.tag == "strong" else words(node)
        match = re.fullmatch(r"([\d., ]+)\s+(?:resultados?|results?)", sample, flags=re.I)
        if match:
            return int(re.sub(r"\D", "", match[1]))
    return None


def read_section(source, key, raw):
    document = fromstring(raw, parser=HTMLParser(encoding="utf-8", no_network=True))
    main = document.find(".//main")
    if main is None:
        raise ValueError(f"El Portal UMA devolvió una página sin el listado público de {source}.")
    rows = PARSERS[key](main)
    count = result_count(main)
    if not rows and count != 0:
        raise ValueError(f"No se reconocieron registros del Portal UMA en {source}.")
    return rows, count, main


def classify_publications(rows, main, url, fetch):
    options = main.xpath('.//*[@data-menu-param="agrTipoPublicacion"]//script[@data-menu-options]/text()')
    if not options:
        return
    by_url = {row["url"]: row for row in rows}
    for option in json.loads(options[0]):
        key = option.get("v")
        if key not in TYPES or not str(option.get("c", "")).isdigit():
            continue
        count = int(option["c"])
        if not count:
            continue
        query = urlencode({"agrTipoPublicacion": key, "size": min(count, MAX_LIST_SIZE)})
        subset, reported, _ = read_section("publicaciones", "publications", fetch(f"{url}?{query}", "publicaciones"))
        if reported != count:
            print(f"Portal UMA: el filtro {key} no coincidió con su recuento; se omitió esta clasificación.")
            continue
        for match in subset:
            if match["url"] in by_url:
                by_url[match["url"]]["type"] = TYPES[key]


def read_portal(snapshot: Path | None = None):
    """Use public HTML, pausing between requests and stopping at access limits."""
    payload = {"date": date.today().isoformat(), "metrics": []}
    robots = get_robots() if snapshot is None else None
    wait = (robots.crawl_delay(AGENT) or 1) if robots is not None else 0

    def fetch(url, label):
        if not robots.can_fetch(AGENT, url):
            raise ValueError(f"robots.txt del Portal UMA excluye {label}.")
        sleep(wait)
        try:
            return read_page(url)
        except HTTPError as error:
            raise portal_error(error, label) from None

    captured = []
    for source, key in SECTIONS.items():
        url = f"{GROUP}/{source}"
        if snapshot is not None:
            file = snapshot / f"{source}.html"
            if not file.is_file():
                continue
            raw = file.read_bytes()
            captured.append(file.stat().st_mtime)
        else:
            raw = fetch(url, source)
        rows, count, main = read_section(source, key, raw)
        if snapshot is None and count is not None and count > len(rows) and main.xpath(".//*[@hx-vals]"):
            size = min(count, MAX_LIST_SIZE)
            rows, _, _ = read_section(source, key, fetch(f"{url}?size={size}", source))
        if snapshot is None and key == "publications":
            classify_publications(rows, main, url, fetch)
        if count is not None and count > len(rows):
            print(f"Portal UMA: {source} entrega {len(rows)} de {count} registros anunciados.")
        payload[key] = rows
        if count is not None and key in METRICS:
            title, title_en = METRICS[key]
            payload["metrics"].append({
                "title": title, "titleEn": title_en, "value": count, "url": url, "source": "Portal de Investigación UMA",
            })
    if snapshot is not None:
        if not captured:
            raise ValueError("La carpeta no contiene páginas HTML del Portal UMA.")
        payload["date"] = date.fromtimestamp(max(captured)).isoformat()
    for metric in payload["metrics"]:
        metric["date"] = payload["date"]
    return payload

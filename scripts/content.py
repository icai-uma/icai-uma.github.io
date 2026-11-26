"""Read the editor workbook and an optional authorized UMA export."""
import json
import re
import unicodedata
from datetime import date
from io import BytesIO
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from openpyxl import load_workbook

PORTAL = "https://portaldelainvestigacion.uma.es"
GROUP = f"{PORTAL}/grupos/69865"
DEFAULT_SOURCE = f"{GROUP}/detalle"
REQUIRED = {
    "group": ("key", "es"),
    "lines": ("title", "description"),
    "team": ("name",),
    "publications": ("title", "year", "type"),
    "projects": ("title", "year"),
    "theses": ("title", "year", "author"),
    "news": ("title", "date"),
    "metrics": ("title", "value", "source", "date"),
}
PUBLICATION_TYPES = {"articulo", "congreso", "capitulo", "libro", "otro", "sin_clasificar"}
EXTERNAL_SECTIONS = ("publications", "projects", "theses", "metrics")
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"


def text(value):
    return "" if value is None else str(value).strip()


def normalized(value):
    decomposed = unicodedata.normalize("NFKD", text(value).casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in decomposed if not unicodedata.combining(c))))


def safe_url(value):
    parts = urlsplit(value)
    if parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password:
        return value
    return ""


def download(url, token="", max_bytes=20_000_000):
    if not safe_url(url) or urlsplit(url).scheme != "https":
        raise ValueError("Las URL de sincronización deben usar HTTPS.")
    headers = {"User-Agent": "ICAI-UMA-website/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        # An authenticated export must use its final URL.
        from urllib.error import HTTPError
        from urllib.request import HTTPRedirectHandler, build_opener

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, response_headers, newurl):
                return None

        opener = build_opener(NoRedirect()).open
    else:
        from urllib.error import HTTPError
        opener = urlopen
    try:
        with opener(Request(url, headers=headers), timeout=40) as response:
            data = response.read(max_bytes + 1)
    except HTTPError as error:
        raise ValueError(f"La fuente remota devolvió HTTP {error.code}.") from None
    except OSError:
        raise ValueError("No se pudo acceder a la fuente remota.") from None
    if len(data) > max_bytes:
        raise ValueError("La fuente remota supera el tamaño admitido.")
    return data


def drive_workbook(file_id, folder_id, token):
    if not token:
        raise ValueError("Falta la credencial de lectura de Google Drive.")
    for identifier in (file_id, folder_id):
        if identifier and not re.fullmatch(r"[a-zA-Z0-9_-]+", identifier):
            raise ValueError("El identificador de Google Drive no es válido.")
    if not file_id:
        query = urlencode({
            "q": f"'{folder_id}' in parents and name = 'ICAI_DATOS.xlsx' and trashed = false",
            "fields": "nextPageToken,incompleteSearch,files(id)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "pageSize": "10",
        })
        result = json.loads(download(f"{DRIVE_FILES}?{query}", token))
        files = result.get("files", [])
        if len(files) != 1 or result.get("nextPageToken") or result.get("incompleteSearch"):
            raise ValueError("Google Drive debe devolver un único ICAI_DATOS.xlsx en la carpeta.")
        file_id = files[0]["id"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", file_id):
        raise ValueError("Google Drive devolvió un ID de fichero inválido.")
    return download(f"{DRIVE_FILES}/{file_id}?alt=media&supportsAllDrives=true", token)


def flag(value, label, default):
    value = normalized(value)
    if not value:
        return default
    if value in {"si", "true", "1", "yes"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    raise ValueError(f"{label}: escribe Sí o No.")


def parse_record(values, section, label):
    row = {field: text(value) for field, value in values.items()}
    for flag_name, default in (("visible", True), ("featured", False)):
        if flag_name in row:
            row[flag_name] = flag(row[flag_name], label, default)
    if not any(row.get(field) for field in REQUIRED[section]) and not any(
        value for field, value in row.items() if field not in {"featured", "visible"}
    ):
        return None
    for field in REQUIRED[section]:
        if not row.get(field):
            raise ValueError(f"{label}: falta el campo {field}.")
    for field in ("year", "endYear"):
        if row.get(field):
            if not re.fullmatch(r"(?:19|20)\d{2}", row[field]):
                raise ValueError(f"{label}: año inválido.")
            row[field] = int(row[field])
    if row.get("endYear") and row["endYear"] < row["year"]:
        raise ValueError(f"{label}: el fin precede al inicio.")
    if row.get("date"):
        try:
            row["date"] = date.fromisoformat(row["date"].split(" ")[0]).isoformat()
        except ValueError:
            raise ValueError(f"{label}: fecha inválida. Usa AAAA-MM-DD.") from None
    if row.get("id") and not re.fullmatch(r"[0-9]+", row["id"]):
        raise ValueError(f"{label}: el ID UMA debe ser numérico.")
    for field in ("url", "code", "photo"):
        if row.get(field) and not safe_url(row[field]):
            raise ValueError(f"{label}: enlace inválido en {field}.")
    if row.get("orcid"):
        orcid = row["orcid"].removeprefix("https://orcid.org/")
        if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9X]", orcid):
            raise ValueError(f"{label}: ORCID inválido.")
        row["orcid"] = f"https://orcid.org/{orcid}"
    if row.get("doi"):
        doi = re.sub(r"^https?://(?:dx\.)?doi\.org/|^doi:\s*", "", row["doi"], flags=re.I)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise ValueError(f"{label}: DOI inválido.")
        row["doi"] = doi
        row["url"] = row.get("url") or f"https://doi.org/{quote(doi, safe='/():;._-')}"
    if section == "publications" and row["type"] not in PUBLICATION_TYPES:
        raise ValueError(f"{label}: tipo de publicación inválido.")
    return row


def read_workbook(input_bytes, schema):
    try:
        book = load_workbook(BytesIO(input_bytes), read_only=True, data_only=True)
    except Exception as error:
        raise ValueError("La entrada editorial no es un archivo XLSX válido.") from error
    data = {}
    try:
        for sheet, spec in schema.items():
            section = spec["label"]
            if sheet not in book:
                raise ValueError(f"Falta la hoja {sheet}.")
            header, *rows = book[sheet].values
            columns = {name: index for index, name in enumerate(header) if name is not None}
            if len(columns) != sum(name is not None for name in header) or not spec["columns"].keys() <= columns.keys():
                raise ValueError(f"Revisa las cabeceras de la hoja {sheet}.")
            records = []
            for index, row in enumerate(rows, 2):
                values = {field: row[columns[name]] for name, field in spec["columns"].items()}
                record = parse_record(values, section, f"{sheet}, fila {index}")
                if record is not None:
                    records.append(record)
            data[section] = records
    finally:
        book.close()
    group = {row["key"]: row for row in data.pop("group")}
    if not {"name", "intro", "about", "location", "email"} <= group.keys():
        raise ValueError("Grupo: faltan claves de la descripción del grupo.")
    if not re.fullmatch(r"[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", group["email"]["es"]):
        raise ValueError("Grupo: correo inválido.")
    return data, group


def aliases(section, row):
    exact = set()
    url = row.get("portalUrl") or row.get("url", "")
    if urlsplit(url).hostname == urlsplit(PORTAL).hostname and re.match(r"^/(documentos|proyectos|tesis)/[^/]+", urlsplit(url).path):
        exact.add(f'url:{urlsplit(url).path.rstrip("/")}')
    if section == "publications":
        if row.get("doi"):
            exact.add(f'doi:{row["doi"].casefold()}')
        weak = f'{normalized(row["title"])}|{row["year"]}'
    elif section == "projects":
        if row.get("reference"):
            exact.add(f'ref:{normalized(row["reference"])}')
        weak = f'{normalized(row["title"])}|{row["year"]}'
    elif section == "theses":
        author = " ".join(sorted(normalized(row["author"]).split()))
        weak = f'{normalized(row["title"])}|{row["year"]}|{author}'
    else:
        weak = f'{normalized(row["title"])}|{normalized(row["source"])}|{row["date"]}'
    return exact, weak


def merge_records(section, imported, editorial):
    combined = []
    identifiers, titles = {}, {}
    for position, row in enumerate([*imported, *editorial]):
        exact, weak = aliases(section, row)
        matches = {identifiers[key] for key in exact if key in identifiers}
        if not matches and (position >= len(imported) or not exact):
            matches = titles.get(weak, set())
        if len(matches) == 1:
            index = next(iter(matches))
            combined[index].update({key: value for key, value in row.items() if value != ""})
        else:
            index = len(combined)
            combined.append(row.copy())
        for key in exact:
            identifiers[key] = index
        titles.setdefault(weak, set()).add(index)
    return [record for record in combined if record.get("visible", True)]


def merge_portal(data, payload, schema):
    """Allow editorial entries to complete or suppress matching public records."""
    roster = payload.get("researchers", [])
    candidates = {}
    for person in roster:
        if not re.fullmatch(r"[0-9]+", text(person.get("id"))) or not text(person.get("name")):
            raise ValueError("Perfil inválido en los datos del Portal UMA.")
        name = normalized(person["name"])
        candidates.setdefault(name, set()).add(text(person["id"]))
    for person in data["team"]:
        matches = candidates.get(normalized(person["name"]), set())
        if not person.get("id") and len(matches) == 1:
            person["id"] = next(iter(matches))
    for section in EXTERNAL_SECTIONS:
        fields = set(next(spec["columns"].values() for spec in schema.values() if spec["label"] == section))
        imported = []
        for index, row in enumerate(payload.get(section, []), 1):
            record = parse_record(
                {field: value for field, value in row.items() if field in fields},
                section, f"Portal UMA {section}, fila {index}",
            )
            if record:
                if safe_url(row.get("portalUrl", "")):
                    record["portalUrl"] = row["portalUrl"]
                imported.append(record)
        data[section] = merge_records(section, imported, data[section])

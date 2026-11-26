import fs from "node:fs/promises";
import path from "node:path";
import { Workbook, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.argv[2] || process.cwd();
const load = async name => JSON.parse(await fs.readFile(path.join(root, "scripts", name), "utf8"));
const [schema, seed] = await Promise.all([load("workbook_schema.json"), load("seed.json")]);
const workbook = Workbook.create();
const guide = workbook.worksheets.add("Leer primero");
guide.showGridLines = false;
guide.getRange("A1:B8").values = [
  ["ICAI · Edición de la web", "Instrucciones"],
  ["1. Compartir", "Mantén este libro en la unidad compartida ICAI, en la carpeta Web de Google Drive."],
  ["2. Editar", "Añade o modifica filas bajo las cabeceras existentes. Mantén los nombres de las hojas y columnas."],
  ["3. Idiomas", "Si falta un texto en inglés, la web usa el español. Los títulos de artículos y tesis se muestran en su idioma original."],
  ["4. Visibilidad", "Escribe No en Publicar para ocultar una fila. Escribe Sí en Destacar para darle prioridad en Inicio."],
  ["5. Equipo", "Escribe el nombre completo. El ID UMA es el número de la ficha pública y puede quedar vacío si la persona no figura en el portal."],
  ["6. Publicaciones", "Tipos válidos: articulo, congreso, capitulo, libro, otro. Escribe el DOI como 10.xxxx/xxxxx."],
  ["7. Indicadores", "Introduce solo valores autorizados para la web, junto con la fuente y la fecha de corte (AAAA-MM-DD)."]
];
guide.getRange("A:A").format.columnWidth = 29;
guide.getRange("B:B").format.columnWidth = 88;
guide.getRange("A2:B8").format.wrapText = true;
guide.getRange("A2:B8").format.rowHeight = 34;

function header(range) {
  range.format.fill = "#103449";
  range.format.font.color = "#FFFFFF";
  range.format.font.bold = true;
  range.format.rowHeight = 27;
}
header(guide.getRange("A1:B1"));
guide.freezePanes.freezeRows(1);

for (const [name, { label, columns }] of Object.entries(schema)) {
  const sheet = workbook.worksheets.add(name);
  const headers = Object.keys(columns);
  const fields = Object.values(columns);
  const records = seed[label];
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRangeByIndexes(0, 0, 1, headers.length).values = [headers];
  header(sheet.getRangeByIndexes(0, 0, 1, headers.length));
  if (records.length) {
    const values = records.map(record => fields.map(field => record[field] ?? (field === "visible" ? "Sí" : null)));
    sheet.getRangeByIndexes(1, 0, values.length, headers.length).values = values;
  }
  fields.forEach((field, column) => {
    const range = sheet.getRangeByIndexes(1, column, Math.max(12, records.length), 1);
    const prose = /^(description|title|authors|topics|es$|en$)/.test(field);
    range.format.columnWidth = prose ? 51 : /url|photo|orcid|doi|code/.test(field) ? 33 : 23;
    range.format.wrapText = prose;
    if (["id", "date", "doi", "reference"].includes(field)) range.setNumberFormat("@");
  });
  for (let row = 0; row < records.length; row += 1) {
    const range = sheet.getRangeByIndexes(row + 1, 0, 1, headers.length);
    range.format.rowHeight = ["group", "lines", "projects", "publications", "news"].includes(label) ? 44 : 28;
    if (row % 2 === 0) range.format.fill = "#EDF5F6";
  }
}
const preview = await workbook.render({sheetName:"Leer primero", range:"A1:B8", scale:1, format:"png"});
if (process.argv[3]) await fs.writeFile(process.argv[3], new Uint8Array(await preview.arrayBuffer()));
const file = await SpreadsheetFile.exportXlsx(workbook);
await file.save(path.join(root, "ICAI_DATOS.xlsx"));

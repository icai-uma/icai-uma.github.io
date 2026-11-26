# Web del grupo ICAI

Sitio bilingüe del grupo **Inteligencia Computacional y Análisis de Imágenes** (TIC-163) de la Universidad de Málaga. Se genera como HTML estático a partir de un Excel. Las páginas incluyen portada, equipo, investigación, noticias y recursos abiertos. La ruta histórica `/repositories.html` enlaza con la nueva página de recursos.

## Editar el contenido

Abre `ICAI_DATOS.xlsx` y consulta la hoja **Leer primero**. Las demás hojas contienen el perfil del grupo, las líneas, el equipo, publicaciones, proyectos, tesis, noticias e indicadores. Conserva las cabeceras. Los datos del Excel autorizados para difusión se convierten en páginas; coloca las notas internas y datos de acceso en otro lugar.

- **Equipo.** Añade el nombre completo. Puedes incluir el ID numérico de la ficha pública del Portal de Investigación UMA para enlazarla directamente. Una exportación institucional con un índice `researchers` permite resolver automáticamente los nombres exactos tras quitar tildes, signos y diferencias de mayúsculas. Los homónimos quedan pendientes hasta añadir un ID al Excel.
- **Publicaciones y proyectos.** Completa el DOI o la referencia si existen. Durante la generación, el Excel prevalece en los campos que rellene y las filas marcadas **No** en **Publicar** ocultan los resultados coincidentes. La página de investigación enlaza con los listados oficiales completos.
- **Indicadores.** Cada dato requiere fuente y fecha de corte. Publica valores que el grupo pueda difundir. La [guía de la UMA](https://biblioguias.uma.es/portaldelainvestigacion/Indicadores) indica qué información se consulta desde su red.

## Google Drive y GitHub Pages

El equipo edita `ICAI_DATOS.xlsx` en **Unidades compartidas → ICAI → Web**, manteniendo el archivo como XLSX. GitHub Actions admite lectura privada mediante un token temporal de Google Cloud y la [API de Google Drive](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

1. En un proyecto de Google Cloud autorizado por la UMA, habilita las API de Drive, IAM Credentials y Security Token Service y configura [Workload Identity Federation para GitHub Actions](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines). Limita el proveedor a `assertion.repository_owner_id == '66728436' && assertion.repository_id == '333233318' && assertion.ref == 'refs/heads/master' && assertion.workflow_ref == 'icai-uma/icai-uma.github.io/.github/workflows/pages.yml@refs/heads/master'`. Autoriza a la identidad federada de ese repositorio a impersonar una cuenta de servicio mediante `roles/iam.workloadIdentityUser`.
2. Dale a esa cuenta acceso de **Lector** al archivo Excel y copia su ID de Google Drive. La cuenta de servicio y la configuración de Workload Identity Federation deben estar permitidas por la política de la unidad compartida. Si se concede permiso sobre la carpeta de forma deliberada, también se admite su ID. En ese caso el flujo busca un único archivo llamado `ICAI_DATOS.xlsx`.
3. En el repositorio, abre **Settings → Secrets and variables → Actions → Variables**. Configura `ICAI_GCP_IDENTITY_PROVIDER` con la ruta completa del proveedor, `ICAI_GCP_SERVICE_ACCOUNT` con su correo y `ICAI_DRIVE_FILE_ID` con el ID del archivo. Para lectura autorizada por carpeta, utiliza en su lugar `ICAI_DRIVE_FOLDER_ID`. El flujo usa la copia inicial del repositorio hasta que se configure un ID.
4. En **Settings → Pages → Build and deployment → Source**, selecciona **GitHub Actions**. Ejecuta **Actions → Sincronizar web ICAI → Run workflow** y comprueba que un cambio visible en Excel aparece en la web. El flujo se ejecuta cada día alrededor de las 06:18 UTC, y tras cambios en `master`. Si falla una fuente configurada o su validación, Pages conserva el despliegue anterior.

El artefacto de Pages contiene las páginas y los recursos estáticos. El libro compartido y las exportaciones originales se procesan durante la compilación.

## Producción científica de la UMA

El portal identifica a ICAI como grupo **69865**. La [API de exportación de Dialnet CRIS](https://fundaciondialnet.unirioja.es/servicios/dialnet-cris/) permite obtener datos e indicadores cuando la institución habilita el servicio. Para conectar el servicio, pide a Biblioteca o al responsable del Portal acceso, el esquema técnico y autorización de publicación conforme al [aviso legal del Portal](https://portaldelainvestigacion.uma.es/aviso_legal). La ficha del grupo y los listados enlazados son la referencia para delimitar la producción atribuida a ICAI.

Esta versión admite una **exportación institucional normalizada** en JSON, descargable por HTTPS (`ICAI_UMA_EXPORT_URL`, con `ICAI_UMA_EXPORT_TOKEN` opcional, ambos como secretos de Actions). El formato que devuelve la API debe adaptarse al contrato descrito abajo una vez recibido. Para probarlo localmente, utiliza `--export` con un fichero del mismo formato. Este lector combina los registros autorizados con los campos curatoriales del Excel en cada ejecución. El Excel permanece como fuente editorial compartida.

```json
{
  "version": 1,
  "groupId": "69865",
  "date": "2026-11-26",
  "researchers": [{"id": "1241323", "name": "Ezequiel López Rubio"}],
  "publications": [],
  "projects": [],
  "theses": [],
  "metrics": []
}
```

Los elementos de las cuatro colecciones usan los nombres internos de la hoja respectiva en [workbook_schema.json](scripts/workbook_schema.json). Los campos mínimos son `title, year, type` para publicaciones, `title, year` para proyectos, `title, year, author` para tesis, y `title, value, source, date` para indicadores. Usa el identificador oficial para evitar asociar producción personal ajena a la del grupo. Los indicadores deben estar autorizados para su publicación.

## Previsualización local

Requiere Python 3.12 o posterior.

```sh
python -m pip install -r requirements.txt
python scripts/build_site.py
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Abre [la previsualización local](http://127.0.0.1:8000/). También puedes abrir directamente `_site/index.html` una vez generada. La imagen abstracta de la portada es una ilustración generada. El catálogo inicial incluye una selección editorial y enlaces a los listados oficiales.

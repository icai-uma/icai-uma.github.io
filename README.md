# Web del grupo ICAI

Sitio bilingüe del grupo **Inteligencia Computacional y Análisis de Imágenes** (TIC-163) de la Universidad de Málaga. Se genera como HTML estático a partir de un Excel. Las páginas incluyen portada, equipo, investigación, noticias y recursos abiertos. La ruta histórica `/repositories.html` enlaza con la nueva página de recursos.

## Editar el contenido

Abre `ICAI_DATOS.xlsx` y consulta la hoja **Leer primero**. Las demás hojas contienen el perfil del grupo, las líneas, el equipo, publicaciones, proyectos, tesis, noticias e indicadores. Conserva las cabeceras. Los datos del Excel autorizados para difusión se convierten en páginas; coloca las notas internas y datos de acceso en otro lugar.

- **Equipo.** Añade el nombre completo. Puedes incluir el ID numérico de la ficha pública del Portal de Investigación UMA. La lectura directa de la ficha oficial de ICAI permite resolver nombres exactos tras quitar tildes, signos y diferencias de mayúsculas. Los homónimos quedan pendientes hasta añadir un ID al Excel.
- **Publicaciones y proyectos.** Completa el DOI o la referencia si existen. Durante la generación, el Excel prevalece en los campos que rellene y las filas marcadas **No** en **Publicar** ocultan los resultados coincidentes. La página de investigación enlaza con los listados oficiales completos.
- **Indicadores.** Cada dato requiere fuente y fecha de corte. Publica valores que el grupo pueda difundir. La [guía de la UMA](https://biblioguias.uma.es/portaldelainvestigacion/Indicadores) indica qué información se consulta desde su red.

## Google Drive y GitHub Pages

El equipo edita `ICAI_DATOS.xlsx` en **Unidades compartidas → ICAI → Web**, manteniendo el archivo como XLSX. GitHub Actions admite lectura privada mediante un token temporal de Google Cloud y la [API de Google Drive](https://developers.google.com/workspace/drive/api/guides/manage-downloads).

1. En un proyecto de Google Cloud autorizado por la UMA, habilita las API de Drive, IAM Credentials y Security Token Service y configura [Workload Identity Federation para GitHub Actions](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines). Limita el proveedor a `assertion.repository_owner_id == '66728436' && assertion.repository_id == '333233318' && assertion.ref == 'refs/heads/master' && assertion.workflow_ref == 'icai-uma/icai-uma.github.io/.github/workflows/pages.yml@refs/heads/master'`. Autoriza a la identidad federada de ese repositorio a impersonar una cuenta de servicio mediante `roles/iam.workloadIdentityUser`.
2. Dale a esa cuenta acceso de **Lector** al archivo Excel y copia su ID de Google Drive. La cuenta de servicio y la configuración de Workload Identity Federation deben estar permitidas por la política de la unidad compartida. Si se concede permiso sobre la carpeta de forma deliberada, también se admite su ID. En ese caso el flujo busca un único archivo llamado `ICAI_DATOS.xlsx`.
3. En el repositorio, abre **Settings → Secrets and variables → Actions → Variables**. Configura `ICAI_GCP_IDENTITY_PROVIDER` con la ruta completa del proveedor, `ICAI_GCP_SERVICE_ACCOUNT` con su correo y `ICAI_DRIVE_FILE_ID` con el ID del archivo. Para lectura autorizada por carpeta, utiliza en su lugar `ICAI_DRIVE_FOLDER_ID`. El flujo usa la copia inicial del repositorio hasta que se configure un ID.
4. En **Settings → Pages → Build and deployment → Source**, selecciona **GitHub Actions**. Ejecuta **Actions → Sincronizar web ICAI → Run workflow** y comprueba que un cambio visible en Excel aparece en la web. El flujo se ejecuta cada día alrededor de las 06:18 UTC, y tras cambios en `master`. Si falla una fuente configurada o su validación, Pages conserva el despliegue anterior.

El artefacto de Pages contiene las páginas y los recursos estáticos. El libro compartido se procesa durante la compilación.

## Producción científica de la UMA

El lector usa directamente las páginas públicas del [grupo ICAI, ficha 69865](https://portaldelainvestigacion.uma.es/grupos/69865/detalle). Obtiene los identificadores de los perfiles, la producción del grupo, los proyectos y las tesis. En publicaciones, los campos dependen de lo que muestre el listado. El enlace a la ficha permite consultar la referencia completa. Los recuentos públicos se etiquetan con su fuente y fecha. Los indicadores bibliométricos que solo están disponibles desde la red de la UMA se consultan en el portal.

Para probar la consulta directa desde una instalación local, ejecuta:

```sh
python scripts/build_site.py --from-uma
```

Durante la compilación se combinan los registros con el Excel. Las columnas editoriales completas prevalecen y **Publicar = No** permite ocultar una coincidencia. El lector respeta `robots.txt`, hace un número acotado de consultas y se detiene si el portal limita el acceso. En ese caso un flujo de publicación conserva el despliegue anterior. El [aviso legal del Portal UMA](https://portaldelainvestigacion.uma.es/aviso_legal) distingue entre enlazar y reproducir sus contenidos. Para incorporar automáticamente los registros a la web pública, usa la variable `ICAI_UMA_PUBLIC_SYNC=true` en GitHub Actions cuando la UMA permita su republicación.

## Previsualización local

Requiere Python 3.12 o posterior.

```sh
python -m pip install -r requirements.txt
python scripts/build_site.py
python -m http.server 8000 --bind 127.0.0.1 --directory _site
```

Abre [la previsualización local](http://127.0.0.1:8000/). También puedes abrir directamente `_site/index.html` una vez generada. Investigación abre en Líneas. Las pestañas conservan enlaces directos como `investigacion.html#proyectos`.

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
# Naviera-Registro

Aplicacion web en Django para el alta de navieras y la gestion inicial de su flota dentro del proceso PBIP de Global Maritime Protection.

## Repositorio

- Gitea `origin`: `http://192.168.100.201:3000/yogit/Naviera-Registro.git`

## Funcionalidad actual

- Registro de navieras desde un formulario publico.
- Validacion de seguridad con Google reCAPTCHA Enterprise.
- Creacion automatica de usuario Django y registro vinculado de la naviera.
- Envio de correo con contrasena temporal al completar el alta.
- Inicio de sesion desde la misma pagina de registro.
- Cambio obligatorio de contrasena en el primer acceso.
- Portal del cliente para registrar buques de la naviera.
- Vista inicial del expediente pre-servicio por buque.
- Paginas informativas de politica de privacidad y configuracion de cookies.

## Stack

- Python
- Django 5.2.2
- SQLite para desarrollo local
- HTML, CSS y JavaScript
- `django-recaptcha`
- Pillow

## Estructura del proyecto

```text
Naviera-Registro/
├── manage.py
├── requirements.txt
├── naviera_registro/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── settings.py
│   ├── templates/
│   └── static/
└── portal_cliente/
    ├── views.py
    ├── urls.py
    └── templates/
```

## Modelos principales

### `Naviera`

- Vinculada `OneToOne` con `django.contrib.auth.models.User`
- Almacena empresa, contacto principal y correo electronico

### `Buque`

- Pertenece a una `Naviera`
- Guarda nombre del buque y numero OMI

### `RequisitoBuque`

- Relacionado con `Buque`
- Permite registrar documentos por categoria:
  - `COTIZACION`
  - `DOCUMENTAL`
  - `ADMINISTRATIVO`

## Rutas principales

- `/` y `/registro-naviera/`: registro de navieras
- `/login/`: autenticacion
- `/portal/`: portal del cliente
- `/portal/cambiar-password/`: cambio obligatorio de contrasena
- `/portal/agregar-buque/`: alta de buques
- `/politica-privacidad/`: aviso de privacidad
- `/configuracion-cookies/`: preferencias de cookies
- `/admin/`: administrador de Django

## Instalacion local

1. Clonar el repositorio.
2. Crear y activar un entorno virtual.
3. Instalar dependencias.
4. Ejecutar migraciones.
5. Iniciar el servidor.

```bash
git clone http://192.168.100.201:3000/yogit/Naviera-Registro.git
cd Naviera-Registro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Dependencias

Archivo [`requirements.txt`](/home/julian/Naviera-Registro/requirements.txt):

- `Django==5.2.2`
- `django-recaptcha==4.0.0`
- `captcha==0.5.0`
- `pillow==12.1.1`

## Flujo de uso

1. La naviera completa el formulario publico de registro.
2. El sistema valida el captcha y crea un usuario con contrasena temporal.
3. Se crea el registro de la naviera y se envia el acceso por correo.
4. El usuario inicia sesion.
5. En el primer acceso debe establecer su contrasena definitiva.
6. Ya dentro del portal puede agregar buques y consultar su expediente base.

## Configuracion actual

- `ALLOWED_HOSTS`: `192.168.100.240`, `localhost`, `127.0.0.1`
- Base de datos local: `db.sqlite3`
- Idioma: `es-mx`
- Zona horaria: `America/Mexico_City`

## Observaciones tecnicas

- El proyecto usa credenciales SMTP y llaves de reCAPTCHA directamente en el codigo. Para un despliegue real conviene moverlas a variables de entorno.
- La carga completa de documentos por expediente aun no esta terminada en las plantillas del portal.
- En `requirements.txt` no aparece `requests`, aunque se usa en [`naviera_registro/views.py`](/home/julian/Naviera-Registro/naviera_registro/views.py).

## Documentacion adicional

- [`docs/README.md`](/home/julian/Naviera-Registro/docs/README.md)
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
# tile_rag (VAMA 3.5)

Asistente de cotización para materiales y acabados con **Flask + ChromaDB + Ollama**, optimizado para conversación natural, memoria de usuario y generación de PDF.

## ¿Qué cambió recientemente?

Esta versión documenta los cambios más recientes del branch (`happy-path-complete`, `requirements-update` e `ingest-update`):

- **Flujo conversacional “happy path” reforzado** en `vama-agent2.py`:
  - Validaciones de conexión al arrancar (Ollama, Chroma y embeddings).
  - Memoria conversacional persistente con historial.
  - Interceptores para cierres de compra/pago/agradecimientos (evita “volver a vender” cuando el cliente ya está cerrando).
  - Manejo de cotización con resumen total y registro de cotizaciones cerradas.
- **Operación y observabilidad**:
  - Logs diarios de conversación en `logs/`.
  - Dataset incremental para fine-tuning en `dataset/conversaciones_completas.jsonl`.
  - Dashboard simple en `/dashboard` y healthcheck en `/health`.
- **Salida comercial**:
  - Generación de PDF por cliente en `cotizaciones/` y descarga por endpoint.
- **Dependencias actualizadas** en `requirements.txt`.
- **Ingesta** con ajuste reciente en `ingest_tiles_catalog.py`.

---

## Estructura del proyecto

- `vama-agent2.py`: servidor principal (VAMA 3.5) y lógica conversacional.
- `vama-agent.py`: versión alternativa previa/corregida.
- `ingest_tiles_catalog.py`: ingesta de CSVs a Chroma en colecciones por categoría.
- `catalog.py`: utilidades de búsqueda rápida por código, CSV y fallback de Chroma.
- `revisar_db.py`: inspección rápida de documentos/metadatos en Chroma.
- `test_vama.py`: prueba de conectividad directa contra Ollama API.
<<<<<<< ours
<<<<<<< ours
- `tests/router_tests.sh`: smoke tests del endpoint `/webhook` con `curl`.
- `data/`: archivos base de catálogo por categoría.
=======
- `tests/router_tests.sh`: smoke tests históricos del endpoint `/webhook`.
>>>>>>> theirs
=======
- `tests/router_tests.sh`: smoke tests históricos del endpoint `/webhook`.
>>>>>>> theirs
- `catalog_work/codes_index.json`: índice de códigos para lookup.
- `dataset/`, `logs/`, `cotizaciones/`: artefactos generados en runtime.

---

## Requisitos

- Python 3.10+
- Ollama levantado localmente en `http://127.0.0.1:11434`
- Modelo Ollama disponible (default del proyecto: `qwen2.5:14b`)
<<<<<<< ours
<<<<<<< ours
- ChromaDB persistente en `chroma_db_v3`
=======
>>>>>>> theirs
=======
>>>>>>> theirs

Instalación de dependencias:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

<<<<<<< ours
<<<<<<< ours
=======
=======
>>>>>>> theirs
## ChromaDB y datos de catálogo

La base de datos de Chroma (`chroma_db_v3`) **se genera localmente** con la ingesta y **no debe versionarse** en el repositorio.

Los CSV de entrada para la ingesta se esperan en un directorio local `data/` (por ejemplo `data/nacionales.csv`, `data/importados.csv`, etc.).

---

<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
## Ingesta de catálogo

Ingesta completa (si están los CSV esperados en `data/`):

```bash
python ingest_tiles_catalog.py --tipo todo
```

Ingesta por categoría (ejemplo):

```bash
python ingest_tiles_catalog.py --tipo nacionales --file data/nacionales.csv
python ingest_tiles_catalog.py --tipo importados --file data/importados.csv
python ingest_tiles_catalog.py --tipo promos --file data/promo.csv
```

Tipos soportados por `--tipo`:

`nacionales`, `importados`, `griferia`, `lavabos`, `sanitarios`, `muebles`, `tinacos`, `espejos`, `tarjas`, `herramientas`, `polvos`, `otras`, `promos`, `todo`.

---

## Ejecutar el agente principal

```bash
python vama-agent2.py
```

<<<<<<< ours
<<<<<<< ours
Por defecto corre en `0.0.0.0:5001`.

### Endpoints
=======
El servicio corre en **`0.0.0.0:5001`**.

### Endpoints (puerto 5001)
>>>>>>> theirs
=======
El servicio corre en **`0.0.0.0:5001`**.

### Endpoints (puerto 5001)
>>>>>>> theirs

- `POST /webhook`: entrada principal de conversación.
- `GET /pdf/<telefono>`: descarga el último PDF generado para el cliente.
- `GET /dashboard`: tablero simple de operación (usuarios, cotizaciones, logs).
- `GET /health`: estado básico del servicio.

Ejemplo de request:

```bash
curl -X POST "http://127.0.0.1:5001/webhook" \
  -H "Content-Type: application/json" \
  -d '{"telefono":"5215512345678","nombre":"Cliente","mensaje":"Necesito piso blanco para baño"}'
```

---

## Pruebas y utilidades

Prueba de conectividad Ollama (sin librería intermedia):

```bash
python test_vama.py
```

Inspección rápida de Chroma:

```bash
python revisar_db.py
```

<<<<<<< ours
<<<<<<< ours
Smoke tests del router (requiere servidor activo y `jq`):

```bash
bash tests/router_tests.sh
```

=======
=======
>>>>>>> theirs
Prueba rápida del router en puerto 5001:

```bash
curl -s -X POST "http://127.0.0.1:5001/webhook" \
  -H "Content-Type: application/json" \
  -d '{"telefono":"demo","nombre":"Cliente","mensaje":"CMX01"}'
```

> Nota: `tests/router_tests.sh` es un script histórico; valida/ajusta su puerto antes de usarlo si tu entorno está en `5001`.

<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
---

## Notas operativas

- El modelo configurado en código es `qwen2.5:14b`. Si usarás otro modelo, actualiza la constante `MODELO`.
- El sistema persiste memoria de usuarios en `memoria_vama.pkl`.
- El dataset para fine-tuning crece con conversaciones útiles; considera rotación/limpieza periódica.
- El endpoint `/dashboard` usa lecturas directas de archivos de logs/dataset para monitoreo rápido.
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs

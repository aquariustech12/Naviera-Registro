# Naviera-Registro

Aplicación web en Django para el registro de navieras, gestión documental de buques y seguimiento inicial del expediente pre-servicio dentro del flujo PBIP de Global Maritime Protection.

El proyecto también incluye MIA, un asistente interno de auditoría marítima integrado al portal y a webhooks de WhatsApp. Su lógica está dividida por responsabilidades dentro de `portal_cliente/`.

## Qué hace hoy

- Registro público de navieras con validación por Google reCAPTCHA Enterprise.
- Creación automática de usuario Django y alta de la naviera asociada.
- Envío de contraseña temporal por correo al completar el registro.
- Inicio de sesión desde la misma pantalla de acceso/registro.
- Cambio obligatorio de contraseña en el primer acceso.
- Portal del cliente para registrar buques.
- Selección de esquema de pago por buque: 100% o 50/50.
- Carga de documentos por buque para cotización y verificación documental PBIP.
- Carga de documentos administrativos generales de la naviera.
- Carga y validación de comprobantes de pago.
- Gestión de entregables como cotización, informe PBIP, factura, XML y comprobantes.
- Descarga de entregables desde el portal del cliente.
- Eliminación/rechazo de documentos desde administración con motivo y notificación al cliente.
- Análisis MIA sobre documentos cargados, consultas PBIP, consultas de estado y alertas por WhatsApp.

## Stack actual

- Python 3
- Django 5.2.2
- SQLite para entorno local
- HTML, CSS y JavaScript
- `django-recaptcha`
- Pillow
- Requests
- LangChain, Chroma y Ollama para RAG/LLM
- `pdfplumber`, `pdf2image`, `pytesseract` y `python-docx` para extracción de texto/OCR cuando están disponibles

## Estructura del repositorio

```text
Naviera-Registro/
├── manage.py
├── requirements.txt
├── README.md
├── docs/
├── biblioteca_mia/
│   ├── CODIGO PBIP GMP_unlocked.pdf
│   └── GUIA PROTECCION MARITIMA IENPAC_unlocked.pdf
├── scripts/
│   ├── build_maritime_brain.py
│   ├── poblar_chroma.py
│   └── sample_fragments.txt
├── naviera_registro/
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   ├── models.py
│   ├── admin.py
│   ├── migrations/
│   ├── static/
│   └── templates/
├── portal_cliente/
│   ├── views.py
│   ├── urls.py
│   ├── models.py
│   ├── admin.py
│   ├── mia_core.py
│   ├── mia_documentos.py
│   ├── mia_herramientas.py
│   ├── mia_memoria.py
│   ├── migrations/
│   └── templates/
└── staticfiles/
```

## Módulos principales

### `naviera_registro/`

Contiene la configuración base del proyecto Django, rutas raíz, vistas públicas de registro/login, modelos principales, administración, plantillas públicas y archivos estáticos propios.

### `portal_cliente/`

Contiene el portal autenticado del cliente: vista principal, alta de buques, carga de documentos, comprobantes, descargas de entregables, webhooks de MIA y acciones administrativas relacionadas con documentos.

### MIA modular

MIA se separó en cuatro archivos:

- `portal_cliente/mia_core.py`: punto único de entrada con `procesar_input_mia()`. Clasifica intención, decide si debe analizar documento, consultar normativa PBIP, consultar estado o responder conversación general.
- `portal_cliente/mia_documentos.py`: análisis de documentos cargados, extracción de texto y dictamen técnico con apoyo de PBIP/Ollama.
- `portal_cliente/mia_herramientas.py`: utilidades compartidas de MIA: Ollama, Chroma, extracción universal de texto, consultas ORM de estado, reporte global y envío de WhatsApp.
- `portal_cliente/mia_memoria.py`: memoria conversacional basada en el modelo `ConversacionMIA`.

### `scripts/`

- `build_maritime_brain.py`: reconstruye la base Chroma desde la biblioteca PBIP usando extracción, limpieza OCR, chunking y embeddings de Ollama.
- `poblar_chroma.py`: script simple para indexar el Código PBIP en Chroma.
- `sample_fragments.txt`: muestra de fragmentos generados para inspección.

## Modelos principales

### `Naviera`

- Relación `OneToOne` con `django.contrib.auth.models.User`.
- Guarda empresa, contacto principal, correo electrónico, estado de alta completa y fecha de alta completa.

### `Buque`

- Relación `ForeignKey` con `Naviera`.
- Guarda nombre del buque, número OMI, método de pago y estado de pagos.

### `RequisitoBuque`

- Almacena documentos de pre-servicio.
- Soporta categorías `COTIZACION`, `DOCUMENTAL` y `ADMINISTRATIVO`.
- Puede quedar sin buque para documentos administrativos generales.
- Incluye motivo de rechazo/eliminación.

### `PuntoPBIP`

- Catálogo maestro de puntos de revisión PBIP.
- Se usa para mostrar la estructura documental del expediente en el portal.

### `DocumentoEntregable`

- Guarda entregables finales por naviera o por buque.
- Tipos actuales: `COTIZACION`, `INFORME_PBIP`, `FACTURA` y `COMPROBANTE_PAGO`.
- Soporta archivo PDF/principal, XML opcional y secuencia para pagos.
- Envía aviso al cliente cuando se crea un nuevo entregable.

### `AnalisisMIA`

- Relación `OneToOne` con `RequisitoBuque`.
- Conserva resumen técnico, alertas y metadatos del análisis automático.

### `ConversacionMIA`

- Memoria de conversación de MIA por número de WhatsApp.
- Guarda rol, contenido, intención, metadatos y timestamp.

## Rutas principales

- `/` y `/registro-naviera/`: alta pública de navieras.
- `/login/`: autenticación.
- `/logout/`: cierre de sesión.
- `/portal/`: portal principal del cliente.
- `/portal/cambiar-password/`: cambio obligatorio de contraseña.
- `/portal/agregar-buque/`: alta de buques.
- `/portal/actualizar-metodo-pago/<buque_id>/`: actualización de esquema de pago.
- `/portal/subir-archivo/<buque_id>/`: carga documental por buque.
- `/portal/subir-finanzas/`: carga documental administrativa.
- `/portal/subir-comprobante-pago/<buque_id>/`: carga de comprobante por buque.
- `/portal/subir-comprobante-pago/`: carga de comprobante general.
- `/portal/descargar/<doc_id>/`: descarga de entregable principal.
- `/portal/descargar/<doc_id>/<formato>/`: descarga de entregable por formato, por ejemplo PDF o XML.
- `/portal/admin/eliminar-documento/<doc_id>/`: eliminación con motivo desde flujo administrativo.
- `/webhook-mia/`: webhook de mensajes de texto para MIA.
- `/webhook-mia-documento/`: webhook de documentos para MIA.
- `/politica-privacidad/`: aviso de privacidad.
- `/configuracion-cookies/`: configuración de cookies.
- `/admin/`: administrador de Django.

## Flujo funcional

1. La naviera se registra desde el formulario público.
2. El sistema valida reCAPTCHA, crea el usuario y crea el registro de naviera.
3. Se envía una contraseña temporal por correo.
4. El usuario inicia sesión y debe cambiar su contraseña.
5. Desde el portal registra buques, elige método de pago y sube documentos.
6. Las cargas documentales pueden disparar análisis MIA en segundo plano.
7. Cuando la naviera completa documentos administrativos, queda marcada como alta completa.
8. El administrador carga entregables; el cliente recibe aviso y puede descargarlos desde el portal.
9. MIA atiende consultas por WhatsApp/webhook sobre PBIP, estado de expedientes y documentos.

## Instalación local

```bash
git clone <URL_DEL_REPOSITORIO>
cd Naviera-Registro
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Servidor local por defecto: `http://127.0.0.1:8000/`

## Configuración actual del proyecto

- Base de datos local: `db.sqlite3`
- `DEBUG = True`
- `ALLOWED_HOSTS = ['192.168.100.240', 'localhost', '127.0.0.1']`
- Idioma: `es-mx`
- Zona horaria: `America/Mexico_City`
- Archivos estáticos de desarrollo: `naviera_registro/static/`
- Archivos estáticos recolectados: `staticfiles/`
- Archivos subidos: `media/`
- Base vectorial esperada por MIA: `scripts/chroma_db`
- Ollama local esperado por MIA: `http://localhost:11434/api/generate`
- Modelo de generación usado por MIA: `qwen2.5:14b`
- Modelo de embeddings usado por MIA: `nomic-embed-text`

## Base de conocimiento MIA

Para reconstruir la base vectorial PBIP:

```bash
cd scripts
python build_maritime_brain.py
```

El script lee `biblioteca_mia/CODIGO PBIP GMP_unlocked.pdf`, genera fragmentos, guarda una muestra en `scripts/sample_fragments.txt` y persiste la colección Chroma en `scripts/chroma_db`.

## Integraciones

- SMTP para envío de contraseñas, acuses, entregables y rechazos.
- Google reCAPTCHA Enterprise para registro público.
- Ollama local para generación de respuestas y embeddings.
- Chroma local para recuperación de normativa PBIP.
- Webhook local de WhatsApp para alertas y conversación con MIA.

## Pendientes técnicos recomendados

- Mover credenciales SMTP, llaves de reCAPTCHA, números autorizados, endpoint de WhatsApp, modelos de Ollama y rutas locales a variables de entorno.
- Evitar rutas absolutas como `CHROMA_PATH = "/home/julian/Naviera-Registro/scripts/chroma_db"` en código.
- Revisar que `requirements.txt` no incluya dependencias de entorno/GPU innecesarias para despliegues ligeros.
- Agregar pruebas para flujos críticos: registro, cambio obligatorio de contraseña, carga documental, comprobantes, entregables y webhooks MIA.
- Confirmar que `db.sqlite3`, `media/`, `staticfiles/` y bases Chroma locales no se versionen si no forman parte del despliegue.

## Documentación adicional

- `docs/README.md`
- `docs/CONTRIBUTING.md.md`
- `docs/LICENSE.MD.md`

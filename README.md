# Naviera-Registro

Aplicación web en Django para el registro de navieras, la carga documental de buques y el seguimiento inicial del expediente pre-servicio dentro del flujo PBIP de Global Maritime Protection.

## Qué hace hoy

- Registro público de navieras con validación por Google reCAPTCHA Enterprise.
- Creación automática de usuario Django y alta de la naviera asociada.
- Envío de contraseña temporal por correo al completar el registro.
- Inicio de sesión desde la misma pantalla de acceso/registro.
- Cambio obligatorio de contraseña en el primer acceso.
- Portal del cliente para registrar buques.
- Carga de documentos por buque para cotización y verificación documental.
- Carga de documentos administrativos generales de la naviera.
- Gestión de entregables como informe PBIP, factura y comprobante de pago.
- Disparo de análisis MIA sobre documentos cargados y envío de notificaciones por correo.

## Stack actual

- Python 3
- Django 5.2.2
- SQLite para entorno local
- HTML, CSS y JavaScript
- `django-recaptcha`
- Pillow

## Estructura del repositorio

```text
Naviera-Registro/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── media/
├── docs/
├── scripts/
│   └── poblar_chroma.py
├── naviera_registro/
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   ├── models.py
│   ├── migrations/
│   ├── static/
│   └── templates/
└── portal_cliente/
    ├── views.py
    ├── urls.py
    ├── agente_mia.py
    ├── migrations/
    └── templates/
```

## Modelos principales

### `Naviera`

- Relación `OneToOne` con `django.contrib.auth.models.User`.
- Guarda empresa, contacto principal y correo electrónico.

### `Buque`

- Relación `ForeignKey` con `Naviera`.
- Guarda nombre del buque y número OMI.

### `RequisitoBuque`

- Almacena documentos de pre-servicio.
- Soporta categorías `COTIZACION`, `DOCUMENTAL` y `ADMINISTRATIVO`.
- Puede quedar sin buque para documentos administrativos generales.

### `PuntoPBIP`

- Catálogo maestro de puntos de revisión PBIP.
- Se usa para mostrar la estructura del expediente en portal.

### `DocumentoEntregable`

- Guarda entregables finales por naviera o por buque.
- Tipos actuales: `INFORME_PBIP`, `FACTURA`, `COMPROBANTE_PAGO`.

### `AnalisisMIA`

- Relación `OneToOne` con `RequisitoBuque`.
- Conserva resumen técnico, alertas y metadatos del análisis automático.

## Rutas principales

- `/` y `/registro-naviera/`: alta pública de navieras.
- `/login/`: autenticación.
- `/portal/`: portal principal del cliente.
- `/portal/cambiar-password/`: cambio obligatorio de contraseña.
- `/portal/agregar-buque/`: alta de buques.
- `/portal/subir-archivo/<buque_id>/`: carga documental por buque.
- `/portal/subir-finanzas/`: carga documental administrativa.
- `/portal/subir-comprobante/`: carga de comprobante de pago.
- `/politica-privacidad/`: aviso de privacidad.
- `/configuracion-cookies/`: configuración de cookies.
- `/admin/`: administrador de Django.

## Flujo funcional

1. La naviera se registra desde el formulario público.
2. El sistema valida el captcha, crea el usuario y el registro de naviera.
3. Se envía una contraseña temporal por correo.
4. El usuario inicia sesión y debe cambiar su contraseña.
5. Desde el portal registra buques y sube documentos por expediente.
6. Cada carga puede disparar análisis MIA y acuse por correo.
7. El portal también muestra entregables y comprobantes asociados.

## Instalación local

```bash
git clone http://192.168.100.201:3000/yogit/Naviera-Registro.git
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
- Archivos estáticos: `naviera_registro/static/`
- Archivos subidos: `media/`

## Integraciones y dependencias pendientes de formalizar

El código actual usa componentes que no están reflejados por completo en [`requirements.txt`](/home/julian/Naviera-Registro/requirements.txt):

- `requests` para reCAPTCHA Enterprise, Ollama, WhatsApp y otras llamadas HTTP.
- `PyPDF2` para leer PDFs cargados por clientes.
- `langchain-chroma`, `langchain-ollama`, `langchain-community` y `langchain-text-splitters` para la parte de MIA/RAG.

Además, hay integraciones que hoy están configuradas directamente en código:

- Credenciales SMTP en [`naviera_registro/settings.py`](/home/julian/Naviera-Registro/naviera_registro/settings.py)
- Llaves y configuración de reCAPTCHA en [`naviera_registro/settings.py`](/home/julian/Naviera-Registro/naviera_registro/settings.py) y [`naviera_registro/views.py`](/home/julian/Naviera-Registro/naviera_registro/views.py)
- Endpoint de Ollama en [`portal_cliente/agente_mia.py`](/home/julian/Naviera-Registro/portal_cliente/agente_mia.py)
- Endpoint local de WhatsApp en [`portal_cliente/agente_mia.py`](/home/julian/Naviera-Registro/portal_cliente/agente_mia.py)

Para un despliegue real conviene mover todo esto a variables de entorno y separar dependencias obligatorias de dependencias opcionales de IA.

## Observaciones del estado actual

- El portal ya cubre más que el alta inicial: incluye documentos administrativos, comprobantes y entregables.
- El repositorio contiene datos locales y carpetas auxiliares como `db.sqlite3`, `media/`, `chroma_db/` y `venv/`.
- El script [`scripts/poblar_chroma.py`](/home/julian/Naviera-Registro/scripts/poblar_chroma.py) apunta a una base vectorial usada por MIA.

## Documentación adicional

- [`docs/README.md`](/home/julian/Naviera-Registro/docs/README.md)

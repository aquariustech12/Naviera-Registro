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

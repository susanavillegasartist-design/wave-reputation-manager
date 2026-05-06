# Wave Reputation Manager

Wave Reputation Manager es una aplicación web en Python para analizar reseñas negativas de Google, detectar posibles indicios de infracción de políticas y generar una reclamación profesional adaptada para solicitar la revisión o retirada de la reseña.

> Aviso legal: la herramienta no garantiza la retirada de reseñas; solo ayuda a preparar reclamaciones basadas en políticas. Verifica siempre las políticas oficiales vigentes antes de enviar cualquier solicitud.

## Funcionalidades

- Interfaz responsive con estilo corporativo tecnológico en negro, blanco, azul eléctrico y morado suave.
- Branding de Wave Music Business en home, registro e inicio de sesión.
- Registro, inicio de sesión y cierre de sesión con rutas `/register`, `/login` y `/logout`.
- Usuarios persistidos en SQLite con contraseña hasheada mediante PBKDF2; nunca se guarda texto plano.
- Plan activo visible en la interfaz. Todo usuario nuevo se crea con plan **Free**.
- Formulario de análisis con nombre del negocio, texto de la reseña, estrellas, usuario visible, fecha y contexto adicional.
- Bloqueo de análisis para visitantes no autenticados: pueden ver la home, pero deben registrarse o iniciar sesión para analizar.
- Historial persistente en SQLite asociado al usuario logueado.
- Estados de carga: “Analizando reseña…”, “Consultando políticas…” y “Generando reclamación…”.
- Motor local por categorías:
  - experiencia no genuina
  - conflicto de intereses
  - manipulación de valoración
  - contenido ofensivo
  - suplantación
  - información falsa o engañosa
  - datos personales
  - contenido irrelevante
- Archivo `google_policies.json` con descripción, ejemplos y argumentos por categoría.
- Resultado con viabilidad estimada, motivos detectados, políticas aplicables, evidencias recomendadas y reclamación adaptada.
- Botón para copiar la reclamación.
- Exportación de informe en PDF.
- Footer corporativo con web externa clicable, email `mailto:` y enlaces legales.
- Páginas legales base:
  - `/legal/aviso-legal`
  - `/legal/privacidad`
  - `/legal/cookies`
  - `/legal/terminos`
  - `/legal/reembolsos`
- Sección de precios con planes Free, Basic y Pro. Stripe o pasarela de pago todavía no está implementada.
- No genera respuestas públicas a reseñas ni promete eliminación garantizada.

## Planes

### Free — 0 €

- 1 análisis gratuito.
- Reclamación básica.
- Historial limitado.

### Basic — 9,99 €/mes

- 10 análisis al mes.
- Reclamaciones personalizadas.
- Historial, PDF y soporte por email.
- Botón preparado como placeholder en `/pricing` con aviso “Pago próximamente disponible”.

### Pro — 24,99 €/mes

- Análisis ilimitados.
- PDF profesional.
- Historial completo.
- Multi-negocio.
- Evidencias recomendadas.
- Soporte prioritario.
- Botón preparado como placeholder en `/pricing` con aviso “Pago próximamente disponible”.

## Requisitos

- Python 3.10 o superior.
- `pip`.

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn app:app --reload
```

Abre la aplicación en:

```text
http://127.0.0.1:8000
```

## Registro e inicio de sesión

1. Visita `http://127.0.0.1:8000/register`.
2. Crea una cuenta con email y contraseña de al menos 8 caracteres.
3. El sistema crea el usuario en SQLite con plan `free`.
4. Si ya tienes cuenta, entra desde `http://127.0.0.1:8000/login`.
5. Cierra sesión desde `/logout` o el botón “Cerrar sesión” de la interfaz.

La base de datos se crea automáticamente en `claims.db` al arrancar la aplicación. También se crean o migran automáticamente las tablas `users` y `claims`.

## Uso básico

1. Inicia sesión o regístrate.
2. Completa el formulario con los datos de la reseña.
3. Añade contexto adicional verificable si existe: reservas, tickets, capturas, comunicaciones o vínculos del usuario.
4. Pulsa **Analizar reseña**.
5. Revisa la viabilidad, motivos, políticas y evidencias recomendadas.
6. Copia la reclamación o exporta el informe en PDF.
7. Consulta el historial inferior para descargar informes anteriores de tu cuenta.

## Probar la aplicación

### Comprobación rápida de sintaxis

```bash
python -m py_compile app.py
```

### Comprobación de rutas registradas

```bash
python - <<'PY'
import app
paths = {route.path for route in app.app.routes}
for path in ['/', '/register', '/login', '/logout', '/pricing', '/legal/{slug}', '/analyze', '/history', '/claims/{claim_id}/pdf']:
    print(path, path in paths)
PY
```

### Prueba manual con servidor local

```bash
uvicorn app:app --reload
```

Después visita `http://127.0.0.1:8000`, crea una cuenta, envía un formulario de ejemplo y descarga el PDF generado desde el resultado o el historial.

### Ejemplo de reseña para probar señales

```text
Nunca fui a ese local, pero me han dicho que son unos estafadores. Si no me pagan publicaré más reseñas desde varias cuentas.
```

Este texto debería activar indicios de experiencia no genuina, contenido ofensivo y manipulación de valoración.

## Estructura del proyecto

```text
.
├── app.py                  # Aplicación FastAPI, auth, motor de análisis, SQLite y exportación PDF
├── google_policies.json    # Categorías locales de políticas, ejemplos y argumentos
├── requirements.txt        # Dependencias Python
├── static/
│   ├── app.js              # Interacción frontend, loading, copiar y refrescar historial
│   ├── logo-wave-music-business.png
│   └── styles.css          # Diseño responsive y tema visual
└── templates/
    ├── auth.html           # Registro e inicio de sesión
    ├── index.html          # Interfaz Jinja2 principal
    ├── legal.html          # Páginas legales dinámicas
    └── pricing.html        # Placeholder de pago futuro
```

## Base de datos

La aplicación crea automáticamente `claims.db` en el directorio del proyecto al arrancar. Este archivo contiene usuarios e historial local de análisis y no debe versionarse si almacena datos reales.

Tablas principales:

- `users`: `id`, `email`, `password_hash`, `plan`, `created_at`.
- `claims`: historial de reclamaciones con `user_id` para asociar cada análisis al usuario logueado.

## Seguridad

- Las contraseñas se guardan con hash PBKDF2-SHA256 y sal aleatoria.
- La cookie de sesión se firma con HMAC y se marca como `httponly`.
- Para producción, configura una clave propia:

```bash
export WAVE_SESSION_SECRET="cambia-esto-por-un-secreto-largo"
```

- No se ha implementado Stripe todavía; `/pricing` es solo una ruta placeholder.

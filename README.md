# Wave Reputation Manager

Wave Reputation Manager es una aplicación web en Python/FastAPI para analizar reseñas negativas de Google, detectar posibles indicios de infracción de políticas y generar una reclamación profesional adaptada para solicitar la revisión o retirada de la reseña.

> Aviso legal: la herramienta no garantiza la retirada de reseñas; solo ayuda a preparar reclamaciones basadas en políticas. Verifica siempre las políticas oficiales vigentes antes de enviar cualquier solicitud.

## Funcionalidades

- Registro, inicio de sesión y cierre de sesión con rutas `/register`, `/login` y `/logout`.
- Usuarios persistidos en SQLite con contraseña hasheada mediante PBKDF2; nunca se guarda texto plano.
- Todo usuario nuevo se crea con plan **Free**.
- Integración de suscripciones Stripe Checkout para Basic y Pro.
- Webhook Stripe con validación de firma para sincronizar estado de suscripción y plan activo.
- Límites por plan aplicados al análisis de reseñas.
- Formulario de análisis con nombre del negocio, texto de reseña, estrellas, usuario visible, fecha y contexto adicional.
- Historial persistente en SQLite asociado al usuario logueado.
- Exportación de informe en PDF.
- Footer corporativo con web externa clicable, email `mailto:` y enlaces legales.
- Páginas legales con datos de titularidad de Wave Music Business.
- Interfaz responsive con branding de Wave Music Business.

## Planes

### Free — 0 €

- 1 análisis gratuito.
- Reclamación básica.
- Historial limitado.
- Puede registrarse sin pagar.

### Basic — 9,99 €/mes

- 10 análisis al mes.
- Reclamaciones personalizadas.
- Historial.
- PDF.
- Soporte por email.

### Pro — 24,99 €/mes

- Análisis ilimitados.
- PDF profesional.
- Historial completo.
- Multi-negocio.
- Evidencias recomendadas.
- Soporte prioritario.

## Requisitos

- Python 3.10 o superior.
- `pip`.
- Cuenta de Stripe con productos/precios mensuales para Basic y Pro.

## Instalación de dependencias

```bash
pip install -r requirements.txt
```

## Configuración de `.env`

1. Copia el ejemplo:

```bash
cp .env.example .env
```

2. Rellena las variables locales en `.env`:

```dotenv
APP_BASE_URL=https://reputation.wavemusicbusiness.com
WAVE_SESSION_SECRET=change-me-to-a-long-random-secret
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_BASIC=
STRIPE_PRICE_ID_PRO=
```

Variables necesarias:

- `APP_BASE_URL`: URL pública de la app. En producción debe ser `https://reputation.wavemusicbusiness.com`.
- `WAVE_SESSION_SECRET`: secreto largo y aleatorio para firmar sesiones.
- `STRIPE_SECRET_KEY`: clave secreta de Stripe para servidor.
- `STRIPE_PUBLISHABLE_KEY`: clave publicable de Stripe, reservada para frontend si se necesita más adelante.
- `STRIPE_WEBHOOK_SECRET`: secreto de firma del endpoint webhook de Stripe.
- `STRIPE_PRICE_ID_BASIC`: Price ID mensual del plan Basic.
- `STRIPE_PRICE_ID_PRO`: Price ID mensual del plan Pro.

Nunca guardes claves reales en Git, README ni código fuente. `.env` está ignorado por Git.

## Ejecución local

```bash
uvicorn app:app --reload
```

Abre la aplicación en:

```text
http://127.0.0.1:8000
```

## Configurar productos y Price IDs en Stripe

1. En Stripe Dashboard, crea un producto para **Wave Reputation Manager Basic**.
2. Añade un precio recurrente mensual de **9,99 €**.
3. Copia el Price ID, con formato parecido a `price_...`, en `STRIPE_PRICE_ID_BASIC`.
4. Crea un producto para **Wave Reputation Manager Pro**.
5. Añade un precio recurrente mensual de **24,99 €**.
6. Copia su Price ID en `STRIPE_PRICE_ID_PRO`.
7. No configures todavía precios anuales: la aplicación solo espera cobro mensual.

## Configurar webhook en Stripe

Crea un endpoint de webhook apuntando a:

```text
https://reputation.wavemusicbusiness.com/stripe/webhook
```

Eventos necesarios:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

Después copia el signing secret del endpoint en `STRIPE_WEBHOOK_SECRET`.

## Rutas de billing

- `POST /billing/create-checkout-session/basic`: inicia Stripe Checkout para Basic con códigos promocionales de Stripe habilitados.
- `POST /billing/create-checkout-session/pro`: inicia Stripe Checkout para Pro con códigos promocionales de Stripe habilitados.
- `POST /stripe/webhook`: recibe y valida eventos Stripe.
- `GET /billing/success`: página de éxito tras checkout.
- `GET /billing/cancel`: página de cancelación.
- `GET /billing/portal`: placeholder preparado para un futuro portal de cliente.

## Base de datos

La aplicación crea automáticamente `claims.db` en el directorio del proyecto al arrancar. Este archivo contiene usuarios, suscripciones e historial local de análisis y no debe versionarse si almacena datos reales.

Tablas principales:

- `users`: `id`, `email`, `password_hash`, `plan`, `stripe_customer_id`, `stripe_subscription_id`, `subscription_status`, `current_period_end`, `updated_at`, `created_at`.
- `claims`: historial de reclamaciones con `user_id` para asociar cada análisis al usuario logueado.

Las migraciones ligeras añaden columnas nuevas si no existen, sin duplicarlas.

## Probar Free, Basic y Pro

### Free

1. Arranca la app local.
2. Registra un usuario nuevo.
3. Comprueba que aparece como plan `Free`.
4. Ejecuta un análisis de reseña.
5. Intenta ejecutar un segundo análisis en el mismo mes.
6. Debe aparecer: `Has alcanzado el límite de tu plan Free. Actualiza a Basic o Pro para continuar.`

### Basic

1. Configura `STRIPE_SECRET_KEY` y `STRIPE_PRICE_ID_BASIC`.
2. Inicia sesión y pulsa **Suscribirme a Basic** en `/pricing`.
3. Completa Checkout con una tarjeta de prueba de Stripe.
4. Verifica que Stripe envía `checkout.session.completed` y `customer.subscription.updated` al webhook.
5. Comprueba que el usuario queda en plan `Basic`, con estado `active` y límite de 10 análisis al mes.
6. Para una prueba sin pago real, puedes actualizar temporalmente la fila del usuario en SQLite a `plan='basic'` y comprobar que el límite mensual se aplica al análisis 11.

### Pro

1. Configura `STRIPE_SECRET_KEY` y `STRIPE_PRICE_ID_PRO`.
2. Inicia sesión y pulsa **Suscribirme a Pro** en `/pricing`.
3. Completa Checkout con una tarjeta de prueba.
4. Verifica en la interfaz que aparece `Pro`, estado de suscripción y límite `Ilimitados`.
5. Para una prueba sin pago real, puedes actualizar temporalmente la fila del usuario en SQLite a `plan='pro'` y comprobar que no se bloquean análisis por cantidad.

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
for path in [
    '/', '/register', '/login', '/logout', '/pricing', '/legal/{slug}',
    '/analyze', '/history', '/claims/{claim_id}/pdf',
    '/billing/create-checkout-session/{selected_plan}', '/stripe/webhook',
    '/billing/success', '/billing/cancel', '/billing/portal',
]:
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
├── app.py                       # Aplicación FastAPI, auth, Stripe, límites, SQLite, análisis y PDF
├── google_policies.json         # Categorías locales de políticas, ejemplos y argumentos
├── requirements.txt             # Dependencias Python
├── .env.example                 # Variables de entorno necesarias sin claves reales
├── static/
│   ├── app.js                   # Interacción frontend, loading, copiar, uso y refresco de historial
│   ├── logo-wave-music-business.png
│   └── styles.css               # Diseño responsive y tema visual
└── templates/
    ├── auth.html                # Registro e inicio de sesión
    ├── billing_status.html      # Éxito, cancelación y portal placeholder
    ├── index.html               # Interfaz Jinja2 principal
    ├── legal.html               # Páginas legales dinámicas
    └── pricing.html             # Planes y botones de Stripe Checkout
```

## Seguridad

- Las contraseñas se guardan con hash PBKDF2-SHA256 y sal aleatoria.
- La cookie de sesión se firma con HMAC y se marca como `httponly`.
- Las claves de Stripe solo se leen desde variables de entorno.
- El webhook valida la firma con `STRIPE_WEBHOOK_SECRET`.
- No se exponen `STRIPE_SECRET_KEY` ni `STRIPE_WEBHOOK_SECRET` en frontend.
- Los logs de billing no imprimen claves secretas.
- HTTPS, NGINX, systemd y configuración de servidor se gestionan fuera del código de la app.

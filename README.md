# Wave Reputation Manager

Wave Reputation Manager es una aplicación web en Python para analizar reseñas negativas de Google, detectar posibles indicios de infracción de políticas y generar una reclamación profesional adaptada para solicitar la revisión o retirada de la reseña.

> Aviso legal: la herramienta no garantiza la retirada de reseñas; solo ayuda a preparar reclamaciones basadas en políticas. Verifica siempre las políticas oficiales vigentes antes de enviar cualquier solicitud.

## Funcionalidades

- Interfaz responsive con estilo corporativo tecnológico en negro, blanco, azul eléctrico y morado suave.
- Formulario de análisis con nombre del negocio, texto de la reseña, estrellas, usuario visible, fecha y contexto adicional.
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
- Historial persistente en SQLite.
- Botón para copiar la reclamación.
- Exportación de informe en PDF.
- No genera respuestas públicas a reseñas ni promete eliminación garantizada.

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

## Uso básico

1. Completa el formulario con los datos de la reseña.
2. Añade contexto adicional verificable si existe: reservas, tickets, capturas, comunicaciones o vínculos del usuario.
3. Pulsa **Analizar reseña**.
4. Revisa la viabilidad, motivos, políticas y evidencias recomendadas.
5. Copia la reclamación o exporta el informe en PDF.
6. Consulta el historial inferior para descargar informes anteriores.

## Probar la aplicación

### Comprobación rápida de sintaxis

```bash
python -m py_compile app.py
```

### Prueba manual con servidor local

```bash
uvicorn app:app --reload
```

Después visita `http://127.0.0.1:8000`, envía un formulario de ejemplo y descarga el PDF generado desde el resultado o el historial.

### Ejemplo de reseña para probar señales

```text
Nunca fui a ese local, pero me han dicho que son unos estafadores. Si no me pagan publicaré más reseñas desde varias cuentas.
```

Este texto debería activar indicios de experiencia no genuina, contenido ofensivo y manipulación de valoración.

## Estructura del proyecto

```text
.
├── app.py                  # Aplicación FastAPI, motor de análisis, SQLite y exportación PDF
├── google_policies.json    # Categorías locales de políticas, ejemplos y argumentos
├── requirements.txt        # Dependencias Python
├── static/
│   ├── app.js              # Interacción frontend, loading, copiar y refrescar historial
│   └── styles.css          # Diseño responsive y tema visual
└── templates/
    └── index.html          # Interfaz Jinja2 principal
```

## Base de datos

La aplicación crea automáticamente `claims.db` en el directorio del proyecto al guardar la primera reclamación. Este archivo contiene el historial local de análisis y no debe versionarse si almacena datos reales.

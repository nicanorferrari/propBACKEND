# Reporte de Revisión del Backend (Urbano CRM SaaS)

## 1. 🚨 Errores Críticos y Problemas de Seguridad Detectados (Y Reparados)

- **Vulnerabilidad Crítica de Autenticación (REPARADO)**:
  - El endpoint `/login` en `routers/auth.py` **NO estaba verificando el hash de la contraseña** al iniciar sesión. Cualquier usuario podía entrar introduciendo cualquier contraseña si conocía el correo electrónico. Esto fue corregido inmediatamente implementando `verify_password`.
  - El endpoint `/register` guardaba las contraseñas en **texto plano** en la base de datos (`hashed_password=user_data.password`). Esto fue corregido inyectando `get_password_hash` en la creación del usuario.
- **Inconsistencias en "Soft Deletes"**:
  - Mientras que `routers/properties.py` implementa borrados suaves (cambiando el `status` a `"Deleted"`), otros módulos como el manejo del equipo (`routers/team.py`) realizan **Hard Deletes** (`db.delete(user)`). Eliminar físicamente registros que están atados como claves foráneas (como agentes asignados a propiedades o agendas) generará excepciones de integridad referencial o cascadas indeseadas.
- **Modelos Asíncronos vs Síncronos**:
  - Toda la API está definida usando `def` síncronos y depende del driver `psycopg2` (que también es síncrono). Dado que FastAPI corre sobre un Event Loop asíncrono nativo (ASGI), las llamadas masivas concurrentes a la DB podrían bloquear el Threadpool si no se migra a `async def` con `asyncpg`, o si no se maneja la concurrencia delegando al executor nativo de Starlette.

## 2. 🛠️ Áreas de Mejora y Rendimiento

- **Lógica de Autenticación Dispersa**:
  - La lógica de las firmas JWT vive en un macro archivo en la raíz `auth.py`, pero los endpoints en `routers/auth.py` repiten mucho código (creación manual de diccionarios OAuth2). Se debería refactorizar hacia un servicio de autenticación único.
- **Consultas N+1 y Cargas Perezosas (Lazy Loading)**:
  - En los listados (como `list_properties` o `list_team`), las sub-entidades (por ejemplo dependencias a `User` u `AgencyConfig`) sufren del problema de consultas N+1 porque SQLAlchemy hace *lazy loading* por defecto. Sería óptimo integrar `joinedload` en las _queries_ para resolver las tablas vinculadas en una sola tracción SQL.
- **Tolerancia a Fallos en APIs Externas**:
  - Se detectaron módulos de IA (`sync_property_ai`, `bot_engine`) y correos que asumen el "Happy Path" constante y fallan interrumpiendo el flujo (devolviendo `500 Server Error` en el frontend silenciosamente). Deben envolverse en gestores de colas como Celery, o como mínimo manejadores de tareas en background de FastAPI (`BackgroundTasks`) para que la API responda inmediatamente y la IA trabaje en las sombras.
- **Validaciones Pydantic Débiles**:
  - Los archivos `schemas.py` son extremadamente permisivos, abusando de tipos como `Any` o faltantes descriptivos en las opciones del modelo. Esto le da poco feedback al desarrollador sobre un mal `Request`.

## 3. ➕ Funciones Recomendadas por Agregar

- **Migraciones Formales (Alembic)**:
  - Actualmente el modelo parece basarse en validadores ad-hoc como `check_db_types.py` y `update_db_defaults.py`. Para entornos de producción SaaS (con múltiples Tenants), integrar **Alembic** organizará las versiones estructurales de base de datos de manera atómica para evitar caída de data con las actulizaciones de código.
- **Controladores de Cuotas (Rate Limiting) y Multi-Tenant Seguro**:
  - Es crítico añadir validaciones de inyección para evitar que un inquilino de agencia pida un listado con un ID que corresponde al de otra agencia, y añadir cuotas de peticiones a la API desde IPs externas para proteger las bases de datos de scraping de su inventario.
- **Centralizar Variables de Entorno y Configuraciones Globales**:
  - Reemplazar constantes dispersas como la duración de WebSockets, algoritmos JWT, links harcodeados en correos y umbrales por un archivo `settings.py` que valide con **Pydantic BaseSettings**, deteniendo la app al arrancar si el contenedor no inyecta las variables necesarias.

---

### Resumen de Acciones Tomadas:

✅ Brechas Críticas de Auth Bloqueadas.  
✅ Se implementó el Servidor Global y Manejador de WebSockets `socket_manager.py`.
✅ Se purgaron decoradores duplicados muertos.
✅ **Soft Delete Unificado**: Actualizado `models.User` con `is_active` y modificado el "Hard Delete" de Equipo en `routers/team.py` para usar Soft Delete al igual que Propiedades.
✅ **Eliminadas Consultas N+1 (list_properties)**: Aplicado `joinedload` en `list_properties` para pre-cargar la relación del Agente Asignado en una sola petición.
✅ **Tolerancia a fallos de IA**: Movido el bloqueante `sync_property_ai` a un módulo `background_tasks.py` usando dependencias de tipo `BackgroundTasks` de FastAPI, con aislamiento de sesión para proteger la disponibilidad al guardar/parchear propiedades.
✅ **Migraciones y Variables de Entorno Seguras**: Creado `settings.py` basado en `BaseSettings` (`pydantic-settings`) para centralizar las credenciales, e inicializado entorno formal de **Alembic** (`alembic init db_migrations`) y auto-generado primer esquema desde los modelos vigentes.  

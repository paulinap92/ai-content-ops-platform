# Monitor de datos · ensayo local 6G

La aplicación habitual (`app.py`) incluye la nueva navegación y el router protegido. El perfil de ensayo `src.core.monitor_local:create_app` inicia el mismo monitor/autenticación/proxy sin agentes LLM, base editorial, importador ni scheduler propios. Las demás pestañas editoriales requieren la aplicación habitual y su entorno anterior; el contenedor mínimo no las simula.

Arranque del conjunto: [instrucciones Windows/Docker/uv](https://github.com/paulinap92/canarias-dashboards/blob/test/centralizacion-6b/docs/centralizacion/41-local-6g-windows.md).

Variables privadas del servidor: `CC_LOCAL_6G=1`, `CC_MONITOR_API_ORIGIN=http://127.0.0.1:8067`, `CC_DATA_OPERATOR_TOKEN` (mínimo 32 caracteres), `EDITOR_TOKEN` (mínimo 32). El navegador usa la sesión habitual; nunca recibe el token operador. `CC_MONITOR_MANUAL_ENABLED=0` en AMBOS servidores. La opción manual solo encola en el worker existente, conserva bloqueo de propietario e idempotencia, no habilita horarios. Todos los propietarios locales permanecen bloqueados. No se ha ejecutado ningún job de fuente.

El refresco es bajo demanda, sin polling. Catálogo 65/75/70; fechas de observación y de materialización local separadas. Capacidad agregada en SQL; infraestructura anterior muestra fecha histórica y no se consulta Neon. No hay borrado. La compactación física raw sigue siendo candidata.

Pruebas nuevas/relevantes sin persistencia editorial:

```powershell
uv run --with pytest --with sqlalchemy --with fastapi --with httpx --with pydantic python -m pytest tests/test_data_monitor_6g.py tests/test_studio_navigation_contract.py -q
```

La suite completa de Studio y las capturas de navegador no se declaran aprobadas por estas pruebas limitadas. Informe completo en los documentos 40–43 de Observatorio.

# Trading-Agent

**Trading-Agent** ahora incluye un MVP ejecutable del **Normies Intelligence Agent** descrito en la documentación del repositorio. El agente escanea NFTs Normies, normaliza traits/señales de Canvas, calcula un `composite_score`, persiste resultados localmente en SQLite y permite listar o explicar rankings desde CLI.

> Seguridad: este MVP es analítico. No ejecuta trades ni mueve fondos.

## Funcionalidad implementada

- Cliente HTTP stdlib para `https://api.normies.art` con validación de IDs `0-9999`, timeout, backoff básico, throttling y cache local.
- Ingesta de `metadata`, `traits`, `pixels`, `canvas/info`, `canvas/diff`, `owner` e intento de `history/stats`.
- Persistencia local en SQLite mediante tabla `normies_signals`.
- Scoring inicial:
  - `rarity_score`: rareza inversa por frecuencia de traits dentro del rango escaneado.
  - `visual_density_score`: densidad de pixeles sobre canvas 40x40.
  - `canvas_activity_score`: personalización, nivel, action points y diff de pixeles.
  - `holder_activity_score`: presencia de owner.
  - `burn_momentum_score`: estadística global de burns cuando esté disponible.
- CLI usable para scan, ranking y explicación.
- Modo `--offline-demo` determinístico para demos y tests cuando la API no esté accesible desde el entorno.

## Instalación rápida

Requiere Python 3.10+ y no necesita dependencias externas en runtime.

```bash
python agent.py normies scan --start 0 --end 25 --offline-demo
python agent.py normies top --limit 10
python agent.py normies explain 0
```

Para usar la API real, omite `--offline-demo`:

```bash
python agent.py normies scan --start 0 --end 25
```

## Configuración

Copia `.env.example` si quieres documentar tus valores operativos y exporta las variables que necesites:

```bash
export NORMIES_BASE_URL=https://api.normies.art
export TRADING_AGENT_DB=data/trading_agent.sqlite3
export NORMIES_CACHE_DIR=.cache/normies
export NORMIES_TIMEOUT_SECONDS=10
export NORMIES_REQUESTS_PER_MINUTE=55
```

## Comandos CLI

### Escanear rango

```bash
python agent.py normies scan --start 0 --end 9999
```

Opciones útiles:

- `--offline-demo`: genera datos determinísticos sin red.
- `--db path/to/file.sqlite3`: usa otra base de datos.
- `--no-cache`: fuerza nuevas llamadas HTTP.

### Ver top Normies

```bash
python agent.py normies top --limit 25
python agent.py normies top --limit 25 --json
```

### Explicar un ranking

```bash
python agent.py normies explain 123
```

## Estructura principal

- `agent.py`: entrypoint CLI.
- `trading_agent/config.py`: configuración por entorno.
- `trading_agent/normies_client.py`: cliente HTTP y rate limiting.
- `trading_agent/normies_ingest.py`: pipeline de ingesta y modo demo.
- `trading_agent/normies_scoring.py`: scoring inicial.
- `trading_agent/normies_repository.py`: persistencia SQLite.
- `trading_agent/normies_cli.py`: comandos `scan`, `top` y `explain`.
- `schema.sql`: esquema SQL incluyendo `normies_signals` para Supabase/Postgres.
- `docs/normies-api-adaptation.md`: blueprint funcional original.

## Roadmap siguiente

- Añadir backtesting/rank history por snapshot.
- Integrar Supabase como backend opcional además de SQLite.
- Añadir dashboard web con cards e imagen SVG/PNG.
- Incorporar SIA social sobre wallets, builders y narrativa Normies.
- Endurecer validación contra schemas oficiales si la API publica OpenAPI.

## Licencia

Libre uso bajo los términos de la licencia [Apache 2.0](LICENSE).

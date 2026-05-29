# Adaptación de Trading-Agent a Normies API

## Objetivo

Adaptar el blueprint actual de **Trading-Agent** para participar en el hackathon de Normies construyendo un agente analítico de NFTs on-chain, no un bot de trading financiero tradicional.

La Normies API expone datos gratuitos y sin API key para 10,000 NFTs Normies: pixeles 40x40, traits, imágenes SVG/PNG, metadata, ownership, Canvas edits, burns e historial de transformaciones. Por eso, la adaptación recomendada es convertir el sistema en un **Normies Intelligence Agent** orientado a scoring, rareza, actividad de holders y señales de Canvas.

## Cambio de enfoque

| Trading-Agent actual | Adaptación Normies |
| --- | --- |
| Tokens financieros | Token IDs Normies `0-9999` |
| Precio, volumen, liquidez | Traits, pixel count, customization, owner, burns |
| Señales TA/on-chain | Señales visuales, ownership y actividad Canvas |
| Portfolio de posiciones | Watchlist / ranking de Normies |
| Risk engine financiero | Quality gates, rate limits y confidence scoring |
| SIA social para tokens AI | SIA social para wallets, holders y narrativa Normies |

## Arquitectura propuesta

```text
Normies API
   |
   v
normies_data_feed
   |-- /normie/{id}/metadata
   |-- /normie/{id}/traits
   |-- /normie/{id}/canvas/info
   |-- /normie/{id}/canvas/diff
   |-- /normie/{id}/owner
   |-- /history/*
   v
normalizador + cache + rate limiter
   v
normies_signals
   |-- rarity_score
   |-- visual_density_score
   |-- canvas_activity_score
   |-- holder_activity_score
   |-- burn_momentum_score
   |-- social_score opcional
   v
strategy/ranking
   v
outputs: dashboard, alerts, recomendaciones, submission de hackathon
```

## Módulos a crear

### 1. Cliente de API

Crear un módulo `trading_agent/normies_client.py` con:

- `base_url = "https://api.normies.art"` configurable por entorno.
- Métodos para `get_metadata(id)`, `get_traits(id)`, `get_pixels(id)`, `get_canvas_info(id)`, `get_canvas_diff(id)`, `get_owner(id)`, `get_history_stats()`.
- Validación estricta de IDs: enteros entre `0` y `9999`.
- Backoff para `429` y lectura de headers `X-RateLimit-*` cuando existan.
- Timeout corto por request y cache local para no recalcular el universo completo.

### 2. Modelo de señales Normies

Crear una tabla o vista equivalente a `token_signals`, pero por NFT:

```sql
CREATE TABLE normies_signals (
  token_id INT PRIMARY KEY CHECK (token_id BETWEEN 0 AND 9999),
  owner_address TEXT,
  type_trait TEXT,
  gender_trait TEXT,
  age_trait TEXT,
  hair_trait TEXT,
  facial_trait TEXT,
  eyes_trait TEXT,
  expression_trait TEXT,
  accessory_trait TEXT,
  pixel_count INT,
  customized BOOLEAN,
  level INT,
  action_points INT,
  added_pixels INT,
  removed_pixels INT,
  net_pixel_change INT,
  rarity_score NUMERIC(6,4),
  visual_density_score NUMERIC(6,4),
  canvas_activity_score NUMERIC(6,4),
  holder_activity_score NUMERIC(6,4),
  burn_momentum_score NUMERIC(6,4),
  composite_score NUMERIC(6,4),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3. Scoring inicial

Propuesta simple para una primera versión demostrable:

```text
composite_score =
  0.30 * rarity_score +
  0.20 * visual_density_score +
  0.20 * canvas_activity_score +
  0.15 * holder_activity_score +
  0.15 * burn_momentum_score
```

Definiciones sugeridas:

- `rarity_score`: inverso de frecuencia de traits en la colección.
- `visual_density_score`: normalización de `Pixel Count` o conteo directo de `1` en `/pixels`.
- `canvas_activity_score`: combinación de `customized`, `level`, `actionPoints`, `addedCount`, `removedCount` y número de versiones.
- `holder_activity_score`: señales por concentración o actividad de wallets si se combina `/holders/{address}` con muestras de owners.
- `burn_momentum_score`: derivado de `/history/stats`, `/history/burns` y `/history/burned-tokens`.

### 4. Reutilización de componentes existentes

- Mantener Supabase como persistencia principal, siguiendo el diseño del repositorio.
- Reutilizar la idea de `buckets` para clasificar Normies:
  - **A**: alta rareza + alta actividad Canvas.
  - **B**: rareza media o visualmente interesante.
  - **C**: baja actividad / baja convicción.
- Reutilizar `anomaly_flags` como `normies_anomaly_flags` para detectar metadata incompleta, tokens burned/unminted o cambios inesperados.
- Reinterpretar `circuit breakers` como protección operacional: pausar ingesta ante exceso de `429`, errores 5xx, inconsistencias de schema o datos incompletos.
- Adaptar SIA para escanear narrativa social sobre Normies, wallets activas, builders del hackathon y actividad alrededor de Canvas.

## MVP para hackathon

### Entregable recomendado

Construir un **Normies Alpha Dashboard / Agent** que permita:

1. Escanear los 10,000 Normies respetando el límite de rate limit.
2. Calcular rareza y señales de Canvas.
3. Mostrar ranking por composite score.
4. Abrir detalle por Normie con imagen SVG/PNG, traits, owner, historial de versiones y canvas diff.
5. Generar explicación tipo agente: “este Normie rankea alto porque combina X trait raro, alta densidad visual y actividad reciente de Canvas”.

### Plan de implementación por etapas

1. **Etapa 1 — Ingesta mínima**
   - Crear cliente HTTP.
   - Descargar `metadata`, `traits`, `canvas/info` y `owner` para un rango configurable de IDs.
   - Persistir en `normies_signals`.

2. **Etapa 2 — Scoring**
   - Calcular frecuencia de traits.
   - Calcular density score desde `Pixel Count` o `/pixels`.
   - Calcular activity score desde Canvas endpoints.

3. **Etapa 3 — Interfaz o salida usable**
   - CLI: `python agent.py normies scan --start 0 --end 9999`.
   - CLI: `python agent.py normies top --limit 25`.
   - Dashboard opcional con cards e imágenes.

4. **Etapa 4 — Inteligencia social opcional**
   - Adaptar SIA para X/Farcaster con keywords `Normies`, `NormiesCanvas`, contract address y wallets relevantes.
   - Combinar social score con composite score sólo como señal secundaria.

## Consideraciones de API

- Base URL: `https://api.normies.art`.
- No requiere API key.
- Rango de token IDs: `0-9999`.
- Rate limit publicado: 60 requests/minuto/IP.
- Los endpoints composited (`/pixels`, `/image.svg`, `/image.png`, `/metadata`) ya incluyen personalizaciones Canvas.
- Para datos pre-transformación, usar `/original/*`.
- Para historial y burns, usar `/history/*` con paginación y límite máximo de 100 cuando aplique.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
| --- | --- |
| Rate limit al escanear 10,000 IDs | Cola con throttle de 50-55 rpm, cache incremental y reintentos con backoff |
| Tokens burned/unminted con `404` | Guardar estado `unavailable` sin tratarlo como error fatal |
| Cambios de schema | Validación con Pydantic o dataclasses y alertas de incompatibilidad |
| Latencia para scan completo | Jobs por lotes y actualización diferencial |
| Scoring subjetivo | Mostrar explicación y componentes del score, no sólo ranking final |

## Primeros archivos a implementar

```text
agent.py
trading_agent/
  __init__.py
  config.py
  normies_client.py
  normies_ingest.py
  normies_scoring.py
  normies_repository.py
  normies_cli.py
schema.sql
```

## Criterio de éxito

La adaptación está lista para una demo cuando podamos ejecutar un scan parcial, persistir señales, listar los top Normies por score y explicar cada ranking con datos de la API.

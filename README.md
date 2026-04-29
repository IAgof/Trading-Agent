# Trading-Agent

**Trading-Agent** es un repositorio que define una arquitectura de agente automático de trading para mercados financieros. Actualmente el proyecto está orientado a **documentación de estrategia y operación** (no incluye todavía implementación ejecutable completa del bot), lo cual lo hace útil para diseño, auditoría y evolución por etapas.

## Estado actual del repositorio

- ✅ Documentación estratégica extensa (`ai-agent-economy-trader.MD`, `siaMD`).
- ⚠️ No hay implementación Python funcional del `agent.py` dentro del repositorio actual.
- ⚠️ No existe `requirements.txt` en la raíz (la instalación rápida previa asumía ese archivo).

> Recomendación: tratar este repo hoy como **spec/blueprint** y no como ejecutable listo para producción.

## Mejoras aplicadas en esta revisión

1. **Corrección de expectativas**: se aclara el estado real del proyecto para evitar instrucciones de uso que fallen.
2. **Roadmap técnico priorizado**: se propone una ruta de implementación incremental.
3. **Checklist de calidad**: se añade un baseline de seguridad/operación antes de operar con fondos reales.

## Roadmap sugerido (prioridad alta → baja)

### Fase 1 — Base ejecutable mínima

- Crear estructura Python:
  - `agent.py` (entrypoint)
  - `trading_agent/config.py`
  - `trading_agent/data_feed.py`
  - `trading_agent/strategy.py`
  - `trading_agent/execution.py`
  - `trading_agent/risk.py`
- Añadir `requirements.txt` + `.env.example`.
- Definir modo `paper/simulation` por defecto.

### Fase 2 — Persistencia y observabilidad

- Integrar Supabase como fuente única de verdad (siguiendo el diseño ya documentado).
- Estandarizar logs estructurados (`json`) con niveles (`INFO/WARN/ERROR`).
- Añadir métricas mínimas: PnL, drawdown, win-rate, exposición por token.

### Fase 3 — Testing y seguridad operativa

- Pruebas unitarias para scoring, thresholds, circuit breakers y DRR.
- Pruebas de integración en modo simulado.
- Reglas de seguridad:
  - límites por posición,
  - límites por día,
  - kill switch manual,
  - validación de llaves/API por entorno.

### Fase 4 — Entorno de producción

- Pipeline CI (lint + tests + type-check).
- Backtesting reproducible con datasets versionados.
- Deploy con scheduler y alertas (fallos de conexión, DRR activado, CB activo).

## Checklist mínimo antes de operar con dinero real

- [ ] Estrategia validada en backtest y forward test.
- [ ] Circuit breakers probados con escenarios extremos.
- [ ] Gestión de riesgo configurada y revisada.
- [ ] Modo simulación ejecutado de forma estable por varios ciclos.
- [ ] Monitoreo y alertas operativos 24/7.

## Estructura documental actual

- `ai-agent-economy-trader.MD`: arquitectura principal del trader, capas y reglas.
- `siaMD`: especificación del Social Intelligence Agent (SIA).

## Licencia

Libre uso bajo los términos de la licencia [Apache 2.0](LICENSE).

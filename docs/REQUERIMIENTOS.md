# Diario de Trading Local — Documento previo de requerimientos

Estado: borrador v0.1 (2026-11-01). Sin decisiones de arquitectura todavía.
Base: barrido de mercado hecho por un agente explorador (Haiku). Los datos marcados **[NV]** no están verificados en fuente oficial.

## 1. Objetivo y alcance

Diario de trading que corre **solo en local** (Windows 11), sin nube ni cuentas, para registrar la operativa y medir el progreso.

- Instrumentos: **Oro** (XAUUSD CFD / futuros GC, MGC), **S&P 500** (ES, MES, SPX CFD), **Nasdaq 100** (NQ, MNQ, NDX CFD).
- Un único usuario.
- Fuera de alcance: forex, cripto, opciones, social, IA, app móvil, sync en vivo con API de bróker, funciones de prop firms.

## 2. Referencias del mercado

| Producto | Qué se toma | Qué se descarta |
|---|---|---|
| TradeZella | Etiquetado por setup/sesión/TF, calendario de P&L, revisión | Nube, suscripción, IA, replay de pago |
| Tradervue | Estadísticas clásicas, vista de trade con notas | Compartir público, nube |
| Edgewonk | Psicología (estado emocional, tilt), checklists, métricas (Gain to Pain, Calmar) | Licencia de pago |
| TraderSync / Trademetria / Chartlog | Importación por CSV, marcas de entrada/salida sobre gráfico | Sync con brokers |
| TradeTally, janzofx/Trading_Journal (open source) | Referencia de modelo de datos e importadores | Licencia y soporte de futuros por confirmar **[NV]** |

Quejas recurrentes del sector que el producto debe evitar: importaciones que pierden trades o calculan mal el P&L, y dependencia de un proveedor. Consecuencia: la **fiabilidad de la importación y la reconciliación** pesan más que las funciones vistosas.

## 3. Requerimientos funcionales

### 3.1 MVP (imprescindible)

| ID | Requerimiento |
|---|---|
| F-01 | Registro manual de operaciones (instrumento, lado, cantidad, entrada, salida, stop inicial, objetivo, comisiones, fechas/horas). |
| F-02 | Importación de CSV/HTML: MT5 (informe HTML), NinjaTrader 8 (CSV de ejecuciones), Tradovate (CSV) y un **CSV genérico propio** documentado. |
| F-03 | Catálogo de instrumentos con tick size, valor del tick y multiplicador editables (ver §5). |
| F-04 | Cálculo de P&L en puntos, ticks y dinero, bruto y neto de comisiones/swaps. |
| F-05 | R-múltiplo por operación a partir del stop inicial. |
| F-06 | Agrupación de ejecuciones parciales en una operación (entradas/salidas escalonadas). |
| F-07 | Campos pre-trade y post-trade (ver §6) y etiquetas de setup, sesión y error. |
| F-08 | Adjuntar capturas de gráfico (archivos locales). |
| F-09 | Panel de métricas (ver §4) con filtros por instrumento, periodo, setup, sesión, día/hora. |
| F-10 | Curva de capital y drawdown; calendario de P&L diario. |
| F-11 | Detección de duplicados al importar y vista de reconciliación (importados vs. esperados). |
| F-12 | Exportación completa (CSV/JSON) y copia de seguridad/restauración con un clic. |

### 3.2 Deseable (fase 2)

MAE/MFE (requiere datos intra-trade o precios de extremo introducidos a mano), checklist pre-trade configurable, estado emocional/tilt, análisis por sesión (Asia, Londres, NY RTH/Globex), plantilla de revisión semanal y mensual, enlace a TradingView por operación, mapa de contratos de futuros con rollover (MNQZ6 → MNQ), Monte Carlo simple, objetivos y reglas personales (máx. pérdida diaria, nº máx. de trades) con alerta de incumplimiento.

### 3.3 Prescindible

Sync en vivo con brokers, rankings sociales, IA, multiusuario, móvil, compartir.

## 4. Métricas a calcular

Cada métrica debe mostrar su fórmula y el tamaño de muestra (n) en la interfaz.

| Métrica | Fórmula |
|---|---|
| Win rate | ganadoras / total |
| Profit factor | ganancias brutas / pérdidas brutas |
| Expectancy (en R y en dinero) | WR × ganancia media − (1−WR) × pérdida media |
| Payoff ratio | ganancia media / pérdida media |
| R medio, mejor/peor R | del R-múltiplo por operación |
| Max drawdown | mayor caída desde pico corrido (valor y %) |
| Racha ganadora/perdedora máxima | consecutivas |
| Sharpe / Sortino / Calmar | declarar rf, MAR y anualización; Calmar = retorno anualizado / max DD |
| Gain to Pain | retorno total / suma absoluta de pérdidas |
| MAE / MFE, profit efficiency | fase 2: salida / MFE |
| Tiempo medio en operación | por ganadoras y perdedoras |

Convención a fijar: las fuentes difieren en suma vs. media (edge ratio, Calmar). Se documenta la elegida.

## 5. Particularidades de los instrumentos

| Instrumento | Dato de partida | Estado |
|---|---|---|
| ES / MES | $50 / $5 por punto; tick 0.25 | **[NV]** CME |
| NQ / MNQ | $20 / $2 por punto; tick 0.25 | **[NV]** CME (una fuente da $1.25 por tick en MNQ, que coincide con $0.50 a 0.25 pts solo si hay error; verificar) |
| GC / MGC | 100 oz / 10 oz; MGC tick $0.10 = $1 | Parcial |
| XAUUSD CFD | Lote estándar 100 oz; varía por bróker | Leer especificación del símbolo en MT5 |

Requisitos derivados:

- Valores por defecto precargados pero **editables y versionados** (un cambio no recalcula el pasado sin avisar).
- Distinguir futuros (comisión por contrato y lado) de CFD (spread, comisión, swap; triple swap habitual en miércoles **[NV]**).
- Tiempos guardados en **UTC**, con zona del origen indicada en cada importación; mostrar en hora de NY y hora local.
- Sesiones configurables (Asia, Londres, NY Globex/RTH) para etiquetar cada operación automáticamente.
- Rollover trimestral (H, M, U, Z): agrupar símbolos de contrato dentro de un instrumento lógico.
- Moneda de la cuenta configurable (conversión si no es USD, por decidir).

## 6. Campos del diario

- **Pre-trade:** setup, contexto (tendencia en TF superior, sesión), riesgo previsto (stop, objetivo, R esperado), checklist, estado emocional.
- **Post-trade:** resultado en R, ejecución vs. plan (A/B/C), error principal (lista cerrada), captura, lección en una frase.
- **Etiquetas:** empezar con 3-4 categorías (setup, sesión, TF) y ampliar tras ~50 trades.
- **Revisión periódica:** errores repetidos, setups ganadores, disparadores emocionales, métricas por instrumento y sesión.

## 7. Requerimientos no funcionales

| ID | Requerimiento |
|---|---|
| N-01 | 100 % local; sin telemetría ni llamadas de red en el uso normal. |
| N-02 | Datos en formato abierto y portable (base local de un solo archivo + export CSV/JSON). |
| N-03 | Arranque con un comando o acceso directo en Windows 11; sin Docker obligatorio. |
| N-04 | Copias de seguridad automáticas versionadas, destino elegido por el usuario. |
| N-05 | No almacenar credenciales de brokers; anonimizar números de cuenta al importar. |
| N-06 | Cálculos financieros con precisión decimal (sin errores de coma flotante en dinero). |
| N-07 | Pruebas automáticas de métricas e importadores con archivos de muestra reales. |
| N-08 | Rendimiento fluido hasta decenas de miles de operaciones. |
| N-09 | Interfaz en español; modelo de datos preparado para otro idioma. |
| N-10 | Migraciones de esquema versionadas para no perder datos al actualizar. |

## 8. Riesgos

| Riesgo | Mitigación |
|---|---|
| Importaciones incorrectas | Archivos de muestra reales, reconciliación (F-11), pruebas (N-07) |
| Desfase horario (DST, zona del broker/NT8) | UTC + zona declarada por importación |
| Valores de contrato erróneos | Verificar en CME antes de fijar por defecto |
| Pérdida de datos | N-04, F-12 |
| Alcance creciente | MVP cerrado; fase 2 solo tras usar el MVP |

## 9. Preguntas abiertas para el usuario

1. ¿Qué plataforma/bróker usas hoy (MT5, NinjaTrader, Tradovate, otro)? Define los importadores del MVP.
2. ¿Operas futuros, CFD o ambos en cada instrumento?
3. ¿Moneda de la cuenta y comisiones habituales?
4. ¿Tienes un historial para importar? Necesito 1-2 exportaciones reales (anonimizadas) para construir los importadores.
5. ¿Prefieres abrir la app en el navegador local o como ventana de escritorio?
6. ¿Usas una cuenta de fondeo o propia (afecta a reglas de pérdida máxima)?
7. ¿Registrarás emociones y checklist en cada trade o solo en revisión?

## 10. Pendientes de verificación

Especificaciones oficiales CME de MNQ/MES/MGC; formato CSV exacto de Tradovate; licencia y soporte de futuros de TradeTally; swaps del bróker del usuario.

## 11. Siguiente paso

Responder §9 → decidir stack y arquitectura → plan de MVP por hitos (modelo de datos + importadores + métricas primero, interfaz después).

# Hoja de ruta (2026-11-01)

Base: segundo barrido del agente explorador. Las fuentes son sobre todo de fabricantes; lo marcado [NV] no está verificado de forma independiente.

## Etapa 1 — Registro y seguimiento (hecha en esta versión)
- Varias cuentas (real, demo, fondeo), con depósitos y retiros aparte del P&L. El drawdown y el rendimiento no se ven alterados por los flujos de caja.
- Informes semanales y mensuales con comparación con el periodo anterior, cumplimiento del plan y revisión escrita (qué salió bien, qué mejorar, objetivo de conducta).
- Varias capturas por operación (archivos o pegar con Ctrl+V), guardadas en `datos/capturas/`.
- Análisis descriptivo por hora, día, tamaño y setup, con intervalo de Wilson y aviso de muestra pequeña (n < 20).
- Exportación de dataset limpio (CSV, una fila por operación) y copia de seguridad.

## Etapa 2 — Optimización estadística (cuando haya datos suficientes)
Orden recomendado, de menor a mayor riesgo de autoengaño:
1. Bootstrap de la expectancy en R (intervalo de confianza). Pregunta: ¿es positiva de verdad?
2. Corrección por múltiples pruebas (Holm/Bonferroni) o contracción hacia la media global al segmentar por hora. Con 24 franjas hay ~70 % de probabilidad de que una parezca significativa solo por azar.
3. Monte Carlo de la curva y riesgo de ruina; fracción de Kelly (¼–½) solo con muestra grande.
4. MAE/MFE: requiere precio intra-operación. Se puede pedir al EA/script de MT5 que lo exporte. [NV: heurística del percentil 80 de MAE]
5. Validación fuera de muestra (walk-forward) antes de cambiar horarios o tamaños.
Tamaño de muestra orientativo (cálculo): ±10 % en el win rate al 95 % pide unas 96 operaciones; estimar la expectancy con error de 0,1 R pide unas 384.

## Etapa 3 — IA sobre capturas y notas
- Usar el modelo para extraer campos de la captura (hora, entrada, stop) y contrastarlos con el registro de MT5, no para juzgar el setup. No hay estudios que validen la detección de errores de ejecución con capturas. [NV]
- Fuga de información: MAE/MFE, notas escritas tras cerrar y comisiones no pueden ser features. Las etiquetas "error" deben definirse por escrito antes de etiquetar. Si cambia el plan, versionar las reglas.
- Con pocos cientos de operaciones, modelos simples y validación con purga; separar oro e índices.
- Las capturas pueden mostrar datos de cuenta: tratarlas como sensibles y valorar un modelo local.

## Pendiente de la etapa 1
- **Importador contra un informe real de Exness.** No existe especificación oficial verificable del HTML de MT5. La tabla Deals (13 columnas: Time, Deal, Symbol, Type, Direction, Volume, Price, Order, Commission, Swap, Profit, Balance, Comment) no trae ID de posición; el orden de columnas de Positions que usa el importador es una suposición. Filas `Balance`/`Credit` = depósitos/retiros, aún no se convierten en movimientos. Localizar columnas por cabecera ES/EN en lugar de por posición.
- **Hora del servidor de Exness: sin confirmar.** Cada cuenta tiene modo de hora de servidor: UTC, cierre NY (GMT+2 invierno / GMT+3 verano de EE.UU.) o desfase fijo. Por defecto es fijo con desfase 0; hay que fijarlo tras comprobar un informe real (Ctrl+M en MT5 muestra la hora del servidor). El análisis por hora y el dataset se muestran en hora de Colombia (UTC-5). Los periodos y el calendario siguen usando la fecha de salida del servidor.
- Sesiones (Asia/Londres/NY) y killzones: sin consenso entre fuentes; no se implementan hasta definir las propias.
- Valores de contrato: ES $50, MES $5, NQ $20, MNQ $2 por punto; GC 100 oz, MGC 10 oz (tick $0,10). Coinciden en varias fuentes secundarias, pero cmegroup.com no respondió: sin verificar en CME. No afectan a CFD, cuyo tamaño de contrato depende del bróker.
- TWR por cuenta (Rk = V⁻k / V⁺k−1 − 1, encadenado) si hay muchos flujos de caja.

## Hecho en v0.3.0
- Retorno TWR y ganancia absoluta (separados de depósitos y retiros), en Resumen y en la pestaña Track record.
- Track record íntegro: siempre desde el primer movimiento u operación, con registro de importaciones y huella SHA-256 de cada archivo.
- Cuentas cent (USC): se guardan en su unidad y el análisis se normaliza a USD.

## Siguiente (barrido de herramientas, ordenado por impacto/esfuerzo)
Monte Carlo y riesgo de ruina; checklist previo y adherencia al plan; costes netos con spread estimado; histograma de R; curva underwater; drawdown de equity flotante y alertas (requiere datos que el HTML no trae); MAE/MFE (requiere precios intra-operación).


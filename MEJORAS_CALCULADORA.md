# ValuationSuite USIL — Debilidades detectadas con los 5 casos y mejoras aplicadas

Fuente de cada número: `python backtest.py` (informe completo en `INFORME_BACKTEST.md`).
Los casos: F1 FrioLog, F2 Smart Recovery, F3 Pantalla RH, F4 Ovos Terra, F5 Humanitas.

## 1. Qué cambia para el usuario (resumen)

| Caso | Resultado v2.0 | Resultado v3.0 (sin VT, tasa en Gs) | ¿Cambia la conclusión? |
|---|---|---|---|
| F1 FrioLog | VAN Gs 7.457 M · TIR 116 % | VAN Gs 2.224 M · TIR 90 % | No: sigue positivo, pero 70 % menor |
| F2 Smart Recovery | VAN Gs 104,4 M · TIR 106 % | VAN Gs 26,3 M · TIR 74 % | No, pero con 6 alertas (incl. EBIT/FCF incoherente) |
| **F3 Pantalla RH** | **VAN +USD 252.034** | **VAN −USD 98.244** · TIR 10,5 % < WACC 15,6 % | **Sí: positivo → negativo** |
| F4 Ovos Terra | VAN Gs 101,1 M · P(VAN<0) 0 % | VAN Gs 10,5 M · escenario pesimista −Gs 108 M | Pasa de «aprobado» a «mixto» (VAN positivo pero frágil) |
| F5 Humanitas* | 4 escenarios con VAN > 0 | siguen > 0, pero C y D con VAN casi nulo | No; alerta de horizontes distintos |

\* Humanitas usa FCF₁ y g∞ inferidos (el fixture no los trae).

## 2. Debilidades → mejoras

| # | Debilidad (evidencia en los casos) | Mejora implementada | Dónde |
|---|---|---|---|
| 1 | **Perpetuidad siempre activa.** El VT pesa 44–66 % del valor. F3 pasa de +252 mil a −79 mil USD sin VT. | VT **opcional y apagado por defecto** (sin VT / desecho / perpetuidad justificada). Se muestran siempre VAN y TIR con y sin VT y el **peso del VT**. La perpetuidad usa FCF normalizado (reinversión ≥ depreciación) y exige justificar la continuidad. | `Project.terminal_mode`, `valuate`, alertas V04, V09 |
| 2 | **TIR inflada** (F1 116 %, F2 106 %): incluía el VT como caja del año N y descartaba como «N/A» las TIR > 200 %. | TIR **principal sin VT**; con VT queda como secundaria y rotulada; se agrega **TIR modificada** e **índice de rentabilidad**. Ya no se oculta una TIR extrema: se muestra y se alerta. | `Metrics`, V02 |
| 3 | **Desajuste de moneda.** Ke en USD aplicado a flujos en Gs; Ke < Kd en F1, F2 y F3. El WACC corregido sube +0,53 a +1,12 pp. | **WACC en la moneda del flujo**: `Ke_Gs = (1+Ke_USD)(1+π_Gs)/(1+π_USD) − 1`, Kd después de IRE, pesos E/V y D/V, prima por tamaño opcional y desglose completo en pantalla y reporte. | `wacc_breakdown`, V01, V07, V17 |
| 4 | **Monte Carlo ciego al riesgo.** Solo variaba g, WACC y CAPEX: P(VAN<0) = 0 % en Ovos Terra mientras su escenario pesimista tiene FCF −Gs 15,8 M/año. | MC sobre **precio, volumen, costo variable unitario, costos fijos, CAPEX y WACC** (triangular o normal truncada, correlaciones opcionales, semilla fija), con P5/P50/P95, CVaR5, posición del caso base y **escenario pesimista determinístico siempre visible**. Alerta aunque P(VAN<0) sea baja. | `run_monte_carlo`, V11 |
| 5 | **Flujo mal construido.** El puente de un año se extrapolaba a g constante; con EBIT negativo la v2.0 daba un crédito fiscal ficticio; el CAPEX de mantenimiento (250 M) era menor que la depreciación (1.500 M) y se perpetuaba. F2: FCF/EBIT = 0,027. F4: impuesto calculado antes de la reposición. | **Motor de flujo desagregado** por año: ingresos − costos = EBITDA − depreciación = EBIT − IRE (solo si EBIT > 0) + depreciación − Δcapital de trabajo − CAPEX de reposición, con rampa, recupero del capital de trabajo y desecho neto de IRE. | `project_flows`, V06 |
| 6 | **Sin validaciones**: aceptaba Ke < Kd, TIR > 100 %, g de 15 % con perpetuidad, horizontes distintos (Humanitas 5 vs 8 años). | 17 alertas con severidad (V01–V17), todas probadas con un input diseñado para dispararlas. | `run_validations`, `compare_scenarios` |
| 7 | **Presentación y trazabilidad.** WACC mostrado 14,53 % vs 14,529866 % interno; Humanitas con WACC distinto y el reporte no imprime los inputs que lo explican. | Tasas con la precisión con que se usan (4 decimales); el reporte imprime el desglose del WACC; el WACC es constante entre escenarios salvo cambio de inputs (probado); comparador de escenarios con alerta. | `fmt_rate`, `compare_scenarios` |
| 8 | **«DICTAMEN: APROBADO» automático.** F1–F4 lo recibían con un MC que no detectaba riesgo. | «**Indicadores favorables bajo los supuestos cargados**» (o mixtos/desfavorables) + alertas activas + **variable crítica** con el valor que hace VAN = 0. | `read_results`, `breakeven` |
| 9 | *(Hallazgo propio)* Los fixtures no se podían comparar entre sí: horizontes distintos, sin valor equivalente. | **Valor anual equivalente (EAA)** para comparar proyectos de vida distinta. | `equivalent_annual_annuity`, V08 |
| 10 | *(Hallazgo propio)* El Monte Carlo no tenía semilla: dos corridas del mismo proyecto daban resultados distintos (F2 tiene dos). | Semilla fija opcional; mismo resultado = mismo reporte. | `MCSpec.seed` |
| 11 | *(Hallazgo propio)* La demo por defecto tenía EBIT negativo y D+E ≠ CAPEX. | Demo reequilibrada (EBIT positivo, D+E = CAPEX). Etiqueta «IRACIS» (derogada) → IRE. | `app.py` |

**Enfoque didáctico.** El propósito principal de la calculadora es enseñar: cada componente de la tasa (Rf, βU, βL, ERP, CRP, prima por tamaño, Ke en USD, π Gs / π USD, Ke en la moneda del flujo, Kd, pesos, WACC), cada línea del flujo, cada fila del punto de equilibrio y cada indicador muestra su definición, su fórmula, cómo interpretarlo y su base teórica (`glosario.py`). Hay además un glosario completo dentro de la app.

## 3. Lectura con criterios CFA (presupuesto de capital y valoración)

Contraste de la calculadora con los principios habituales del currículo CFA. Es una lectura de principios, **no una auditoría ni una certificación del CFA Institute**; conviene validar los umbrales contra el material vigente.

| Principio | Estado v2.0 | Estado v3.0 |
|---|---|---|
| El VAN es el criterio principal; la TIR es secundaria y puede dar señales falsas | La TIR (con VT) dominaba el mensaje | VAN decide; la TIR principal es sin VT; TIRM; el VAN prevalece en la lectura (probado) |
| TIR no única con flujos no convencionales | No se detectaba | Alerta V14 (más de un cambio de signo) |
| Payback: ignora valor del dinero y flujos posteriores | Se mostraba como indicador | Se muestra como secundario; también descontado |
| Proyectos mutuamente excluyentes con vidas distintas | No se podía comparar | EAA + alerta V08 |
| WACC con estructura **objetivo** a valores de mercado; Kd = rendimiento de mercado actual | Sin guía; Kd libre | Ayudas en cada input; alerta V17 si Kd < Rf en la moneda del flujo |
| Coherencia moneda/inflación entre flujos y tasa | Ausente | Conversión por diferencial de inflación; V07 y V15 |
| Valor terminal: Gordon con FCF normalizado y g ≤ crecimiento nominal de largo plazo | g∞ libre, sin reinversión | FCF normalizado; g∞ ≤ WACC − 2 pp; alerta V16 |
| Flujos incrementales (sin costos hundidos ni financieros; con costo de oportunidad) | Sin mención | Textos de ayuda y nota en el reporte (el modelo **no puede verificarlo**) |
| Análisis de sensibilidad, escenarios y simulación | Sensibilidad WACC×g y MC limitado | Sensibilidad, escenario pesimista, MC sobre drivers, punto de equilibrio |
| Estándares de conducta: separar hechos de opiniones, informar supuestos y limitaciones | Reporte sin sección de limitaciones | Sección «Supuestos y limitaciones» en TXT y PDF |

## 4. Lo que NO está resuelto o no se puede afirmar

- **Humanitas** se evaluó con FCF₁ y g∞ **inferidos** de los outputs; no es una reproducción verificada. Que su WACC cambiara con el horizonte **no se puede explicar** con el código: el reporte v2.0 no guardaba los inputs.
- El **Monte Carlo v2.0 no se reproduce** dentro de ±0,5 % (rangos y semilla desconocidos). Las cifras de P(VAN<0) corregidas de F1–F3 y F5 usan rangos **supuestos** y solo ven el nivel del FCF, no precio ni volumen; solo F4 corre el motor completo. El 73 % de F4 depende de esos rangos asumidos.
- Las inflaciones (3,5 % / 2,5 %) y los pesos E/V–D/V de F1 y F2 son **supuestos o derivaciones**, rotulados en el informe.
- El **escenario pesimista por defecto** (todos los drivers en su extremo a la vez) es severo: casi cualquier proyecto con margen ajustado mostrará la alerta V11. Se puede cambiar a «P10 adverso» en la barra lateral.
- Los umbrales de las alertas (p. ej. «inversión significativa» = CAPEX ≥ 25 % de las ventas; FCF/EBIT entre 0,30 y 1,50) son criterios de juicio, no normas.
- El modelo **no** arrastra pérdidas fiscales (IRE solo sobre EBIT > 0), **no** valora opciones reales y **no** valida que los flujos sean realmente incrementales: eso depende de quien carga los datos.
- Los casos F3 (VAN negativo sin VT) y F4 (VAN casi nulo) cambian de conclusión **bajo los supuestos del informe**; no equivalen a una recomendación de rechazo.

## 5. Cómo verificar

```bash
python -m unittest -v          # 56 pruebas del motor + 14 de la interfaz
python backtest.py             # regenera INFORME_BACKTEST.md
streamlit run app.py
```

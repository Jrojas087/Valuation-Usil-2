# Informe de backtest — ValuationSuite USIL v2.0 → v3.0

Generado por `python backtest.py`. Todo número sale de ejecutar el código; los datos faltantes figuran como SUPUESTO al final de la Fase 4.

## FASE 1 — Reproducción (línea base)

### 1.1 Reproducción de los outputs reportados (tolerancia ±0,5 %)

| Fixture | Indicador | Reportado v2.0 | Reproducido | Δ |
|---|---|---|---|---|
| F1 | VAN | 7.454.269.220 | 7.457.184.159 | +0,04% |
| F1 | TIR | 116,35% | 116,36% | +0,01% |
| F1 | Payback simple / desc. | 1,1 / 1,3 | 1,11 / 1,28 | ✓ (redondeo) |
| F2 | PV FCF | 40.496.748 | 40.500.303 | +0,01% |
| F2 | VT año 5 | 148.743.916 | 148.788.828 | +0,03% |
| F2 | PV VT | 77.309.486 | 77.344.077 | +0,04% |
| F2 | VAN | 104.372.234 | 104.410.380 | +0,04% |
| F2 | TIR | 106,00% | 106,01% | +0,01% |
| F2 | Payback simple / desc. | 1,4 / 1,7 | 1,42 / 1,68 | ✓ (redondeo) |
| F2 (2.ª corrida, WACC 11,81 %) | VAN | 135.541.600 | 135.620.088 | +0,06% |
| F2 (2.ª corrida) | TIR | 110,95% | 110,96% | +0,01% |
| F3 (USD @7.000) | VAN | 252.033,88 | 252.033,89 | +0,00% |
| F3 | TIR | 22,17% | 22,17% | +0,01% |
| F3 | Payback simple | 6,1 | 6,08 | ✓ (redondeo; truncado daría 6,0) |
| F3 | VT % del valor | 43,69% | 43,69% | +0,00% |
| F3 (USD) | VAN sin VT | -79.657,64 | -79.657,63 | +0,00% |
| F4 (FCF armado, Ke sin redondear) | VAN | 101.149.710 | 101.149.710 | +0,00% |
| F4 | VAN con Ke redondeado 11,21 % | 101.149.710 | 101.089.446 | -0,06% |
| F4 | TIR | 47,29% | 47,29% | -0,00% |
| F4 | Payback simple / desc. | 3,41 / 4,54 | 3,41 / 4,54 | ✓ |

**Fórmulas reales de la v2.0** (leídas de `app.py` en el commit `7f07375`):

| Elemento | Fórmula en el código |
|---|---|
| FCF₁ | `NOPAT + Dep − CAPEX₁ − ΔCT`, con `NOPAT = EBIT·(1−T)` **aun si EBIT < 0** y `ΔCT = ΔAR + ΔINV − ΔAP` |
| FCF_t | `FCF₁·(1+g)^(t−1)` (crecimiento constante; ΔCT, CAPEX y depreciación crecen a g) |
| Valor terminal | `FCF_N·(1+g∞)/(WACC−g∞)` **siempre**, si `WACC > g∞ + 0,5 pp`; si no, VAN = NaN |
| VAN | `Σ FCF_t/(1+WACC)^t + VT/(1+WACC)^N − CAPEX₀` |
| TIR | `numpy_financial.irr` con el VT sumado al flujo del año N; devuelve N/A si TIR < −99 % o > 200 % |
| Payback | acumulado con interpolación lineal intra-año; se muestra con `f"{x:.1f}"` (redondea) |
| Índice de rentabilidad | **no se calcula** |
| Ke | `Rf + β_L·ERP + CRP`, `β_L = β_U·(1+(1−T)·D/E)` (Hamada) — **sin diferencial de inflación** |
| Kd | input del usuario; entra al WACC como `Kd·(1−T)` |
| WACC | `E/V·Ke + D/V·Kd·(1−T)`; no depende del horizonte, de g ni de ningún input operativo |
| Monte Carlo | triangulares sobre **g, WACC, CAPEX y un multiplicador de FCF₁ (0,85–1,15)**; sin semilla; VT siempre incluido |

**Veredictos de la Fase 1**
- **Hipótesis confirmada** para F1, F2 (ambas corridas), F3 y F4: VAN, TIR y payback reproducen dentro de ±0,06 %.
- Las diferencias residuales (≤ 0,06 %) vienen de que los WACC reportados están redondeados a 2 decimales (p. ej. 12,80 %).
- **Ovos Terra SÍ se reproduce**; la hipótesis de partida estaba incompleta solo en el armado del FCF. Con los inputs del fixture:
  `FCF = (Ventas − Balanceado − Fijos)·(1−10 %) − Reposición equivalente = 14.912.000`, `g = 0 %`, `CAPEX₀ = 50.820.000` (solo etapa 1;
  la etapa 2 entra como costo anual equivalente, que es el valor anual de 35.390.000 a 2 años al Ke: 20.728.000 ≈ 35.390.000 × 0,5854),
  y Ke sin redondear (11,2063 %). *Derivación hecha por ingeniería inversa y verificada numéricamente (VAN con error 0,00001 %).*
  Esto también muestra que el impuesto se calculó sobre el margen **antes** de la reposición y sin depreciación (ver D5).
- **Monte Carlo: no reproducible dentro de ±0,5 %.** Dos razones medidas: (i) la v2.0 no usa semilla y los rangos usados no figuran en los
  fixtures; (ii) con rangos simétricos plausibles no se obtienen los σ y P95 de F2 (σ = 208,7 M reportado; ~13–58 M simulado según rangos),
  y en F3 la mediana reportada (USD 145 mil) está muy por debajo del caso base (USD 252 mil), lo que exige rangos asimétricos no registrados.
  El ruido de muestreo por sí solo es chico (CV 0,1–0,25 % con 10.000 simulaciones), de modo que el ±0,5 % sería alcanzable **si se conocieran los rangos**.
  Sí se reproducen cualitativamente P(VAN<0) ≈ 0 %, P5 > 0 y asimetría a la derecha.

### 1.2 Humanitas (inputs no informados: FCF₁ y g∞ **inferidos**)

| Esc. | Compra / crec. / horizonte | FCF₁ inferido | g∞ inferido | VAN rep. | VAN modelo | TIR rep. | TIR modelo | Payback |
|---|---|---|---|---|---|---|---|---|
| A | 10% / 20% / 5a | 3.795.908 | -0,40% | 55.611.099 | 55.611.099 | 126,91% | 126,87% | 1,16 / 1,30 |
| B | 10% / 10% / 5a | 3.782.525 | -0,45% | 40.228.380 | 40.228.380 | 114,59% | 114,57% | 1,18 / 1,34 |
| C | 5% / 20% / 8a | 709.550 | -2,80% | 10.089.056 | 10.089.056 | 34,86% | 34,87% | 4,49 / 5,82 |
| D | 5% / 10% / 8a | 714.294 | -3,30% | 4.552.689 | 4.552.689 | 25,49% | 25,49% | 5,15 / 7,25 |

**Lectura (con límites).** El fixture no informa FCF₁ ni g∞. Despejándolos de VAN y TIR de cada escenario aparecen valores coherentes
entre A↔B (FCF₁ ≈ 3,78–3,80 M; g∞ ≈ −0,4 %) y C↔D (FCF₁ ≈ 0,71 M; g∞ ≈ −2,8 a −3,3 %). Con 2 incógnitas y 2 outputs por escenario el ajuste
**no es una validación independiente**; solo la consistencia entre pares lo es, y es buena pero no exacta. **No puede afirmarse** que
Humanitas se reproduzca con la v2.0: falta información. Un g∞ negativo es llamativo (¿se usó un VT con g∞ < 0, o el FCF tiene otra estructura?).

**WACC distinto según horizonte (11,13 % vs 10,98 %).** No puede explicarse con el código: el WACC de la v2.0 depende solo de
`Rf, ERP, CRP, βU, T, D, E, Kd` (ver tabla de fórmulas). Por lo tanto, entre las corridas cambió al menos uno de esos inputs
(p. ej. la relación D/E o el Kd), que el reporte no imprime. Esto es un defecto de trazabilidad (D7), no de fórmula.

## FASE 2 — Diagnóstico de defectos con evidencia

### D1 y D2 — Perpetuidad por defecto y TIR inflada

| Caso | VAN con VT | VAN sin VT | VT % del valor | TIR con VT | TIR sin VT | ¿VAN sin VT < 0? |
|---|---|---|---|---|---|---|
| F1 | 7.457.184.159 | 2.266.331.678 | 62,0% | 116,4% | 90,0% | no |
| F2 | 104.410.380 | 27.066.303 | 65,6% | 106,0% | 74,0% | no |
| F3 | 1.764.237.255 | -557.603.429 | 43,7% | 22,2% | 10,5% | SÍ |
| F4 | 101.149.710 | 4.008.393 | 63,9% | 47,3% | 14,3% | no |
| F5-A* | 55.611.099 | 15.495.427 | 66,7% | 126,9% | 96,6% | no |
| F5-B* | 40.228.380 | 12.139.873 | 62,7% | 114,6% | 87,6% | no |
| F5-C* | 10.089.056 | 2.295.944 | 53,3% | 34,9% | 21,1% | no |
| F5-D* | 4.552.689 | 456.632 | 45,1% | 25,5% | 13,4% | no |

*(\* Humanitas con inputs inferidos; sus filas son indicativas.)*

- **D1 — CONFIRMADO, severidad ALTA.** El VT se aplica siempre (`app.py`: `tv = fcf[-1]*(1+g_inf)/(wacc-g_inf)` sin interruptor) y pesa
  **44 % (F3) a 66 % (F2)** del valor, como se indicó. Sin VT, **Pantalla RH** pasa a VAN negativo (−USD 79.657,63): es el único caso de la tabla en que ocurre.
  **Matiz que corrige el enunciado:** en **Ovos Terra el VAN sin perpetuidad es +Gs 4,0 M (positivo, equivale al 7,9 % del CAPEX₀)**,
  no negativo; es un margen mínimo que desaparece con ajustes menores (ver Fase 4). En Humanitas C y D (inputs inferidos) el VAN sin VT también es positivo pero chico.
- **D2 — CONFIRMADO, severidad ALTA.** `cashflows[-1] += tv` en el cálculo de la TIR. TIR con VT: F1 116 %, F2 106 %, Humanitas A ≈ 127 %;
  sin VT bajan a 90 %, 74 % y valores aún altos que revelan otro problema (FCF₁ vs inversión; ver V02/V03).

### D3 — Desajuste de moneda (Ke en USD aplicado a flujos en Gs)

| Caso | Ke v2.0 | Kd | Ke < Kd | Ke en Gs corregido* | Ke_Gs < Kd |
|---|---|---|---|---|---|
| F1 | 12,53% | 14,50% | SÍ | 13,6279% | SÍ |
| F2 | 13,03% | 18,00% | SÍ | 14,1327% | SÍ |
| F3 | 14,53% | 16,00% | SÍ | 15,6474% | SÍ |

\* SUPUESTO: Ke reportado = CAPM en USD (así lo establece el código: `ke = rf + beta_l*erp + crp`, sin conversión), π Gs = 3.5 % y π USD = 2.5 %
(valores del benchmark TechCare; no están en los fixtures). Factor de conversión: (1+π_Gs)/(1+π_USD) = 1.009756, es decir **+0.98 pp sobre (1+Ke)**.

- **D3 — CONFIRMADO, severidad ALTA.** El código no tiene inputs de inflación ni conversión. Ke < Kd en F1, F2 y F3 (con deuda).
  Aun con la conversión de +0,98 pp, **Ke_Gs sigue siendo menor que Kd en F1, F2 y F3**: el problema no es solo de moneda; también hay un Kd alto
  (14,5 %–18 %) frente a un CAPM con ERP/CRP bajos. La alerta V01 sigue activa en F1 y F2 en la versión corregida (correcto: es una inconsistencia real de inputs);
  en F3 no se dispara porque, con WACC = Ke, el modelo trata el proyecto como 100 % capital propio (SUPUESTO).
- Benchmark: Ke_USD 14.34 % → Ke_Gs = (1,1434·1,035/1,025) − 1 = 15.46 %,
  coherente con el WACC Gs de 15,46 % del benchmark (con deuda más barata).

### D4 — Monte Carlo sin capacidad de detectar riesgo


- **Replicando Ovos Terra** (solo crecimiento −3 % a +1,5 %): P(VAN<0) = **0.0 %**, P5 = Gs 91.012.426, P95 = Gs 105.764.135
  (reportado: P5 73.669.241 / P95 130.121.212: no se reproduce porque los rangos de la v2.0 se desconocen; la conclusión cualitativa —0 % de pérdida— sí coincide).
- El escenario **pesimista determinístico** del fixture da FCF = Gs -15.760.000 por año. Con esa serie constante, la fórmula v2.0 da
  VAN = **Gs -211.431.765** (con VT sobre un flujo negativo, que además resta valor: es un VT negativo, otro absurdo del método).
  Sin VT: Gs -108.766.317. **La simulación mostraba 0 % de probabilidad de pérdida mientras un escenario plausible destruye todo el capital.**
- **CONFIRMADO, severidad ALTA.** Evidencia en el código: `run_monte_carlo` solo muta `g`, `WACC`, `CAPEX` y un multiplicador de FCF₁ (0,85–1,15) fijo;
  no hay precio, volumen, costos ni capital de trabajo. Es **imposible** que detecte el riesgo operativo. El multiplicador ±15 % sobre FCF₁ parece
  cubrir el flujo, pero en Ovos Terra el FCF base (14,9 M) es la diferencia de dos magnitudes grandes (ventas 153,6 M): una caída de ~10,8 % de las ventas ya lo vuelve negativo.
- Sesgo y base descentrada (F2/F3): **CONFIRMADO en F3** (mediana USD 145.163 vs base USD 252.034: el caso base queda entre el P50 y el P95 reportados, es decir,
  por encima del centro de la distribución; el percentil exacto no puede calcularse porque la v2.0 no lo informa) y en F2 (σ = 208,7 M con P50 = 95,9 M y P95 = 429,8 M: cola derecha explosiva porque el WACC simulado se acerca a g∞; el VT crece como 1/(WACC−g∞)).

### D5 — FCF como input único / EBIT no concilia


- **PARCIALMENTE CONFIRMADO, severidad MEDIA-ALTA.** *Matiz sobre la v2.0:* el código **sí** tiene un puente contable para el Año 1
  (ventas, costos variables y fijos, depreciación, CAPEX de mantenimiento, ΔAR/ΔINV/ΔAP). Los fixtures F1–F3 y F5, en cambio, traen el FCF como dato.
  Los defectos reales del código son otros: (a) `NOPAT = EBIT·(1−T)` también con EBIT negativo (crédito fiscal ficticio; con los valores por defecto de la v2.0 el EBIT del Año 1 era −250 M);
  (b) el puente de un solo año se extrapola con g constante: ΔCT, CAPEX y depreciación crecen a g en vez de seguir las ventas y la vida de los activos;
  (c) el CAPEX de mantenimiento por defecto (250 M) era menor que la depreciación (1.500 M) y esa diferencia se perpetuaba en el VT; (d) no hay reposición ni valor de desecho.
- **Smart Recovery:** EBIT₁ 334.313.200 vs FCF₁ 9.068.680 → FCF/EBIT = **0.027** (fuera del rango razonable 0,30–1,50): incoherente. Alerta V06 se dispara.
- **Pantalla RH:** EBIT₁ 579.000.000 vs FCF₁ 476.100.000 → FCF/EBIT = **0.822** (dentro del rango): con la información disponible
  **no puede afirmarse** inconsistencia (faltan depreciación, CAPEX y capital de trabajo). Se descarta como evidencia de D5 en este caso.
- **Ovos Terra:** el impuesto se calculó sobre el margen antes de reposición y sin depreciación: el FCF reproducido (14,9 M) difiere del que resulta de un flujo conciliado (ver Fase 4).

### D6 — Sin validaciones de inputs
- **CONFIRMADO, severidad MEDIA.** El único chequeo del código es `WACC > g∞ + 0,5 pp`, más tres `st.warning` (costos > ventas, FCF₁ < 0, TIR < WACC). No hay alertas para
  Ke < Kd (F1, F2, F3), TIR > 100 % (F1, F2, Humanitas), g explícito de 15 % + perpetuidad (F2), moneda de la tasa vs. flujo, ni horizontes distintos entre escenarios (Humanitas 5 vs 8 años).
  En la versión corregida estas situaciones disparan V01 (Ke < Kd), V02/V03 (TIR y payback extremos), V04 (peso del VT), V05 (g explícito), V06 (EBIT vs FCF), V08 (horizontes) y V07 cuando se desactiva la conversión de moneda.

### D7 — Inconsistencias de presentación
- **WACC distinto entre escenarios (Humanitas): CONFIRMADO como síntoma, causa no determinable con la información disponible** (ver 1.2). Defecto de trazabilidad: el reporte no imprime D/E, Kd ni Rf.
- **WACC mostrado 14,53 % vs interno 14,529866 %: CONFIRMADO.** `fmt_pct` usa `.2f`; el VAN se calcula con la tasa sin redondear. Recalcular a mano con 14,53 % da un VAN de F3 que difiere en USD 9,65 (0,004 %): inmaterial, pero el reporte no permite reproducir la cifra.
- **Payback truncado (1,48 → «1,4»): NO CONFIRMADO en el código ni en los fixtures.** La v2.0 usa `f"{pb:.1f}"`, que redondea. Los fixtures lo corroboran: F1 1,278 se muestra «1,3» (truncar daría 1,2),
  F2 1,682 → «1,7», F3 6,076 → «6,1». Si el usuario vio «1,4» para 1,48, provino de otra versión o de una transcripción manual. Se descarta como defecto de la v2.0, pero se fija redondeo comercial con 2 decimales (C7).

### D8 — «DICTAMEN: APROBADO» automático
- **CONFIRMADO, severidad ALTA.** `committee_check` devuelve «APROBADO» si VAN>0, P(VAN<0) ≤ 20 %, P50>0 y P5>0. Con un Monte Carlo que no puede detectar riesgo (D4) y un VAN inflado por el VT (D1),
  F1, F2, F3 y F4 cumplen los criterios con los datos reportados (VAN>0, P(VAN<0) ≤ 1,5 %, P5>0), aunque F3 tiene VAN negativo sin VT y F4 tiene un escenario pesimista con flujo negativo. Se reemplaza por «Indicadores favorables bajo los supuestos cargados» + alertas + variable crítica (C8).

## FASE 4 — Re-ejecución con la versión corregida sobre los mismos fixtures

### F1 — FrioLog Paraguay (transporte refrigerado) (valores en Gs)
| Indicador | Versión actual | Versión corregida | Δ | Causa |
|---|---|---|---|---|
| WACC | 12,8000% | 13,3278% | +0,53 pp | D3 (Ke en moneda del flujo) |
| VAN (indicador principal) | 7.457.184.159 | 2.224.164.471 | -70,17% | D1 + D3 |
| VAN con VT (referencial) | 7.457.184.159 | 7.058.972.759 | -5,34% | D3 (tasa); FCF normalizado igual al v2.0 porque el fixture no trae reinversión |
| Peso del VT | 62,0% | 60,6% | — | se muestra siempre (C1) |
| TIR principal (sin VT) | 116,36% (con VT) | 89,99% | — | D2 |
| TIR con VT (secundaria) | 116,36% | 115,47% | — | D3 |
| TIRM sin VT | no existía | 44,87% | — | C2 |
| Índice de rentabilidad (sin VT) | no existía | 3,41 | — | nuevo |
| Payback simple / desc. | 1,11 / 1,28 | 1,11 / 1,29 | — | sin cambio salvo que el flujo del año N cambie (recupero CT) |
| P(VAN<0) | 0,0% | 0,0% | — | D4 (drivers) + D1 |
| P5 / P50 / P95 de VAN | 5.249.000.000 / — / — | 1.477.294.435 / 1.995.336.484 / 2.375.135.707 | — | D4 |
| CVaR5 | — | 1.382.941.084 | — | D4 |
| Posición del caso base en la distribución | no se informaba | 81,2% | — | C4 |
| VAN escenario pesimista determinístico | no existía | 989.774.867 | — | C4 |
| Variable crítica (VAN = 0) | no existía | FCF (nivel): -70,7% | — | C8 |
| Lectura | DICTAMEN: APROBADO (VAN>0, P(VAN<0)≤20 %, P5>0) | Indicadores favorables bajo los supuestos cargados | — | D8 |
| Alertas activas | ninguna | V01, V02, V03, V04 | — | D6 |

### F2 — Smart Recovery (suplemento) (valores en Gs)
| Indicador | Versión actual | Versión corregida | Δ | Causa |
|---|---|---|---|---|
| WACC | 13,9800% | 14,7523% | +0,77 pp | D3 (Ke en moneda del flujo) |
| VAN (indicador principal) | 104.410.380 | 26.251.151 | -74,86% | D1 + D3 |
| VAN con VT (referencial) | 104.410.380 | 96.113.797 | -7,95% | D3 (tasa); FCF normalizado igual al v2.0 porque el fixture no trae reinversión |
| Peso del VT | 65,6% | 63,8% | — | se muestra siempre (C1) |
| TIR principal (sin VT) | 106,01% (con VT) | 73,99% | — | D2 |
| TIR con VT (secundaria) | 106,01% | 104,58% | — | D3 |
| TIRM sin VT | no existía | 42,51% | — | C2 |
| Índice de rentabilidad (sin VT) | no existía | 2,95 | — | nuevo |
| Payback simple / desc. | 1,42 / 1,68 | 1,42 / 1,70 | — | sin cambio salvo que el flujo del año N cambie (recupero CT) |
| P(VAN<0) | 0,0% | 0,0% | — | D4 (drivers) + D1 |
| P5 / P50 / P95 de VAN | 42.920.804 / — / 429.776.275 | 16.701.361 / 23.266.399 / 28.141.567 | — | D4 |
| CVaR5 | 37.881.736 | 15.499.971 | — | D4 |
| Posición del caso base en la distribución | no se informaba | 81,8% | — | C4 |
| VAN escenario pesimista determinístico | no existía | 10.261.413 | — | C4 |
| Variable crítica (VAN = 0) | no existía | FCF (nivel): -66,1% | — | C8 |
| Lectura | DICTAMEN: APROBADO (VAN>0, P(VAN<0)≤20 %, P5>0) | Indicadores favorables bajo los supuestos cargados | — | D8 |
| Alertas activas | ninguna | V01, V02, V03, V04, V05, V06 | — | D6 |

### F3 — Pantalla icónica RH (pantalla LED publicitaria) (valores en USD @7.000)
| Indicador | Versión actual | Versión corregida | Δ | Causa |
|---|---|---|---|---|
| WACC | 14,5299% | 15,6472% | +1,12 pp | D3 (Ke en moneda del flujo) |
| VAN (indicador principal) | 252.034 | -98.244 | -138,98% | D1 + D3 |
| VAN con VT (referencial) | 252.034 | 178.842 | -29,04% | D3 (tasa); FCF normalizado igual al v2.0 porque el fixture no trae reinversión |
| Peso del VT | 43,7% | 40,4% | — | se muestra siempre (C1) |
| TIR principal (sin VT) | 22,17% (con VT) | 10,47% | — | D2 |
| TIR con VT (secundaria) | 22,17% | 21,49% | — | D3 |
| TIRM sin VT | no existía | 12,91% | — | C2 |
| Índice de rentabilidad (sin VT) | no existía | 0,81 | — | nuevo |
| Payback simple / desc. | 6,08 / N/D | 6,08 / N/D | — | sin cambio salvo que el flujo del año N cambie (recupero CT) |
| P(VAN<0) | 1,5% | 100,0% | — | D4 (drivers) + D1 |
| P5 / P50 / P95 de VAN | 29.424 / — / 287.369 | -228.745 / -148.459 / -79.518 | — | D4 |
| CVaR5 | 6.061 | -247.642 | — | D4 |
| Posición del caso base en la distribución | no se informaba | 87,0% | — | C4 |
| VAN escenario pesimista determinístico | no existía | -343.555 | — | C4 |
| Variable crítica (VAN = 0) | no existía | CAPEX inicial: -19,4% | — | C8 |
| Lectura | DICTAMEN: APROBADO (VAN>0, P(VAN<0)≤20 %, P5>0) | Indicadores desfavorables bajo los supuestos cargados | — | D8 |
| Alertas activas | ninguna | V11 | — | D6 |

### F4 — Ovos Terra (huevos, 800 ponedoras) (valores en Gs)
| Indicador | Versión actual | Versión corregida | Δ | Causa |
|---|---|---|---|---|
| WACC | 11,2100% | 12,2912% | +1,08 pp | D3 (Ke en Gs) |
| VAN (indicador principal) | 101.149.710 | 10.465.703 | -89,65% | D1 (se quita la perpetuidad) + D3 (tasa) + D5 (flujo conciliado) |
| VAN con VT (referencial) | 101.149.710 | 47.618.096 | -52,92% | D3 (tasa); FCF normalizado igual al v2.0 porque el fixture no trae reinversión |
| Peso del VT | 63,9% | 43,1% | — | se muestra siempre (C1) |
| TIR principal (sin VT) | 47,29% (con VT) | 19,17% | — | D2 |
| TIR con VT (secundaria) | 47,29% | 34,25% | — | D3 |
| TIRM sin VT | no existía | 16,58% | — | C2 |
| Índice de rentabilidad (sin VT) | no existía | 1,21 | — | nuevo |
| Payback simple / desc. | 3,41 / 4,54 | 3,35 / 4,32 | — | sin cambio salvo que el flujo del año N cambie (recupero CT) |
| P(VAN<0) | 0,0% | 73,3% | — | D4 (drivers) + D1 |
| P5 / P50 / P95 de VAN | 73.669.241 / — / 130.121.212 | -71.921.143 / -17.559.116 / 27.841.361 | — | D4 |
| CVaR5 | — | -84.551.869 | — | D4 |
| Posición del caso base en la distribución | no se informaba | 84,0% | — | C4 |
| VAN escenario pesimista determinístico | -15.760.000 (FCF anual) | -108.029.272 | — | C4 |
| Variable crítica (VAN = 0) | no existía | Precio (ingresos Año 1): -2,1% | — | C8 |
| Lectura | DICTAMEN: APROBADO (VAN>0, P(VAN<0)≤20 %, P5>0) | Indicadores mixtos bajo los supuestos cargados | — | D8 |
| Alertas activas | ninguna | V11, V15 | — | D6 |

### F5 — Humanitas (inputs inferidos, ver 1.2; WACC reportado tratado como Ke USD de una estructura 100 % propia: SUPUESTO)

| Esc. | WACC | VAN actual | VAN corregido (sin VT) | TIR actual (con VT) | TIR sin VT | P(VAN<0) | Alertas |
|---|---|---|---|---|---|---|---|
| A | 11,1300% → 12,2142% | 55.611.099 | 14.893.300 | 126,9% | 96,6% | 0,0% | V02, V03, V04, V05 |
| B | 11,1300% → 12,2142% | 40.228.380 | 11.665.911 | 114,6% | 87,6% | 0,0% | V02, V03, V04 |
| C | 10,9800% → 12,0627% | 10.089.056 | 1.979.641 | 34,9% | 21,1% | 2,2% | V04, V05, V11 |
| D | 10,9800% → 12,0627% | 4.552.689 | 246.545 | 25,5% | 13,4% | 70,6% | V04, V11 |

Alertas al comparar los cuatro escenarios: **V08** Horizontes distintos entre escenarios comparados; **C7** El WACC cambió sin cambio en sus inputs.

### Resumen: ¿qué proyectos cambian de conclusión?

| Caso | Proyecto | VAN v2.0 | VAN corregido | ¿Cambia de signo? | ¿TIR sin VT < WACC? |
|---|---|---|---|---|---|
| F1 | FrioLog Paraguay (transporte refrigerado) | positivo | positivo | no | no |
| F2 | Smart Recovery (suplemento) | positivo | positivo | no | no |
| F3 | Pantalla icónica RH (pantalla LED publicitaria) | positivo | negativo | SÍ | SÍ |
| F4 | Ovos Terra (huevos, 800 ponedoras) | positivo | positivo | no | no |
| F5-A* | Humanitas A | positivo | positivo | no | no |
| F5-B* | Humanitas B | positivo | positivo | no | no |
| F5-C* | Humanitas C | positivo | positivo | no | no |
| F5-D* | Humanitas D | positivo | positivo | no | no |

**Ovos Terra — por qué cambia.** El FCF conciliado del Año 1 es Gs 8.501.200 (vs 14.912.000 de la v2.0): el motor deduce la reposición y la depreciación antes de
calcular el IRE y descuenta la inversión en capital de trabajo del Año 1 (SUPUESTO: 1/12 de los costos anuales), que se recupera al final. Aun así, **sin perpetuidad y con el Ke llevado a guaraníes (WACC 12,2912%)** el VAN es Gs 10.465.703;
con el escenario pesimista del fixture el VAN pasa a Gs -108.029.272. El Monte Carlo corregido da P(VAN<0) = 73,3% (la v2.0 mostraba 0 %).


### Supuestos usados (todos explícitos)

1. **SUPUESTO** — π Gs = 3.5 % y π USD = 2.5 % (del benchmark TechCare PY; los fixtures no traen inflaciones).
2. **SUPUESTO** — Ke reportado de F1, F2 y F3 = CAPM en USD (confirmado por el código: no hay conversión); Kd reportado ya está en Gs.
3. **SUPUESTO** — Pesos E/V y D/V de F1 y F2 DESPEJADOS del WACC reportado: wD = (Ke − WACC)/(Ke − Kd(1−T)). F3: 100 % capital propio (WACC = Ke a 2 decimales).
4. **SUPUESTO** — Sin información de capital de trabajo, valor de desecho ni reposición en F1, F2, F3 y F5: capital de trabajo = 0, valor de desecho = 0 (criterio TechCare), sin perpetuidad. Esto es conservador y probablemente subestima F1 (flota usada con valor de reventa) y F3.
5. **SUPUESTO** — Monte Carlo corregido en fixtures con FCF directo (sin estructura de costos): único driver operativo = nivel del FCF, triangular (0,70; 1,00; 1,10), CAPEX (0,95; 1,00; 1,20), WACC ± 2 pp, 10.000 sim., semilla 2026. Escenario pesimista = extremos adversos de esos rangos.
6. **SUPUESTO** — IRE 10 %.
7. **SUPUESTO** — F4: depreciación lineal a 5 años de la etapa 1 (no informada); capital de trabajo = 1/12 de los costos anuales (balanceado + fijos) con recupero al año 5; la reposición del plantel se mantiene como costo anual equivalente (Gs 20.728.000) dentro de los costos fijos; balanceado tratado como costo fijo por gallina (no varía con la postura).
8. **SUPUESTO** — F4 pesimista: la descomposición (postura 70 % → ingresos; balanceado de Gs 2.500 a 3.000/kg, precio base INFERIDO) se calibra para que el FCF con la fórmula v2.0 coincida con el dato del fixture (−15.760.000); el FCF total pesimista es dato, la descomposición es supuesto.
9. **SUPUESTO** — F4 Monte Carlo corregido: precio de venta (0,90; 1,00; 1,08), postura/volumen (mín = caso pesimista; 1,00; 1,05), costos fijos incl. alimento (0,97; 1,00; máx = pesimista), CAPEX (0,95; 1,00; 1,15), WACC ± 2 pp.

### Limitaciones del backtest
- Humanitas depende de inputs inferidos (no verificables).
- El Monte Carlo de la v2.0 no puede reproducirse dentro de ±0,5 % por falta de rangos y de semilla.
- Las corridas corregidas de F1, F2, F3 y F5 usan el FCF del fixture (sin estructura de costos), por lo que el Monte Carlo y el punto de equilibrio solo ven el **nivel** del FCF, el CAPEX y la tasa.
  Solo F4 permite correr el motor completo (precio, volumen, costos). Esa diferencia limita la comparabilidad entre casos.
- Las inflaciones (3,5 % / 2,5 %) son las del benchmark TechCare, no datos de cada proyecto.

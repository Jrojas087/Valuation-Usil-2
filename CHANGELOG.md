# Changelog

## 3.1 — correcciones del testeo adversarial
Fallos encontrados atacando la v3.0 con entradas extremas; cada uno tiene su prueba de regresión (`TestAdversarial`, `TestAdversarialUI`).

### Corregido
- **Rangos del Monte Carlo sin validar**: mín > máx anulaba la variación en silencio y un rango que no contenía al caso base sorteaba
  valores fuera de lo declarado. Ahora `MCSpec.validate()` los rechaza (en la app los rangos quedaron fijos).
- **Tasas sin límites**: la interfaz aceptaba Rf −200 %, β o Kd negativos, IRE 150 % y π USD −100 % (este último rompía la app). Ahora
  cada campo tiene límites y el motor rechaza un WACC ≤ 0, un IRE fuera de [0 %, 100 %) y una inflación ≤ −100 %.
- **Lectura «favorable» con alertas de severidad alta**: pasa a «Indicadores favorables con reservas bajo los supuestos cargados».
- **Comparador de escenarios**: cada escenario guarda su moneda y se muestra en ella; alerta V19 si se mezclan monedas.
- **Payback**: se informa el último cruce del acumulado; si el acumulado termina negativo, N/D (antes informaba el primer cruce).
- **Ventas = 0 con costos variables o capital de trabajo**: se rechaza con un mensaje (antes esos costos se descartaban).
- El nombre del proyecto y el responsable se escapan en el encabezado (admitían HTML).

### Cambiado (mueve resultados)
- **Reposición independiente de la vida contable**: en la app se carga como % del CAPEX inicial (por defecto 12,5 %, equivalente al
  100 % de la depreciación a 8 años de la v3.0). Antes, cambiar la vida contable de 8 a 3 años bajaba el VAN de la demo de Gs 2.424 M a 28 M.
- **Sin reposición en el año N** cuando el proyecto termina (sin VT o con desecho). El VAN de la demo pasa de Gs 2.424 M a 2.693 M.
- **Desecho simétrico**: vender por debajo del valor libro genera escudo fiscal (supone otra renta gravada contra la cual deducirlo).
- **Arrastre de pérdidas fiscales** (siempre activo en la app): hasta 5 años, tope 20 % de la renta neta de cada año.

### Simplificado (decisión didáctica)
- **El Monte Carlo ya no se configura**: se quitaron de la barra lateral sus 16 controles (simulaciones, distribución, semilla, rangos de
  cada variable, rango del WACC, correlaciones y tipo de escenario pesimista). Corre con supuestos fijos (15.000 escenarios, triangular,
  semilla fija, rangos por defecto, sin correlaciones) y la app los enuncia en una línea bajo el histograma. Los resultados se muestran igual.
  El motor conserva esas opciones para pruebas y backtest.
- El arrastre de pérdidas fiscales queda siempre activo, sin casilla.

### Calibrado con 10 proyectos aleatorios
Se generaron 10 proyectos al azar (semilla fija) y se recalcularon con un segundo modelo escrito aparte, en Python puro.
- **Exactitud**: WACC, flujos, VAN, TIR, payback, valor anual equivalente y puntos de equilibrio coinciden con el modelo independiente
  (diferencia relativa < 1e-9), y la app muestra lo mismo que el motor en los 10 casos. Quedó como prueba permanente (`TestAleatorios`).
- **Escenario pesimista recalibrado**: con todas las variables en el extremo de su rango caía por debajo del peor de los 15.000 escenarios
  simulados en los 10 casos, así que la alerta V11 saltaba siempre y ningún proyecto podía leerse «favorable». En la app ahora cada
  variable va en su 25 % más adverso, todas a la vez (≈ 7 % peor de la simulación). El motor conserva los extremos por defecto.
- **Peso del VT acotado** a 0–100 % (mostraba 106 % cuando los flujos del horizonte eran negativos); sin valor si el total es ≤ 0.
- **Alerta V20**: el horizonte supera la vida de los activos y la reposición no cubre su desgaste (proyectos que terminan).
- **Variable crítica con VAN negativo**: el texto aclara que indica cuánto debe mejorar el proyecto, no su margen de seguridad.

### Agregado
- Alertas V18 (D/V > 80 %) y V19 (monedas distintas entre escenarios).
- `Project.maint_capex_of_capex`, `repl_final_year`, `loss_carryforward`, `loss_cf_years`, `loss_cf_cap`. Sus valores por defecto conservan
  el comportamiento de la v3.0, por eso el backtest de F1–F5 no cambia de números (solo la lectura de dos casos pasa a «con reservas»).

### A verificar
- Los parámetros del arrastre (5 años, 20 %) se cargaron según la Ley 6380/2019; confirmar contra la norma vigente.

## 3.0 — corrección del motor y nuevo one-pager
Respuesta a los defectos D1–D8 detectados con los 5 casos (ver `MEJORAS_CALCULADORA.md` e `INFORME_BACKTEST.md`).

### Agregado
- `valuation_engine.py`: motor sin Streamlit (flujo desagregado, WACC en la moneda del flujo, VT opcional, Monte Carlo sobre drivers,
  punto de equilibrio, 17 alertas, EAA, TIRM, índice de rentabilidad). Incluye el **modo compatibilidad** (`legacy_*`) con las fórmulas v2.0.
- `fixtures.py` (casos F1–F5 y benchmark, sin modificar), `backtest.py` (genera `INFORME_BACKTEST.md`).
- `test_engine.py` (56 pruebas: T1–T6, C1–C8, criterios CFA, reportes, glosario) y `test_app.py` (14 pruebas de interfaz con `AppTest`,
  incluida la verificación de que cada campo, indicador y tabla trae su explicación académica).
- Comparador de escenarios con alerta de horizontes distintos y valor anual equivalente.
- Sección «Supuestos y limitaciones» en el TXT y el PDF.

- `glosario.py`: **explicación académica de cada concepto** (qué es, fórmula, cómo leerlo y base teórica). Alimenta las tablas de la tasa de
  descuento, del punto de equilibrio y del puente EBITDA → FCF, los tooltips de campos e indicadores, un glosario consultable dentro de la
  app y una sección de glosario en el TXT del one-pager. El propósito principal de la calculadora es enseñar.

### Cambiado
- Valor terminal: **desactivado por defecto**; VAN y TIR se muestran siempre con y sin VT, con el peso del VT.
- TIR principal **sin VT**; TIR con VT es secundaria y rotulada.
- Ke convertido a la moneda del flujo por diferencial de inflación; desglose completo del WACC; tasas con 4 decimales.
- Impuesto (IRE) solo si EBIT > 0 (la v2.0 daba crédito fiscal con EBIT negativo).
- Monte Carlo: drivers operativos, semilla fija opcional, correlaciones, CVaR5, posición del caso base, escenario pesimista determinístico.
- «DICTAMEN: APROBADO» → «Indicadores favorables/mixtos/desfavorables bajo los supuestos cargados» + alertas + variable crítica.
- Payback con redondeo comercial a 2 decimales; «IRACIS» → «IRE».
- One-pager (`report_usil.py`) rediseñado; `app.py` reescrito sobre el motor (`width="stretch"` en lugar de `use_container_width`).

### Sin cambio de comportamiento (a propósito)
- Modo compatibilidad: reproduce los fixtures F1–F4 dentro de ±0,06 % (test T6).

### Limitaciones conocidas
Ver sección 4 de `MEJORAS_CALCULADORA.md`.

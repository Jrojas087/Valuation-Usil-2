# Changelog

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

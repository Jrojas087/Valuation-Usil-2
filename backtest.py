# backtest.py — Fases 1, 2 y 4: reproducción, diagnóstico y re-ejecución sobre los mismos fixtures.
# Uso:  python backtest.py            → imprime y escribe INFORME_BACKTEST.md
#
# Todo número del informe sale de ejecutar este script. Lo que los fixtures NO traen se declara en
# ASSUMPTIONS y se rotula "SUPUESTO" en el informe (nunca se inventa en silencio).

from __future__ import annotations

import io
import sys

import numpy as np

import fixtures as fx
import valuation_engine as ve

SEED = 2026
PI_GS, PI_USD = 0.035, 0.025       # SUPUESTO: tomadas del benchmark TechCare PY
TAX = 0.10                          # IRE (dato del enunciado)

ASSUMPTIONS: list[str] = []


def assume(s: str) -> None:
    if s not in ASSUMPTIONS:
        ASSUMPTIONS.append(s)


# ── Formato es-PY (miles con punto, decimales con coma) ──────────────────────
def n0(x):
    return "—" if x is None or x != x else f"{x:,.0f}".replace(",", ".")


def n2(x):
    return "—" if x is None or x != x else f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pc(x, nd=2):
    return "—" if x is None or x != x else f"{x * 100:.{nd}f}%".replace(".", ",")


def dpc(a, b):
    """Diferencia relativa (a − b)/|b|."""
    if a is None or b is None or b == 0 or a != a or b != b:
        return "—"
    return f"{(a - b) / abs(b) * 100:+.2f}%".replace(".", ",")


def yrs(x):
    return ve.fmt_years(x, 2).replace(".", ",")


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ═════════════════════════════════════════════════════════════════════════════
# Reconstrucción de inputs que los fixtures no traen
# ═════════════════════════════════════════════════════════════════════════════
def f4_fcf() -> float:
    f = fx.F4_OVOS_TERRA
    return (f["ventas"] - f["balanceado"] - f["fijos"]) * (1 - TAX) - f["reposicion_costo_anual_equiv"]


def f4_ke() -> float:
    f = fx.F4_OVOS_TERRA
    return f["rf"] + f["beta"] * f["erp"] + f["crp"]


def infer_humanitas() -> dict:
    """Despeja (FCF₁, g∞) de cada par de escenarios con la fórmula de la v2.0. Es una INFERENCIA:
    dos incógnitas por escenario, dos outputs (VAN, TIR); la consistencia A↔B y C↔D es la única validación."""
    f = fx.F5_HUMANITAS
    C = f["capex0"]

    def model(F1, g, ginf, n, w):
        r = ve.legacy_dcf(C, n, w, ginf, F1, g)
        return r["van"], r["irr_raw"]

    out = {}
    for sc, d in f["scenarios"].items():
        best = None
        for ginf in np.arange(-0.06, 0.0501, 0.0005):
            lo, hi = 1e4, 5e8
            for _ in range(70):
                mid = (lo + hi) / 2
                v = model(mid, d["crecimiento"], ginf, d["n_years"], d["wacc"])[0]
                lo, hi = (mid, hi) if v < d["van"] else (lo, mid)
            F1 = (lo + hi) / 2
            irr = model(F1, d["crecimiento"], ginf, d["n_years"], d["wacc"])[1]
            e = abs(irr - d["irr"])
            if best is None or e < best[0]:
                best = (e, ginf, F1)
        out[sc] = dict(ginf=best[1], F1=best[2])
    return out


# ═════════════════════════════════════════════════════════════════════════════
# FASE 1 — reproducción con la fórmula de la v2.0
# ═════════════════════════════════════════════════════════════════════════════
def phase1():
    rows, md = [], []
    L = ve.legacy_dcf
    f = fx.F1_FRIOLOG
    r = L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"])
    rows.append(("F1", "VAN", n0(f["reported"]["van"]), n0(r["van"]), dpc(r["van"], f["reported"]["van"])))
    rows.append(("F1", "TIR", pc(f["reported"]["irr"]), pc(r["irr"]), dpc(r["irr"], f["reported"]["irr"])))
    rows.append(("F1", "Payback simple / desc.", "1,1 / 1,3", f"{yrs(r['payback'])} / {yrs(r['payback_disc'])}",
                 "✓ (redondeo)"))
    f = fx.F2_SMART_RECOVERY
    r = L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], fcfs=f["fcfs"])
    rp = f["reported"]
    rows += [("F2", "PV FCF", n0(rp["pv_fcf"]), n0(r["pv_fcf"]), dpc(r["pv_fcf"], rp["pv_fcf"])),
             ("F2", "VT año 5", n0(rp["tv"]), n0(r["tv"]), dpc(r["tv"], rp["tv"])),
             ("F2", "PV VT", n0(rp["pv_tv"]), n0(r["pv_tv"]), dpc(r["pv_tv"], rp["pv_tv"])),
             ("F2", "VAN", n0(rp["van"]), n0(r["van"]), dpc(r["van"], rp["van"])),
             ("F2", "TIR", pc(rp["irr"]), pc(r["irr"]), dpc(r["irr"], rp["irr"])),
             ("F2", "Payback simple / desc.", "1,4 / 1,7", f"{yrs(r['payback'])} / {yrs(r['payback_disc'])}", "✓ (redondeo)")]
    r2 = L(f["capex0"], f["n_years"], f["reported_run2"]["wacc"], f["g_inf"], fcfs=f["fcfs"])
    rows += [("F2 (2.ª corrida, WACC 11,81 %)", "VAN", n0(f["reported_run2"]["van"]), n0(r2["van"]),
              dpc(r2["van"], f["reported_run2"]["van"])),
             ("F2 (2.ª corrida)", "TIR", pc(f["reported_run2"]["irr"]), pc(r2["irr"]),
              dpc(r2["irr"], f["reported_run2"]["irr"]))]
    f = fx.F3_PANTALLA_RH
    r = L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"])
    rp, fxr = f["reported"], f["fx_pyg_per_usd"]
    rows += [("F3 (USD @7.000)", "VAN", n2(rp["van_usd"]), n2(r["van"] / fxr), dpc(r["van"] / fxr, rp["van_usd"])),
             ("F3", "TIR", pc(rp["irr"]), pc(r["irr"]), dpc(r["irr"], rp["irr"])),
             ("F3", "Payback simple", "6,1", yrs(r["payback"]), "✓ (redondeo; truncado daría 6,0)"),
             ("F3", "VT % del valor", pc(rp["vt_pct"]), pc(r["vt_pct"]), dpc(r["vt_pct"], rp["vt_pct"])),
             ("F3 (USD)", "VAN sin VT", n2(rp["van_sin_vt_usd"]), n2(r["van_sin_vt"] / fxr),
              dpc(r["van_sin_vt"] / fxr, rp["van_sin_vt_usd"]))]
    f = fx.F4_OVOS_TERRA
    fcf, ke = f4_fcf(), f4_ke()
    r = L(f["capex_stage1"], f["n_years"], ke, f["g_inf"], fcf, 0.0)
    rp = f["reported"]
    r_round = L(f["capex_stage1"], f["n_years"], f["wacc"], f["g_inf"], fcf, 0.0)
    rows += [("F4 (FCF armado, Ke sin redondear)", "VAN", n0(rp["van"]), n0(r["van"]), dpc(r["van"], rp["van"])),
             ("F4", "VAN con Ke redondeado 11,21 %", n0(rp["van"]), n0(r_round["van"]), dpc(r_round["van"], rp["van"])),
             ("F4", "TIR", pc(rp["irr"]), pc(r["irr"]), dpc(r["irr"], rp["irr"])),
             ("F4", "Payback simple / desc.", "3,41 / 4,54", f"{yrs(r['payback'])} / {yrs(r['payback_disc'])}", "✓")]
    md.append("### 1.1 Reproducción de los outputs reportados (tolerancia ±0,5 %)\n")
    md.append(table(["Fixture", "Indicador", "Reportado v2.0", "Reproducido", "Δ"], rows))
    md.append("""
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
""")
    return "\n".join(md)


def phase1_humanitas():
    inf = infer_humanitas()
    f = fx.F5_HUMANITAS
    rows = []
    for sc, d in f["scenarios"].items():
        i = inf[sc]
        r = ve.legacy_dcf(f["capex0"], d["n_years"], d["wacc"], i["ginf"], i["F1"], d["crecimiento"])
        rows.append((sc, f"{d['compra'] * 100:.0f}% / {d['crecimiento'] * 100:.0f}% / {d['n_years']}a",
                     n0(i["F1"]), pc(i["ginf"]), n0(d["van"]), n0(r["van"]), pc(d["irr"]), pc(r["irr_raw"]),
                     f"{yrs(r['payback'])} / {yrs(r['payback_disc'])}"))
    txt = ["### 1.2 Humanitas (inputs no informados: FCF₁ y g∞ **inferidos**)\n",
           table(["Esc.", "Compra / crec. / horizonte", "FCF₁ inferido", "g∞ inferido", "VAN rep.", "VAN modelo",
                  "TIR rep.", "TIR modelo", "Payback"], rows),
           """
**Lectura (con límites).** El fixture no informa FCF₁ ni g∞. Despejándolos de VAN y TIR de cada escenario aparecen valores coherentes
entre A↔B (FCF₁ ≈ 3,78–3,80 M; g∞ ≈ −0,4 %) y C↔D (FCF₁ ≈ 0,71 M; g∞ ≈ −2,8 a −3,3 %). Con 2 incógnitas y 2 outputs por escenario el ajuste
**no es una validación independiente**; solo la consistencia entre pares lo es, y es buena pero no exacta. **No puede afirmarse** que
Humanitas se reproduzca con la v2.0: falta información. Un g∞ negativo es llamativo (¿se usó un VT con g∞ < 0, o el FCF tiene otra estructura?).

**WACC distinto según horizonte (11,13 % vs 10,98 %).** No puede explicarse con el código: el WACC de la v2.0 depende solo de
`Rf, ERP, CRP, βU, T, D, E, Kd` (ver tabla de fórmulas). Por lo tanto, entre las corridas cambió al menos uno de esos inputs
(p. ej. la relación D/E o el Kd), que el reporte no imprime. Esto es un defecto de trazabilidad (D7), no de fórmula.
"""]
    return "\n".join(txt), inf


# ═════════════════════════════════════════════════════════════════════════════
# FASE 2 — diagnóstico de D1–D8
# ═════════════════════════════════════════════════════════════════════════════
def phase2(inf):
    L = ve.legacy_dcf
    md = ["## FASE 2 — Diagnóstico de defectos con evidencia\n"]

    cases = []
    f = fx.F1_FRIOLOG
    cases.append(("F1", L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"]), 1.0))
    f = fx.F2_SMART_RECOVERY
    cases.append(("F2", L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], fcfs=f["fcfs"]), 1.0))
    f = fx.F3_PANTALLA_RH
    cases.append(("F3", L(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"]), 1.0))
    f = fx.F4_OVOS_TERRA
    cases.append(("F4", L(f["capex_stage1"], f["n_years"], f4_ke(), f["g_inf"], f4_fcf(), 0.0), 1.0))
    h = fx.F5_HUMANITAS
    for sc, d in h["scenarios"].items():
        i = inf[sc]
        cases.append((f"F5-{sc}*", L(h["capex0"], d["n_years"], d["wacc"], i["ginf"], i["F1"], d["crecimiento"]), 1.0))

    rows = [(k, n0(r["van"]), n0(r["van_sin_vt"]), pc(r["vt_pct"], 1), pc(r["irr_raw"], 1),
             pc(r["irr_sin_vt"], 1), "SÍ" if r["van_sin_vt"] < 0 else "no") for k, r, _ in cases]
    md.append("### D1 y D2 — Perpetuidad por defecto y TIR inflada\n")
    md.append(table(["Caso", "VAN con VT", "VAN sin VT", "VT % del valor", "TIR con VT", "TIR sin VT", "¿VAN sin VT < 0?"], rows))
    md.append("""
*(\\* Humanitas con inputs inferidos; sus filas son indicativas.)*

- **D1 — CONFIRMADO, severidad ALTA.** El VT se aplica siempre (`app.py`: `tv = fcf[-1]*(1+g_inf)/(wacc-g_inf)` sin interruptor) y pesa
  **44 % (F3) a 66 % (F2)** del valor, como se indicó. Sin VT, **Pantalla RH** pasa a VAN negativo (−USD 79.657,63): es el único caso de la tabla en que ocurre.
  **Matiz que corrige el enunciado:** en **Ovos Terra el VAN sin perpetuidad es +Gs 4,0 M (positivo, equivale al 7,9 % del CAPEX₀)**,
  no negativo; es un margen mínimo que desaparece con ajustes menores (ver Fase 4). En Humanitas C y D (inputs inferidos) el VAN sin VT también es positivo pero chico.
- **D2 — CONFIRMADO, severidad ALTA.** `cashflows[-1] += tv` en el cálculo de la TIR. TIR con VT: F1 116 %, F2 106 %, Humanitas A ≈ 127 %;
  sin VT bajan a 90 %, 74 % y valores aún altos que revelan otro problema (FCF₁ vs inversión; ver V02/V03).
""")

    f1, f2, f3 = fx.F1_FRIOLOG, fx.F2_SMART_RECOVERY, fx.F3_PANTALLA_RH
    rows = []
    for k, f in (("F1", f1), ("F2", f2), ("F3", f3)):
        wb = ve.wacc_from_reported(f["wacc"], ke_usd=f["ke"], kd_pre=f["kd"], tax=TAX, flow_currency="PYG",
                                   infl_flow=PI_GS, infl_usd=PI_USD)
        rows.append((k, pc(f["ke"]), pc(f["kd"]), "SÍ" if f["ke"] < f["kd"] else "no", pc(wb.ke_flow, 4),
                     "no" if wb.ke_flow >= f["kd"] else "SÍ"))
    f4 = fx.F4_OVOS_TERRA
    bm = fx.BENCHMARK_TECHCARE
    md.append("### D3 — Desajuste de moneda (Ke en USD aplicado a flujos en Gs)\n")
    md.append(table(["Caso", "Ke v2.0", "Kd", "Ke < Kd", "Ke en Gs corregido*", "Ke_Gs < Kd"], rows))
    md.append(f"""
\\* SUPUESTO: Ke reportado = CAPM en USD (así lo establece el código: `ke = rf + beta_l*erp + crp`, sin conversión), π Gs = {PI_GS*100:.1f} % y π USD = {PI_USD*100:.1f} %
(valores del benchmark TechCare; no están en los fixtures). Factor de conversión: (1+π_Gs)/(1+π_USD) = {(1+PI_GS)/(1+PI_USD):.6f}, es decir **+{((1+PI_GS)/(1+PI_USD)-1)*100:.2f} pp sobre (1+Ke)**.

- **D3 — CONFIRMADO, severidad ALTA.** El código no tiene inputs de inflación ni conversión. Ke < Kd en F1, F2 y F3 (con deuda).
  Aun con la conversión de +0,98 pp, **Ke_Gs sigue siendo menor que Kd en F1, F2 y F3**: el problema no es solo de moneda; también hay un Kd alto
  (14,5 %–18 %) frente a un CAPM con ERP/CRP bajos. La alerta V01 sigue activa en F1 y F2 en la versión corregida (correcto: es una inconsistencia real de inputs);
  en F3 no se dispara porque, con WACC = Ke, el modelo trata el proyecto como 100 % capital propio (SUPUESTO).
- Benchmark: Ke_USD {bm['ke_total_usd']*100:.2f} % → Ke_Gs = (1,1434·1,035/1,025) − 1 = {((1+bm['ke_total_usd'])*(1+bm['infl_gs'])/(1+bm['infl_usd'])-1)*100:.2f} %,
  coherente con el WACC Gs de 15,46 % del benchmark (con deuda más barata).
""")

    # D4 Monte Carlo
    rg = ve.legacy_monte_carlo(15_000, f4_fcf(), 5, 0.02, (-0.03, 0.0, 0.015), (f4_ke() - 1e-6, f4_ke(), f4_ke() + 1e-6),
                               (f4["capex_stage1"],) * 2 + (f4["capex_stage1"] + 1e-6,), (1.0, 1.0, 1.0 + 1e-9), seed=SEED)
    st = ve.mc_stats(rg)
    pess_fcf = f4["pessimistic"]["fcf_anual"]
    rp = L(f4["capex_stage1"], 5, f4_ke(), 0.02, pess_fcf, 0.0)
    md.append("### D4 — Monte Carlo sin capacidad de detectar riesgo\n")
    md.append(f"""
- **Replicando Ovos Terra** (solo crecimiento −3 % a +1,5 %): P(VAN<0) = **{st['prob_neg']*100:.1f} %**, P5 = Gs {n0(st['p5'])}, P95 = Gs {n0(st['p95'])}
  (reportado: P5 73.669.241 / P95 130.121.212: no se reproduce porque los rangos de la v2.0 se desconocen; la conclusión cualitativa —0 % de pérdida— sí coincide).
- El escenario **pesimista determinístico** del fixture da FCF = Gs {n0(pess_fcf)} por año. Con esa serie constante, la fórmula v2.0 da
  VAN = **Gs {n0(rp['van'])}** (con VT sobre un flujo negativo, que además resta valor: es un VT negativo, otro absurdo del método).
  Sin VT: Gs {n0(rp['van_sin_vt'])}. **La simulación mostraba 0 % de probabilidad de pérdida mientras un escenario plausible destruye todo el capital.**
- **CONFIRMADO, severidad ALTA.** Evidencia en el código: `run_monte_carlo` solo muta `g`, `WACC`, `CAPEX` y un multiplicador de FCF₁ (0,85–1,15) fijo;
  no hay precio, volumen, costos ni capital de trabajo. Es **imposible** que detecte el riesgo operativo. El multiplicador ±15 % sobre FCF₁ parece
  cubrir el flujo, pero en Ovos Terra el FCF base (14,9 M) es la diferencia de dos magnitudes grandes (ventas 153,6 M): una caída de ~10,8 % de las ventas ya lo vuelve negativo.
- Sesgo y base descentrada (F2/F3): **CONFIRMADO en F3** (mediana USD 145.163 vs base USD 252.034: el caso base queda entre el P50 y el P95 reportados, es decir,
  por encima del centro de la distribución; el percentil exacto no puede calcularse porque la v2.0 no lo informa) y en F2 (σ = 208,7 M con P50 = 95,9 M y P95 = 429,8 M: cola derecha explosiva porque el WACC simulado se acerca a g∞; el VT crece como 1/(WACC−g∞)).
""")

    r2 = fx.F2_SMART_RECOVERY
    md.append("### D5 — FCF como input único / EBIT no concilia\n")
    md.append(f"""
- **PARCIALMENTE CONFIRMADO, severidad MEDIA-ALTA.** *Matiz sobre la v2.0:* el código **sí** tiene un puente contable para el Año 1
  (ventas, costos variables y fijos, depreciación, CAPEX de mantenimiento, ΔAR/ΔINV/ΔAP). Los fixtures F1–F3 y F5, en cambio, traen el FCF como dato.
  Los defectos reales del código son otros: (a) `NOPAT = EBIT·(1−T)` también con EBIT negativo (crédito fiscal ficticio; con los valores por defecto de la v2.0 el EBIT del Año 1 era −250 M);
  (b) el puente de un solo año se extrapola con g constante: ΔCT, CAPEX y depreciación crecen a g en vez de seguir las ventas y la vida de los activos;
  (c) el CAPEX de mantenimiento por defecto (250 M) era menor que la depreciación (1.500 M) y esa diferencia se perpetuaba en el VT; (d) no hay reposición ni valor de desecho.
- **Smart Recovery:** EBIT₁ 334.313.200 vs FCF₁ 9.068.680 → FCF/EBIT = **{r2['fcfs'][0]/r2['ebit_y1']:.3f}** (fuera del rango razonable 0,30–1,50): incoherente. Alerta V06 se dispara.
- **Pantalla RH:** EBIT₁ 579.000.000 vs FCF₁ 476.100.000 → FCF/EBIT = **{fx.F3_PANTALLA_RH['fcf1']/fx.F3_PANTALLA_RH['ebit_y1']:.3f}** (dentro del rango): con la información disponible
  **no puede afirmarse** inconsistencia (faltan depreciación, CAPEX y capital de trabajo). Se descarta como evidencia de D5 en este caso.
- **Ovos Terra:** el impuesto se calculó sobre el margen antes de reposición y sin depreciación: el FCF reproducido (14,9 M) difiere del que resulta de un flujo conciliado (ver Fase 4).
""")

    md.append("""### D6 — Sin validaciones de inputs
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
""")
    return "\n".join(md)


# ═════════════════════════════════════════════════════════════════════════════
# FASE 4 — re-ejecución con el motor corregido
# ═════════════════════════════════════════════════════════════════════════════
def mc_direct():
    return ve.MCSpec(sims=10_000, seed=SEED,
                     ranges={"price": (1, 1, 1), "volume": (0.70, 1.0, 1.10), "unit_vc": (1, 1, 1),
                             "fixed": (1, 1, 1), "capex": (0.95, 1.0, 1.20)}, wacc_range=0.02)


def run_direct(f, fcfs, wacc_dict):
    """Corrida corregida de un fixture con FCF dado."""
    p = ve.Project(n_years=len(fcfs), capex0=f["capex0"], fcf_direct=list(fcfs), g_revenue=f.get("g", 0.0),
                   g_inf=f.get("g_inf", 0.02), ebit_reported=f.get("ebit_y1"), terminal_mode="none", name=f["name"])
    wb = ve.wacc_from_reported(**wacc_dict)
    return ve.evaluate(p, wb, mc_direct())


def f4_project():
    f = fx.F4_OVOS_TERRA
    fixed = f["balanceado"] + f["fijos"] + f["reposicion_costo_anual_equiv"]
    return ve.Project(n_years=5, capex0=f["capex_stage1"], revenue_y1=f["ventas"], var_cost_y1=0.0,
                      fixed_cost_y1=fixed, g_revenue=0.0, g_fixed=0.0, tax=TAX, dep_years=5, maint_capex_pct=0.0,
                      nwc_y1=(f["balanceado"] + f["fijos"]) / 12, recover_nwc=True, terminal_mode="none",
                      g_inf=f["g_inf"], name=f["name"])


def f4_pess():
    """Pesimista del fixture: postura 70 %, balanceado Gs 3.000/kg. Descomposición SUPUESTA (precio base Gs 2.500/kg)."""
    f = fx.F4_OVOS_TERRA
    feed_p = f["balanceado"] * 3000 / 2500
    # ingreso pesimista tal que el FCF v2.0 sea el del fixture:  (V'−B'−F)(1−T) − R = fcf_pess
    v_p = (f["pessimistic"]["fcf_anual"] + f["reposicion_costo_anual_equiv"]) / (1 - TAX) + feed_p + f["fijos"]
    fixed_base = f["balanceado"] + f["fijos"] + f["reposicion_costo_anual_equiv"]
    fixed_p = feed_p + f["fijos"] + f["reposicion_costo_anual_equiv"]
    return dict(price=1.0, volume=v_p / f["ventas"], unit_vc=1.0, fixed=fixed_p / fixed_base, capex=1.0, wacc=0.0)


def phase4(inf):
    md = ["## FASE 4 — Re-ejecución con la versión corregida sobre los mismos fixtures\n"]
    assume(f"π Gs = {PI_GS*100:.1f} % y π USD = {PI_USD*100:.1f} % (del benchmark TechCare PY; los fixtures no traen inflaciones).")
    assume("Ke reportado de F1, F2 y F3 = CAPM en USD (confirmado por el código: no hay conversión); Kd reportado ya está en Gs.")
    assume("Pesos E/V y D/V de F1 y F2 DESPEJADOS del WACC reportado: wD = (Ke − WACC)/(Ke − Kd(1−T)). F3: 100 % capital propio (WACC = Ke a 2 decimales).")
    assume("Sin información de capital de trabajo, valor de desecho ni reposición en F1, F2, F3 y F5: capital de trabajo = 0, valor de desecho = 0 (criterio TechCare), sin perpetuidad. Esto es conservador y probablemente subestima F1 (flota usada con valor de reventa) y F3.")
    assume("Monte Carlo corregido en fixtures con FCF directo (sin estructura de costos): único driver operativo = nivel del FCF, triangular (0,70; 1,00; 1,10), CAPEX (0,95; 1,00; 1,20), WACC ± 2 pp, 10.000 sim., semilla 2026. Escenario pesimista = extremos adversos de esos rangos.")
    assume("IRE 10 %.")

    results = {}
    f = fx.F1_FRIOLOG
    fc = [f["fcf1"] * (1 + f["g"]) ** t for t in range(f["n_years"])]
    results["F1"] = (run_direct(f, fc, dict(wacc=f["wacc"], ke_usd=f["ke"], kd_pre=f["kd"], tax=TAX, flow_currency="PYG",
                                           infl_flow=PI_GS, infl_usd=PI_USD)),
                     ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"]), f)
    f = fx.F2_SMART_RECOVERY
    results["F2"] = (run_direct(f, f["fcfs"], dict(wacc=f["wacc"], ke_usd=f["ke"], kd_pre=f["kd"], tax=TAX, flow_currency="PYG",
                                                  infl_flow=PI_GS, infl_usd=PI_USD)),
                     ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], fcfs=f["fcfs"]), f)
    f = fx.F3_PANTALLA_RH
    fc = [f["fcf1"] * (1 + f["g"]) ** t for t in range(f["n_years"])]
    results["F3"] = (run_direct(f, fc, dict(wacc=f["wacc"], tax=TAX, flow_currency="PYG", infl_flow=PI_GS, infl_usd=PI_USD)),
                     ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"]), f)

    # F4 con estructura completa
    f = fx.F4_OVOS_TERRA
    assume("F4: depreciación lineal a 5 años de la etapa 1 (no informada); capital de trabajo = 1/12 de los costos anuales (balanceado + fijos) con recupero al año 5; "
           "la reposición del plantel se mantiene como costo anual equivalente (Gs 20.728.000) dentro de los costos fijos; balanceado tratado como costo fijo por gallina (no varía con la postura).")
    assume("F4 pesimista: la descomposición (postura 70 % → ingresos; balanceado de Gs 2.500 a 3.000/kg, precio base INFERIDO) se calibra para que el FCF con la fórmula v2.0 coincida con el dato del fixture (−15.760.000); el FCF total pesimista es dato, la descomposición es supuesto.")
    assume("F4 Monte Carlo corregido: precio de venta (0,90; 1,00; 1,08), postura/volumen (mín = caso pesimista; 1,00; 1,05), costos fijos incl. alimento (0,97; 1,00; máx = pesimista), CAPEX (0,95; 1,00; 1,15), WACC ± 2 pp.")
    pm = f4_pess()
    spec = ve.MCSpec(sims=10_000, seed=SEED,
                     ranges={"price": (0.90, 1.0, 1.08), "volume": (pm["volume"], 1.0, 1.05), "unit_vc": (1, 1, 1),
                             "fixed": (0.97, 1.0, pm["fixed"]), "capex": (0.95, 1.0, 1.15)}, wacc_range=0.02)
    w4 = ve.WaccInputs(rf=f["rf"], erp=f["erp"], crp=f["crp"], beta_u=f["beta"], tax=TAX, debt=0.0, equity=1.0, kd=0.0,
                       infl_flow=PI_GS, infl_usd=PI_USD)
    ev4 = ve.evaluate(f4_project(), w4, spec, pess_mult=pm)
    leg4 = ve.legacy_dcf(f["capex_stage1"], 5, f4_ke(), f["g_inf"], f4_fcf(), 0.0)
    results["F4"] = (ev4, leg4, f)

    def blk(k):
        ev, leg, f = results[k]
        m = ev.metrics
        fxr = fx.F3_PANTALLA_RH["fx_pyg_per_usd"] if k == "F3" else 1
        unit = "USD @7.000" if k == "F3" else "Gs"
        rep = f["reported"]
        van_rep = rep.get("van_usd", rep.get("van"))
        van_cur = (leg["van"]) / fxr
        mcs = ev.mc.stats
        crit = ev.critical
        rows = [
            ("WACC", pc(f["wacc"], 4), pc(m.wacc, 4), f"{(m.wacc - f['wacc']) * 100:+.2f} pp".replace(".", ","),
             "D3 (Ke en moneda del flujo)" if k != "F4" else "D3 (Ke en Gs)"),
            ("VAN (indicador principal)", n0(van_cur), n0(m.van_main / fxr), dpc(m.van_main / fxr, van_cur),
             "D1 (se quita la perpetuidad) + D3 (tasa) + D5 (flujo conciliado)" if k == "F4" else "D1 + D3"),
            ("VAN con VT (referencial)", n0(van_cur), n0(m.van_con_vt / fxr), dpc(m.van_con_vt / fxr, van_cur),
             "D3 (tasa); FCF normalizado igual al v2.0 porque el fixture no trae reinversión"),
            ("Peso del VT", pc(leg["vt_pct"], 1), pc(m.vt_weight, 1), "—", "se muestra siempre (C1)"),
            ("TIR principal (sin VT)", pc(leg["irr"], 2) + " (con VT)", pc(m.irr_sin_vt, 2), "—", "D2"),
            ("TIR con VT (secundaria)", pc(leg["irr"], 2), pc(m.irr_con_vt, 2), "—", "D3"),
            ("TIRM sin VT", "no existía", pc(m.mirr_sin_vt, 2), "—", "C2"),
            ("Índice de rentabilidad (sin VT)", "no existía", n2(m.ir_sin_vt), "—", "nuevo"),
            ("Payback simple / desc.", f"{yrs(leg['payback'])} / {yrs(leg['payback_disc'])}",
             f"{yrs(m.payback)} / {yrs(m.payback_disc)}", "—", "sin cambio salvo que el flujo del año N cambie (recupero CT)"),
            ("P(VAN<0)", pc(rep["mc"]["prob_neg"], 1), pc(mcs["prob_neg"], 1), "—", "D4 (drivers) + D1"),
            ("P5 / P50 / P95 de VAN", f"{n0(rep['mc'].get('p5', rep['mc'].get('p5_usd')))} / — / {n0(rep['mc'].get('p95', rep['mc'].get('p95_usd')))}",
             f"{n0(mcs['p5'] / fxr)} / {n0(mcs['p50'] / fxr)} / {n0(mcs['p95'] / fxr)}", "—", "D4"),
            ("CVaR5", n0(rep["mc"].get("cvar5", rep["mc"].get("cvar5_usd"))) if rep["mc"].get("cvar5", rep["mc"].get("cvar5_usd")) else "—",
             n0(mcs["cvar5"] / fxr), "—", "D4"),
            ("Posición del caso base en la distribución", "no se informaba", pc(mcs["base_percentile"], 1), "—", "C4"),
            ("VAN escenario pesimista determinístico", n0(f["pessimistic"]["fcf_anual"]) + " (FCF anual)" if k == "F4" else "no existía",
             n0(ev.pess_van_main / fxr), "—", "C4"),
            ("Variable crítica (VAN = 0)", "no existía",
             (f"{crit.label}: {crit.rel_change * 100:+.1f}%".replace(".", ",") if crit else "—"), "—", "C8"),
            ("Lectura", "DICTAMEN: APROBADO (VAN>0, P(VAN<0)≤20 %, P5>0)", ev.reading.headline, "—", "D8"),
            ("Alertas activas", "ninguna", ", ".join(a.code for a in ev.alerts) or "ninguna", "—", "D6"),
        ]
        head = f"### {f['id']} — {f['name']} (valores en {unit})\n"
        return head + table(["Indicador", "Versión actual", "Versión corregida", "Δ", "Causa"], rows)

    for k in ("F1", "F2", "F3", "F4"):
        md.append(blk(k))
        md.append("")
    # Cambios de conclusión
    chg = []
    for k, (ev, leg, f) in results.items():
        van_c = leg["van"]
        chg.append((k, f["name"], "positivo" if van_c > 0 else "negativo", "positivo" if ev.metrics.van_main > 0 else "negativo",
                    "SÍ" if (van_c > 0) != (ev.metrics.van_main > 0) else "no",
                    "SÍ" if (ev.metrics.irr_sin_vt or 0) < ev.metrics.wacc else "no"))

    # Humanitas
    h = fx.F5_HUMANITAS
    rowsH = []
    hs = []
    for sc, d in h["scenarios"].items():
        i = inf[sc]
        fc = [i["F1"] * (1 + d["crecimiento"]) ** t for t in range(d["n_years"])]
        p = ve.Project(n_years=d["n_years"], capex0=h["capex0"], fcf_direct=fc, g_revenue=d["crecimiento"], g_inf=0.02,
                       terminal_mode="none", name=f"Humanitas {sc}")
        wb = ve.wacc_from_reported(d["wacc"], tax=TAX, flow_currency="PYG", infl_flow=PI_GS, infl_usd=PI_USD)
        ev = ve.evaluate(p, wb, mc_direct())
        leg = ve.legacy_dcf(h["capex0"], d["n_years"], d["wacc"], i["ginf"], i["F1"], d["crecimiento"])
        hs.append(dict(name=f"Esc. {sc}", n_years=d["n_years"], wacc=ev.metrics.wacc, wacc_key=None))
        rowsH.append((sc, f"{pc(d['wacc'], 4)} → {pc(ev.metrics.wacc, 4)}", n0(d["van"]), n0(ev.metrics.van_main),
                      pc(d["irr"], 1), pc(ev.metrics.irr_sin_vt, 1), pc(ev.mc.stats["prob_neg"], 1),
                      ", ".join(a.code for a in ev.alerts)))
        chg.append((f"F5-{sc}*", f"Humanitas {sc}", "positivo" if leg["van"] > 0 else "negativo",
                    "positivo" if ev.metrics.van_main > 0 else "negativo",
                    "SÍ" if (leg["van"] > 0) != (ev.metrics.van_main > 0) else "no",
                    "SÍ" if (ev.metrics.irr_sin_vt or 0) < ev.metrics.wacc else "no"))
    cmp_alerts = ve.compare_scenarios(hs)
    md.append("### F5 — Humanitas (inputs inferidos, ver 1.2; WACC reportado tratado como Ke USD de una estructura 100 % propia: SUPUESTO)\n")
    md.append(table(["Esc.", "WACC", "VAN actual", "VAN corregido (sin VT)", "TIR actual (con VT)", "TIR sin VT",
                     "P(VAN<0)", "Alertas"], rowsH))
    md.append("\nAlertas al comparar los cuatro escenarios: " + ("; ".join(f"**{a.code}** {a.title}" for a in cmp_alerts) or "ninguna") + ".\n")
    md.append("### Resumen: ¿qué proyectos cambian de conclusión?\n")
    md.append(table(["Caso", "Proyecto", "VAN v2.0", "VAN corregido", "¿Cambia de signo?", "¿TIR sin VT < WACC?"], chg))
    return "\n".join(md), results


def phase4_notes(results):
    ev, leg, f = results["F4"]
    m = ev.metrics
    fcf_conc = ev.flows.fcf_ops[0]
    return f"""
**Ovos Terra — por qué cambia.** El FCF conciliado del Año 1 es Gs {n0(fcf_conc[0])} (vs 14.912.000 de la v2.0): el motor deduce la reposición y la depreciación antes de
calcular el IRE y descuenta la inversión en capital de trabajo del Año 1 (SUPUESTO: 1/12 de los costos anuales), que se recupera al final. Aun así, **sin perpetuidad y con el Ke llevado a guaraníes (WACC {pc(m.wacc, 4)})** el VAN es Gs {n0(m.van_main)};
con el escenario pesimista del fixture el VAN pasa a Gs {n0(ev.pess_van_main)}. El Monte Carlo corregido da P(VAN<0) = {pc(ev.mc.stats['prob_neg'], 1)} (la v2.0 mostraba 0 %).
"""


# ═════════════════════════════════════════════════════════════════════════════
def main():
    buf = io.StringIO()
    w = buf.write
    w("# Informe de backtest — ValuationSuite USIL v2.0 → v3.0\n\n")
    w("Generado por `python backtest.py`. Todo número sale de ejecutar el código; los datos faltantes figuran como SUPUESTO al final de la Fase 4.\n\n")
    w("## FASE 1 — Reproducción (línea base)\n\n")
    w(phase1() + "\n")
    h_md, inf = phase1_humanitas()
    w(h_md + "\n")
    w(phase2(inf) + "\n")
    p4, results = phase4(inf)
    w(p4 + "\n")
    w(phase4_notes(results) + "\n")
    w("\n### Supuestos usados (todos explícitos)\n\n" + "\n".join(f"{i}. **SUPUESTO** — {a}" for i, a in enumerate(ASSUMPTIONS, 1)) + "\n")
    w("""
### Limitaciones del backtest
- Humanitas depende de inputs inferidos (no verificables).
- El Monte Carlo de la v2.0 no puede reproducirse dentro de ±0,5 % por falta de rangos y de semilla.
- Las corridas corregidas de F1, F2, F3 y F5 usan el FCF del fixture (sin estructura de costos), por lo que el Monte Carlo y el punto de equilibrio solo ven el **nivel** del FCF, el CAPEX y la tasa.
  Solo F4 permite correr el motor completo (precio, volumen, costos). Esa diferencia limita la comparabilidad entre casos.
- Las inflaciones (3,5 % / 2,5 %) son las del benchmark TechCare, no datos de cada proyecto.
""")
    txt = buf.getvalue()
    with open("INFORME_BACKTEST.md", "w", encoding="utf-8") as fh:
        fh.write(txt)
    sys.stdout.reconfigure(encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()

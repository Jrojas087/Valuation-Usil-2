# app.py — ValuationSuite USIL v2.0
# Dashboard DCF · Monte Carlo · Análisis de Sensibilidad
# Monedas: PYG (Guaraní) y USD (Dólar) · Export PDF/TXT · MBA Proyectos de Inversión

import io
from datetime import date

import numpy as np
import numpy_financial as npf
import plotly.graph_objects as go
import streamlit as st

import report_usil as rep

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ValuationSuite USIL — Evaluación Financiera",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS premium dark
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
  --bg0:#050914; --bg1:#071026; --card:#0b1733; --card2:#0d1b3d;
  --line:rgba(255,255,255,.08); --text:#eaf1ff; --muted:rgba(234,241,255,.72);
  --accent:#66a9ff; --good:#27d17c; --warn:#ffcc66; --bad:#ff5d5d;
}
html, body, [class*="stApp"] {
  background: radial-gradient(1200px 700px at 20% 0%, #0a1736 0%, var(--bg0) 55%, #04070f 100%) !important;
  color: var(--text) !important;
}
h1,h2,h3,h4,h5,h6,p,div,span,label { color: var(--text); }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--bg1), #050914) !important;
  border-right: 1px solid var(--line);
}
[data-testid="stMetric"] {
  background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
  border: 1px solid var(--line); padding: 14px; border-radius: 14px;
}
.block-container { padding-top: 1.2rem; }
hr { border-color: var(--line); }
.card {
  background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
  border: 1px solid var(--line); border-radius: 18px; padding: 18px;
  box-shadow: 0 10px 30px rgba(0,0,0,.25);
}
.card h3 { margin: 0 0 8px 0; font-size: 1.05rem; }
.small { color: var(--muted); font-size: .88rem; }
.pill {
  display:inline-block; padding: 6px 14px; border-radius: 999px;
  border: 1px solid var(--line); background: rgba(102,169,255,.10);
  font-weight: 700; letter-spacing: .02em;
}
.pill.good { background: rgba(39,209,124,.14); }
.pill.warn { background: rgba(255,204,102,.14); }
.pill.bad  { background: rgba(255,93,93,.14); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Selección de moneda (PYG / USD)
# ─────────────────────────────────────────────────────────────────────────────
_CURR_OPTIONS = {
    "PYG 🇵🇾  Guaraní Paraguayo": ("Gs.", 0),
    "USD 🇺🇸  Dólar Estadounidense": ("$", 2),
}
_curr_sel  = st.sidebar.selectbox("💱 Moneda del proyecto", list(_CURR_OPTIONS.keys()), index=0)
_sym, _dec = _CURR_OPTIONS[_curr_sel]
CURRENCY   = _curr_sel.split()[0]   # "PYG" o "USD"

# Valores por defecto según moneda
_IS_PYG = (CURRENCY == "PYG")
_DEF = {
    "capex0":    3_500_000_000.0   if _IS_PYG else 1_000_000.0,
    "step_big":  50_000_000.0      if _IS_PYG else 50_000.0,
    "step_med":  100_000_000.0     if _IS_PYG else 100_000.0,
    "step_sm":   25_000_000.0      if _IS_PYG else 25_000.0,
    "step_wc":   10_000_000.0      if _IS_PYG else 10_000.0,
    "debt":      2_000_000_000.0   if _IS_PYG else 600_000.0,
    "equity":    3_000_000_000.0   if _IS_PYG else 900_000.0,
    "sales":     10_000_000_000.0  if _IS_PYG else 3_000_000.0,
    "cvar":      6_000_000_000.0   if _IS_PYG else 1_800_000.0,
    "cfix":      2_750_000_000.0   if _IS_PYG else 825_000.0,
    "dep":       1_500_000_000.0   if _IS_PYG else 450_000.0,
    "capex_y1":  250_000_000.0     if _IS_PYG else 75_000.0,
    "d_ar":      90_000_000.0      if _IS_PYG else 27_000.0,
    "d_inv":     80_000_000.0      if _IS_PYG else 24_000.0,
    "d_ap":      30_000_000.0      if _IS_PYG else 9_000.0,
}

def fmt_money(x) -> str:
    try:
        v = float(x)
        if not np.isfinite(v):
            return "—"
    except Exception:
        return "—"
    if _dec == 0:
        # PYG: punto como separador de miles (convención paraguaya)
        return f"{_sym} " + f"{v:,.0f}".replace(",", ".")
    # USD: coma como separador de miles
    return f"{_sym} {v:,.{_dec}f}"

def fmt_pct(x) -> str:
    try:
        v = float(x)
        if not np.isfinite(v):
            return "—"
        return f"{v * 100:.2f}%"
    except Exception:
        return "—"

# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de cálculo
# ─────────────────────────────────────────────────────────────────────────────
MIN_SPREAD = 0.005

def safe_irr(cashflows):
    try:
        irr = float(npf.irr(cashflows))
        if not np.isfinite(irr) or irr < -0.99 or irr > 2.0:
            return None
        return irr
    except Exception:
        return None

def payback_simple(capex0: float, fcfs: np.ndarray):
    cum = -capex0
    for i, f in enumerate(fcfs, 1):
        prev = cum
        cum += f
        if cum >= 0:
            frac = (0 - prev) / f if f != 0 else 0.0
            return float(i - 1 + frac)
    return None

def payback_discounted(capex0: float, fcfs: np.ndarray, wacc: float):
    cum = -capex0
    for i, f in enumerate(fcfs, 1):
        pv = f / (1 + wacc) ** i
        prev = cum
        cum += pv
        if cum >= 0:
            frac = (0 - prev) / pv if pv != 0 else 0.0
            return float(i - 1 + frac)
    return None

def committee_check(npv_base, prob_neg, p50, p5):
    checks = [
        ("VAN base > 0",   npv_base > 0),
        ("P(VAN<0) ≤ 20%", prob_neg <= 0.20),
        ("P50(VAN) > 0",   p50 > 0),
        ("P5(VAN) > 0",    p5 > 0),
    ]
    ok = sum(b for _, b in checks)
    if ok == len(checks): return "APROBADO", checks
    if ok == 0:           return "RECHAZADO", checks
    return "OBSERVADO", checks

# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo (distribuciones triangulares)
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def run_monte_carlo(sims, fcf_y1, n_years, g_inf,
                    g_min, g_mode, g_max,
                    w_min, w_mode, w_max,
                    capex_min, capex_mode, capex_max,
                    fcf_mult_min, fcf_mult_mode, fcf_mult_max):
    rng     = np.random.default_rng()
    g_s     = rng.triangular(g_min, g_mode, g_max, sims)
    w_s     = rng.triangular(w_min, w_mode, w_max, sims)
    capex_s = rng.triangular(capex_min, capex_mode, capex_max, sims)
    mult_s  = rng.triangular(fcf_mult_min, fcf_mult_mode, fcf_mult_max, sims)

    yrs    = np.arange(1, n_years + 1)
    fcf1_s = fcf_y1 * mult_s
    fcf_p  = fcf1_s[:, None] * (1.0 + g_s)[:, None] ** (yrs[None, :] - 1)

    valid = w_s > (g_inf + MIN_SPREAD)
    npv_s = np.full(sims, np.nan)
    idx   = np.where(valid)[0]
    if idx.size:
        fv, wv, cv = fcf_p[idx], w_s[idx], capex_s[idx]
        fv = fv.copy()
        fv[:, -1] += (fv[:, -1] * (1 + g_inf)) / (wv - g_inf)
        npv_s[idx] = np.sum(fv / (1 + wv)[:, None] ** yrs[None, :], axis=1) - cv
    return npv_s

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Inputs
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar.expander("ℹ️ Ayuda — ¿qué ingresar en cada campo?"):
    st.markdown("""
**Sección 0 — CAPEX Año 0**: monto total de la inversión inicial (maquinarias, obras, licencias, etc.)

**Sección 1 — CAPM/WACC**:
- *Rf* = tasa libre de riesgo (ej. bonos del tesoro EE.UU.)
- *ERP* = prima de riesgo del mercado accionario
- *CRP* = prima de riesgo país (Paraguay ≈ 2%)
- *βU* = riesgo del negocio sin deuda (buscar betas por industria en Damodaran)
- *T* = tasa del impuesto a la renta

**Sección 2 — Estructura de capital**:
- *D* = deuda total del proyecto
- *E* = capital propio aportado por los socios
- *Kd* = tasa de interés del préstamo

**Sección 3A — Contable Año 1**: datos del estado de resultados proyectado

**Sección 3B — Proyección**:
- *g explícito* = tasa de crecimiento anual de los flujos durante los N años
- *g perpetuidad* = tasa de crecimiento a largo plazo (generalmente ≈ inflación)

**Sección 4 — Monte Carlo**: rangos de incertidumbre. Los valores por defecto son razonables para un análisis inicial.
""")

st.sidebar.divider()
st.sidebar.header("🧩 Identificación")
project     = st.sidebar.text_input("Proyecto",    "Proyecto ABC")
responsible = st.sidebar.text_input("Responsable", "Docente: Jorge Rojas")

st.sidebar.divider()
st.sidebar.header("0) Inversión inicial")
capex0 = st.sidebar.number_input(
    f"CAPEX Año 0 ({CURRENCY})",
    value=_DEF["capex0"], step=_DEF["step_big"], min_value=1.0,
)

st.sidebar.divider()
st.sidebar.header("1) CAPM / WACC")
rf       = st.sidebar.number_input("Rf (%)",             value=4.5,  step=0.1)  / 100
erp      = st.sidebar.number_input("ERP (%)",            value=5.5,  step=0.1)  / 100
crp      = st.sidebar.number_input("CRP (%)",            value=2.0,  step=0.1)  / 100
beta_u   = st.sidebar.number_input("βU (desapalancada)", value=0.90, step=0.05)
tax_rate = st.sidebar.number_input("Impuesto T (%)",     value=10.0, step=0.5)  / 100

st.sidebar.divider()
st.sidebar.header("2) Estructura de capital")
debt      = st.sidebar.number_input(f"Deuda (D) [{CURRENCY}]",          value=_DEF["debt"],   step=_DEF["step_big"], min_value=0.0)
equity_bk = st.sidebar.number_input(f"Capital propio (E) [{CURRENCY}]", value=_DEF["equity"], step=_DEF["step_big"], min_value=1.0)
kd        = st.sidebar.number_input("Kd (%)",                            value=7.0, step=0.25) / 100

st.sidebar.divider()
st.sidebar.header("3A) Contable Año 1 → FCF₁")
sales_y1 = st.sidebar.number_input(f"Ventas Año 1 [{CURRENCY}]",          value=_DEF["sales"],   step=_DEF["step_med"], min_value=0.0)
cvar_y1  = st.sidebar.number_input(f"Costos variables [{CURRENCY}]",       value=_DEF["cvar"],    step=_DEF["step_med"], min_value=0.0)
cfix_y1  = st.sidebar.number_input(f"Costos fijos [{CURRENCY}]",           value=_DEF["cfix"],    step=_DEF["step_big"], min_value=0.0)
dep_y1   = st.sidebar.number_input(f"Depreciación (no caja) [{CURRENCY}]", value=_DEF["dep"],     step=_DEF["step_big"], min_value=0.0)
capex_y1 = st.sidebar.number_input(f"CAPEX Año 1 (mant.) [{CURRENCY}]",   value=_DEF["capex_y1"],step=_DEF["step_sm"],  min_value=0.0)
st.sidebar.markdown("**Δ Capital de trabajo**")
d_ar  = st.sidebar.number_input(f"Δ AR [{CURRENCY}]",  value=_DEF["d_ar"],  step=_DEF["step_wc"])
d_inv = st.sidebar.number_input(f"Δ INV [{CURRENCY}]", value=_DEF["d_inv"], step=_DEF["step_wc"])
d_ap  = st.sidebar.number_input(f"Δ AP [{CURRENCY}]",  value=_DEF["d_ap"],  step=_DEF["step_wc"])

st.sidebar.divider()
st.sidebar.header("3B) Proyección + perpetuidad")
n_years = int(st.sidebar.slider("Años de proyección (N)", 3, 10, 5))
g_exp   = st.sidebar.number_input("g explícito (%) ciclo 1..N", value=5.0, step=0.25) / 100
g_inf   = st.sidebar.number_input("g perpetuidad (%)",           value=2.0, step=0.10) / 100

st.sidebar.divider()
st.sidebar.header("4) Monte Carlo")
sims         = int(st.sidebar.slider("Simulaciones", 5_000, 60_000, 15_000, 1_000))
st.sidebar.caption("Distribuciones triangulares · RNG interno sin semilla fija.")
g_min_mc     = st.sidebar.number_input("g mín (%)",        value=2.0, step=0.25) / 100
g_mode_mc    = st.sidebar.number_input("g base (%)",       value=5.0, step=0.25) / 100
g_max_mc     = st.sidebar.number_input("g máx (%)",        value=8.0, step=0.25) / 100
wacc_range   = st.sidebar.number_input("WACC rango ± (%)", value=2.0, step=0.25) / 100
capex_min_mc = st.sidebar.number_input(f"CAPEX mín [{CURRENCY}]",  value=max(capex0 * 0.90, 1.0), step=_DEF["step_big"])
capex_mode_mc= st.sidebar.number_input(f"CAPEX base [{CURRENCY}]", value=capex0,              step=_DEF["step_big"])
capex_max_mc = st.sidebar.number_input(f"CAPEX máx [{CURRENCY}]",  value=capex0 * 1.10,       step=_DEF["step_big"])
mult_min     = st.sidebar.number_input("Shock FCF₁ mín",  value=0.85, step=0.01)
mult_mode    = st.sidebar.number_input("Shock FCF₁ base", value=1.00, step=0.01)
mult_max     = st.sidebar.number_input("Shock FCF₁ máx",  value=1.15, step=0.01)

# ─────────────────────────────────────────────────────────────────────────────
# Cálculos determinísticos
# ─────────────────────────────────────────────────────────────────────────────
D, E = float(debt), float(equity_bk)
V    = max(D + E, 1e-9)
wD, wE = D / V, E / V

beta_l = beta_u * (1 + (1 - tax_rate) * (D / max(E, 1e-9)))
ke     = rf + beta_l * erp + crp
wacc   = wE * ke + wD * kd * (1 - tax_rate)

ebit        = sales_y1 - cvar_y1 - cfix_y1 - dep_y1
nopat       = ebit * (1 - tax_rate)
delta_wc    = d_ar + d_inv - d_ap
fcf_y1_calc = nopat + dep_y1 - capex_y1 - delta_wc

years      = np.arange(1, n_years + 1)
fcf_series = fcf_y1_calc * (1 + g_exp) ** (years - 1)

valid_tv = wacc > (g_inf + MIN_SPREAD)
if valid_tv:
    tv       = (fcf_series[-1] * (1 + g_inf)) / (wacc - g_inf)
    pv_fcf   = float(np.sum(fcf_series / (1 + wacc) ** years))
    pv_tv    = float(tv / (1 + wacc) ** n_years)
    npv_base = pv_fcf + pv_tv - capex0
else:
    tv = pv_fcf = pv_tv = npv_base = float("nan")

cashflows = [-capex0] + list(fcf_series)
if np.isfinite(tv):
    cashflows[-1] += float(tv)
irr_base   = safe_irr(cashflows)
irr_spread = (irr_base - wacc) if (irr_base is not None and np.isfinite(wacc)) else None

pb_simple = payback_simple(capex0, fcf_series)
pb_disc   = payback_discounted(capex0, fcf_series, wacc) if np.isfinite(wacc) else None

# ─────────────────────────────────────────────────────────────────────────────
# Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────
w_min_mc  = max(wacc - wacc_range, 0.001)
w_mode_mc = max(wacc, 0.001)
w_max_mc  = max(wacc + wacc_range, 0.001)

npv_s = run_monte_carlo(
    sims, float(fcf_y1_calc), n_years, float(g_inf),
    float(g_min_mc), float(g_mode_mc), float(g_max_mc),
    float(w_min_mc), float(w_mode_mc), float(w_max_mc),
    float(capex_min_mc), float(capex_mode_mc), float(capex_max_mc),
    float(mult_min), float(mult_mode), float(mult_max),
)
valid_rate = float(np.isfinite(npv_s).mean())
npv_valid  = npv_s[np.isfinite(npv_s)]

if npv_valid.size:
    prob_neg = float((npv_valid < 0).mean())
    p5, p50, p95 = np.percentile(npv_valid, [5, 50, 95])
    mean_mc = float(np.mean(npv_valid))
    std_mc  = float(np.std(npv_valid))
    var5    = float(np.percentile(npv_valid, 5))
    cvar5   = float(np.mean(npv_valid[npv_valid <= var5])) if np.any(npv_valid <= var5) else var5
else:
    prob_neg = p5 = p50 = p95 = mean_mc = std_mc = cvar5 = float("nan")

# ─────────────────────────────────────────────────────────────────────────────
# Dictamen del comité
# ─────────────────────────────────────────────────────────────────────────────
if not np.isfinite(npv_base):
    verdict   = "OBSERVADO"
    checks    = [("Consistencia TV (WACC > g∞ + spread)", False)]
    rationale = "La TV no puede calcularse: WACC debe superar g∞ + spread mínimo. Ajustar supuestos."
else:
    verdict, checks = committee_check(float(npv_base), float(prob_neg), float(p50), float(p5))
    rationale = {
        "APROBADO":  ("El proyecto satisface criterios conservadores: creación de valor y downside "
                      "controlado bajo incertidumbre razonable."),
        "RECHAZADO": ("El proyecto no cumple criterios mínimos. Se recomienda rediseñar supuestos "
                      "clave o estructura de inversión antes de avanzar."),
        "OBSERVADO": ("El proyecto muestra potencial, pero requiere reforzar supuestos críticos y "
                      "mitigaciones antes de aprobación final."),
    }[verdict]

# ─────────────────────────────────────────────────────────────────────────────
# Advertencias de validación de inputs
# ─────────────────────────────────────────────────────────────────────────────
if (cvar_y1 + cfix_y1) > sales_y1:
    st.warning("⚠️ Costos operativos (variables + fijos) superan las ventas Año 1. EBIT será negativo.")
if fcf_y1_calc < 0:
    st.warning(f"⚠️ FCF Año 1 calculado es negativo ({fmt_money(fcf_y1_calc)}). Verificar el bridge contable.")
if not valid_tv:
    st.error(f"⛔ WACC ({fmt_pct(wacc)}) no supera g∞ + spread ({fmt_pct(g_inf + MIN_SPREAD)}). Valor terminal inválido.")
if irr_base is not None and irr_base < wacc:
    st.warning(f"⚠️ TIR ({fmt_pct(irr_base)}) < WACC ({fmt_pct(wacc)}): el proyecto destruye valor relativo al costo de capital.")

# ─────────────────────────────────────────────────────────────────────────────
# Header del dashboard
# ─────────────────────────────────────────────────────────────────────────────
st.title("📊 ValuationSuite USIL — One-Pager Ejecutivo")
st.caption(f"DCF · Monte Carlo · Sensibilidad · Moneda: {CURRENCY} · Modelo académico MBA")

with st.expander("🚀 ¿Cómo usar esta aplicación? — Guía rápida para principiantes"):
    st.markdown("""
**Esta herramienta evalúa proyectos de inversión usando técnicas financieras profesionales.**
No necesitás ser experto en finanzas para usarla — solo completar los datos del sidebar izquierdo.

#### Pasos recomendados:

1. **Seleccioná la moneda** del proyecto (PYG o USD) en el selector de arriba del sidebar.

2. **Ingresá los datos básicos** en el sidebar izquierdo:
   - **Sección 0**: ¿Cuánto cuesta arrancar el proyecto? (inversión inicial)
   - **Sección 1**: Parámetros del costo de capital (si no los conocés, podés dejar los valores por defecto para un análisis inicial)
   - **Sección 2**: ¿Cuánto se financia con deuda y cuánto con capital propio?
   - **Sección 3A**: Datos contables del primer año (ventas, costos, depreciación)
   - **Sección 3B**: ¿Cuántos años proyectamos? ¿A qué tasa crece el negocio?
   - **Sección 4**: Monte Carlo (incertidumbre — podés dejar los valores por defecto)

3. **Leé el dictamen automático** (parte superior derecha): APROBADO ✅ / OBSERVADO ⚠️ / RECHAZADO ❌

4. **Revisá los 8 indicadores** en las tarjetas azules. Hacé clic en *"¿Qué significa cada indicador?"* para ver las explicaciones.

5. **Analizá los gráficos**: waterfall (estructura del valor), flujos de caja y distribución del riesgo.

6. **Mirá la tabla de sensibilidad**: muestra qué pasa si las condiciones cambian.

7. **Descargá el reporte** en PDF o TXT para compartir con tu equipo o comité.

---
💡 **Consejo**: Si no sabés qué valor poner en algún campo, dejá el valor por defecto y ajustá después según los datos reales del proyecto.
""")

hL, hR = st.columns([0.78, 0.22], gap="large")
with hL:
    st.markdown(f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:14px;">
        <div>
          <div style="font-size:1.05rem;font-weight:800;letter-spacing:.02em;">
            ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA ({CURRENCY})
          </div>
          <div class="small">Universidad San Ignacio de Loyola (USIL) — MBA — Proyectos de Inversión / Valuation</div>
          <div class="small">Proyecto: <b>{project}</b> &nbsp;|&nbsp; Responsable: <b>{responsible}</b></div>
        </div>
        <div class="small" style="text-align:right;">Fecha: <b>{date.today().isoformat()}</b></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with hR:
    pill_cls = "good" if verdict == "APROBADO" else ("bad" if verdict == "RECHAZADO" else "warn")
    st.markdown(f"""
    <div class="card" style="text-align:center;">
      <div class="small">Dictamen automático</div>
      <div class="pill {pill_cls}" style="font-size:1.1rem;">{verdict}</div>
      <div class="small" style="margin-top:8px;">Checklist + Monte Carlo</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# KPIs — 8 métricas en 2 filas de 4
# ─────────────────────────────────────────────────────────────────────────────
r1c1, r1c2, r1c3, r1c4 = st.columns(4, gap="medium")
r1c1.metric("VAN (base)",    fmt_money(npv_base) if np.isfinite(npv_base) else "—",     "Determinístico")
r1c2.metric("TIR (base)",    fmt_pct(irr_base)   if irr_base is not None else "N/A",    "Determinístico")
r1c3.metric("TIR − WACC",   fmt_pct(irr_spread)  if irr_spread is not None else "N/A", "Spread sobre costo capital")
r1c4.metric("WACC",          fmt_pct(wacc),                                              f"Ke {fmt_pct(ke)} · Kd {fmt_pct(kd)}")

r2c1, r2c2, r2c3, r2c4 = st.columns(4, gap="medium")
r2c1.metric("Payback",         f"{pb_simple:.2f} años" if pb_simple is not None else "N/A", "Simple")
r2c2.metric("Payback (desc.)", f"{pb_disc:.2f} años"   if pb_disc   is not None else "N/A", "Descontado al WACC")
r2c3.metric("P(VAN<0)",        f"{prob_neg*100:.1f}%"  if np.isfinite(prob_neg) else "—",   "Monte Carlo")
r2c4.metric("P50 (VAN)",       fmt_money(p50)           if np.isfinite(p50) else "—",        "Monte Carlo")

# ─── Glosario de indicadores (desplegable) ────────────────────────────────────
with st.expander("📖 ¿Qué significa cada indicador? — Haz clic para ver las explicaciones"):
    st.markdown("""
### Indicadores principales del DCF (Flujo de Caja Descontado)

**💰 VAN — Valor Actual Neto**
> Es la métrica más importante. Responde a la pregunta: *¿cuánto valor crea (o destruye) este proyecto en dinero de hoy?*
> - **VAN > 0** → el proyecto genera más de lo que cuesta. Se crea riqueza. ✅
> - **VAN = 0** → el proyecto apenas cubre su costo de capital. Ni gana ni pierde.
> - **VAN < 0** → el proyecto destruye valor. Se recomienda no invertir. ❌
>
> *Fórmula simplificada:* VAN = Σ (FCF / (1+WACC)ⁿ) + Valor Terminal − Inversión Inicial

---

**📈 TIR — Tasa Interna de Retorno**
> Es la tasa de rentabilidad que genera el proyecto. Se compara con el WACC:
> - **TIR > WACC** → el proyecto rinde más de lo que cuesta financiarlo. ✅
> - **TIR < WACC** → el proyecto no cubre su costo de capital. ❌

---

**📊 TIR − WACC (Spread)**
> Indica cuánto rinde el proyecto *por encima* de su costo de capital.
> - Un spread positivo confirma la creación de valor.
> - Cuanto mayor el spread, más atractivo es el proyecto.

---

**⚖️ WACC — Costo Promedio Ponderado del Capital**
> Es la tasa mínima de retorno que debe generar el proyecto para satisfacer a los inversores y a los bancos.
> Se calcula combinando el costo de la deuda (Kd) y el costo del capital propio (Ke) según la proporción de cada uno.
> - **Ke** = rentabilidad exigida por los accionistas (calculada con el modelo CAPM).
> - **Kd** = tasa de interés de la deuda, ajustada por el beneficio fiscal.

---

**⏱️ Payback (Período de Recupero Simple)**
> Tiempo que tarda el proyecto en recuperar la inversión inicial con los flujos de caja sin descontar.
> - Se expresa en años.
> - No considera el valor del dinero en el tiempo (limitación).

---

**⏱️ Payback Descontado**
> Igual que el payback simple, pero descuenta los flujos al WACC antes de sumarlos.
> Es más conservador y más preciso: tiene en cuenta que el dinero futuro vale menos que el dinero hoy.

---

### Indicadores de riesgo (Monte Carlo)

**🎲 P(VAN < 0) — Probabilidad de pérdida**
> Indica qué porcentaje de los escenarios simulados terminan con un VAN negativo.
> - < 10% → riesgo muy bajo ✅
> - 10–20% → riesgo aceptable (criterio máximo del comité)
> - > 20% → riesgo elevado ⚠️

---

**📉 P5 / P50 / P95 — Percentiles del VAN simulado**
> Resumen de la distribución de resultados en las simulaciones:
> - **P5** = en el 5% de peores escenarios, el VAN sería al menos este valor. (Caso adverso plausible)
> - **P50** = mediana: la mitad de los escenarios tiene VAN superior a este valor. (Caso central)
> - **P95** = en el 5% de mejores escenarios, el VAN alcanzaría este valor. (Caso favorable)

---

**📊 CVaR5 — Valor en Riesgo Condicional al 5%**
> Es el promedio del VAN en el 5% de peores escenarios.
> Mide la severidad del daño en situaciones extremas adversas.

---

### Conceptos del modelo financiero

**🏭 FCF — Flujo de Caja Libre (Free Cash Flow)**
> Dinero que genera el negocio después de pagar todos sus costos operativos, impuestos,
> inversiones de mantenimiento y cambios en capital de trabajo. Es el efectivo disponible
> para remunerar a deudores e inversores.

**📐 Puente Contable → FCF₁**
```
EBIT   = Ventas − Costos Variables − Costos Fijos − Depreciación
NOPAT  = EBIT × (1 − Tasa Impuesto)
FCF₁   = NOPAT + Depreciación − CAPEX mantenimiento − ΔCapital de Trabajo
```

**🔮 TV — Valor Terminal (Perpetuidad)**
> Captura el valor de todos los flujos más allá del horizonte explícito de proyección,
> asumiendo que el negocio continúa creciendo a una tasa constante (g∞) para siempre.
> Fórmula: TV = FCFₙ × (1+g∞) / (WACC − g∞)

**📐 Beta (β)**
> Mide el riesgo de mercado de la empresa comparado con el mercado en general.
> - βU (desapalancada) = riesgo del negocio sin efecto de la deuda.
> - βL (apalancada) = riesgo ajustado por la estructura deuda/capital de la empresa.

**🎯 Monte Carlo — ¿Qué es?**
> Técnica que simula miles de escenarios posibles variando simultáneamente los supuestos
> clave (g de crecimiento, WACC, CAPEX, y FCF₁) dentro de rangos razonables.
> El resultado es una distribución de posibles VAN, que permite evaluar el riesgo de
> forma probabilística en lugar de un único número determinístico.

**📊 Análisis de Sensibilidad — ¿Qué es?**
> Tabla que muestra cómo cambia el VAN al variar el WACC (filas) y el g explícito (columnas).
> Permite ver qué tan robusto es el resultado: si el VAN sigue positivo con WACC más alto
> y crecimiento más bajo, el proyecto es más resistente a condiciones adversas.
""")

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# Fila central: Decisión & supuestos  +  Value Bridge Waterfall
# ─────────────────────────────────────────────────────────────────────────────
colA, colB = st.columns([0.55, 0.45], gap="large")

with colA:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📋 Decisión & supuestos")
    st.write(rationale)
    st.markdown("**Supuestos clave**")
    st.markdown(
        f"- Horizonte: **{n_years} años** + perpetuidad\n"
        f"- g explícito: **{fmt_pct(g_exp)}** &nbsp;·&nbsp; g∞: **{fmt_pct(g_inf)}**\n"
        f"- WACC: **{fmt_pct(wacc)}** &nbsp;·&nbsp; Ke: **{fmt_pct(ke)}** &nbsp;·&nbsp; Kd: **{fmt_pct(kd)}**\n"
        f"- βU: **{beta_u:.2f}** → βL: **{beta_l:.2f}** &nbsp;·&nbsp; T: **{fmt_pct(tax_rate)}**\n"
        f"- CAPEX₀: **{fmt_money(capex0)}** &nbsp;·&nbsp; FCF₁ (calc.): **{fmt_money(fcf_y1_calc)}**"
    )
    st.markdown("**Puente contable → FCF₁**")
    st.markdown(
        f"- EBIT: {fmt_money(ebit)} &nbsp;→&nbsp; NOPAT: {fmt_money(nopat)}\n"
        f"- + Depreciación: {fmt_money(dep_y1)} &nbsp;·&nbsp; − CAPEX mant.: {fmt_money(capex_y1)}\n"
        f"- − ΔCT (AR+INV−AP): {fmt_money(delta_wc)}"
    )
    st.markdown("**Checklist Comité**")
    for label, ok in checks:
        st.write(("✅ " if ok else "❌ ") + label)
    st.markdown("</div>", unsafe_allow_html=True)

with colB:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🏗️ Estructura del valor (Waterfall)")
    if np.isfinite(npv_base):
        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "total"],
            x=["PV FCF\n(ciclo 1..N)", "PV TV\n(perpetuidad)", "− CAPEX₀\n(inversión)", "VAN\n(neto)"],
            y=[pv_fcf, pv_tv, -capex0, 0],
            connector={"line": {"color": "rgba(255,255,255,0.12)", "width": 1}},
            increasing={"marker": {"color": "#27d17c"}},
            decreasing={"marker": {"color": "#ff5d5d"}},
            totals={"marker": {"color": "#66a9ff"}},
            text=[fmt_money(pv_fcf), fmt_money(pv_tv), fmt_money(-capex0), fmt_money(npv_base)],
            textposition="outside",
        ))
        fig_wf.update_layout(
            height=330,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(color="#eaf1ff", size=11),
        )
        fig_wf.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
        st.plotly_chart(fig_wf, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"VAN = **{fmt_money(npv_base)}**")
    else:
        st.warning("TV inválida: ajustar WACC y g∞.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# Fila inferior: FCF proyectados + Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────
colC, colD = st.columns([0.50, 0.50], gap="large")

with colC:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📈 Flujos de caja proyectados (FCF)")
    st.markdown(
        "<div class='small'>Barras: FCF libre por año (verde = positivo, rojo = negativo). "
        "Línea punteada: PV acumulado descontado al WACC.</div>",
        unsafe_allow_html=True,
    )
    bar_colors = ["#27d17c" if f >= 0 else "#ff5d5d" for f in fcf_series]
    cum_pv = (np.cumsum(fcf_series / (1 + wacc) ** years)
              if np.isfinite(wacc) else np.full(len(years), float("nan")))

    fig_fcf = go.Figure()
    fig_fcf.add_trace(go.Bar(
        x=[f"Año {i}" for i in years],
        y=fcf_series.tolist(),
        marker_color=bar_colors,
        name="FCF",
        yaxis="y",
    ))
    fig_fcf.add_trace(go.Scatter(
        x=[f"Año {i}" for i in years],
        y=cum_pv.tolist(),
        mode="lines+markers",
        name="PV acumulado",
        line=dict(color="#66a9ff", width=2, dash="dot"),
        marker=dict(size=6),
        yaxis="y2",
    ))
    fig_fcf.update_layout(
        height=300,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(x=0.02, y=0.98, bgcolor="rgba(0,0,0,0)", font=dict(color="#eaf1ff", size=10)),
        font=dict(color="#eaf1ff"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.07)"),
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        barmode="relative",
    )
    st.plotly_chart(fig_fcf, use_container_width=True, config={"displayModeBar": False})
    if np.isfinite(tv):
        st.caption(f"TV (año {n_years}): {fmt_money(tv)} &nbsp;·&nbsp; PV(TV): {fmt_money(pv_tv)}")
    st.markdown("</div>", unsafe_allow_html=True)

with colD:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎲 Riesgo — Monte Carlo")
    if npv_valid.size:
        st.markdown(
            f"<div class='small'>Sims: <b>{sims:,}</b> · válidas: <b>{valid_rate*100:.1f}%</b> · "
            f"P(VAN&lt;0): <b>{prob_neg*100:.1f}%</b></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='small'>P5/P50/P95: <b>{fmt_money(p5)}</b> / <b>{fmt_money(p50)}</b> / <b>{fmt_money(p95)}</b>"
            f"&nbsp;·&nbsp; σ: <b>{fmt_money(std_mc)}</b> · CVaR5: <b>{fmt_money(cvar5)}</b></div>",
            unsafe_allow_html=True,
        )
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=npv_valid,
            nbinsx=40,
            marker_color="#66a9ff",
            opacity=0.80,
            name="VAN",
        ))
        # Zona negativa sombreada en rojo
        fig_hist.add_vrect(
            x0=float(npv_valid.min()), x1=0,
            fillcolor="rgba(255,93,93,0.08)", line_width=0,
        )
        fig_hist.add_vline(
            x=0, line_color="rgba(255,93,93,0.85)", line_width=1.8,
            annotation_text="VAN=0", annotation_position="top right",
            annotation=dict(font_color="#ff5d5d", font_size=10),
        )
        for pct_val, label in [(p5, "P5"), (p50, "P50"), (p95, "P95")]:
            if np.isfinite(pct_val):
                fig_hist.add_vline(
                    x=float(pct_val), line_dash="dash",
                    line_color="rgba(234,241,255,0.50)", line_width=1.5,
                    annotation_text=label,
                    annotation=dict(font_color="#eaf1ff", font_size=9),
                )
        fig_hist.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(color="#eaf1ff"),
            bargap=0.04,
        )
        fig_hist.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
        fig_hist.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
        st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            "<div class='small'>P5 = adverso plausible · P50 = central · P95 = favorable · "
            "CVaR5 = severidad media del 5% peor.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Monte Carlo sin resultados válidos. Revisar WACC vs g∞.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    "<div class='small' style='text-align:center;margin-top:8px;'>"
    "Uso académico (MBA). Resultados dependen de supuestos; no sustituyen due diligence. "
    "· ValuationSuite USIL v2.0</div>",
    unsafe_allow_html=True,
)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Análisis de Sensibilidad — WACC × g_exp → VAN
# ─────────────────────────────────────────────────────────────────────────────
st.header("🔍 Análisis de Sensibilidad — WACC × g")
st.caption(
    "VAN recalculado variando WACC (filas) y g explícito (columnas). "
    "Verde = VAN > 0 · Rojo = VAN < 0 · Celda con borde azul = caso base determinístico."
)

with st.expander("ℹ️ ¿Cómo leer esta tabla?"):
    st.markdown("""
**La tabla de sensibilidad muestra qué tan robusto es el proyecto ante cambios en dos supuestos clave:**

- **Filas (WACC)**: el costo del capital. Si el WACC sube (tasas de interés más altas, más riesgo), el VAN baja.
- **Columnas (g)**: la tasa de crecimiento anual de los flujos. Si el negocio crece más, el VAN sube.

**Cómo interpretarla:**
- 🟢 **Verde**: el proyecto crea valor (VAN positivo) bajo esa combinación de supuestos.
- 🔴 **Rojo**: el proyecto destruye valor (VAN negativo) bajo esa combinación.
- El color más intenso indica un VAN de mayor magnitud (positiva o negativa).
- La **celda con borde azul** es el caso base (tus supuestos actuales).

**Regla práctica**: Si la mayoría de las celdas son verdes, el proyecto es robusto.
Si muchas celdas son rojas, el proyecto depende mucho de que los supuestos se cumplan exactamente.
""")

WACC_DELTAS  = [-0.030, -0.015, 0.000,  0.015,  0.030]
G_EXP_DELTAS = [-0.020, -0.010, 0.000,  0.010,  0.020]

wacc_labels  = [f"{(wacc + dw) * 100:.1f}%" for dw in WACC_DELTAS]
g_exp_labels = [f"{(g_exp + dg) * 100:.1f}%" for dg in G_EXP_DELTAS]
npv_ref      = abs(float(npv_base)) if np.isfinite(npv_base) and npv_base != 0 else 1.0

sens_rows = []
for dw in WACC_DELTAS:
    row = []
    for dg in G_EXP_DELTAS:
        w = wacc + dw
        g = g_exp + dg
        if w > (g_inf + MIN_SPREAD) and w > 0:
            fs   = fcf_y1_calc * (1 + g) ** (years - 1)
            tv_s = (fs[-1] * (1 + g_inf)) / (w - g_inf)
            npv_ = float(np.sum(fs / (1 + w) ** years) + tv_s / (1 + w) ** n_years - capex0)
        else:
            npv_ = float("nan")
        row.append(npv_)
    sens_rows.append(row)

g_th = "".join(
    f'<th style="padding:7px 12px;text-align:right;color:#66a9ff;font-weight:600;">{lbl}</th>'
    for lbl in g_exp_labels
)
tbody = ""
for ri, (wacc_lbl, row_data) in enumerate(zip(wacc_labels, sens_rows)):
    is_base_row = (ri == 2)
    row_bg = "background:rgba(102,169,255,0.06);" if is_base_row else ""
    tbody += f'<tr style="{row_bg}">'
    tbody += (
        f'<td style="padding:7px 12px;color:#eaf1ff;font-weight:{"700" if is_base_row else "400"};">'
        f'{wacc_lbl}</td>'
    )
    for ci, val in enumerate(row_data):
        is_base_cell = (ri == 2 and ci == 2)
        base_border  = "border:2px solid #66a9ff;" if is_base_cell else ""
        if not np.isfinite(val):
            cs, ct = "background:rgba(255,255,255,0.04);color:#555;", "—"
        elif val > 0:
            alpha = 0.10 + min(val / (npv_ref * 3 + 1), 1.0) * 0.35
            cs = f"background:rgba(39,209,124,{alpha:.2f});color:#27d17c;font-weight:700;"
            ct = fmt_money(val)
        else:
            alpha = 0.10 + min(abs(val) / (npv_ref * 3 + 1), 1.0) * 0.35
            cs = f"background:rgba(255,93,93,{alpha:.2f});color:#ff5d5d;font-weight:700;"
            ct = fmt_money(val)
        tbody += f'<td style="padding:7px 12px;text-align:right;{cs}{base_border}">{ct}</td>'
    tbody += "</tr>"

st.markdown(f"""
<div class="card" style="overflow-x:auto;">
  <table style="width:100%;border-collapse:collapse;font-size:.86rem;">
    <thead>
      <tr>
        <th style="padding:7px 12px;text-align:left;color:#66a9ff;font-weight:600;">WACC \\ g exp</th>
        {g_th}
      </tr>
    </thead>
    <tbody>{tbody}</tbody>
  </table>
  <div class="small" style="margin-top:10px;">
    Filas = WACC base ± 1.5 pp / 3 pp. Columnas = g base ± 1 pp / 2 pp.
    Intensidad del color proporcional a la magnitud del VAN.
  </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Export — TXT + PDF
# ─────────────────────────────────────────────────────────────────────────────
st.header("📥 Export")

onepager = rep.OnePager(
    institution="Universidad San Ignacio de Loyola (USIL)",
    program="Maestría en Administración de Negocios (MBA)",
    course="Proyectos de Inversión / Valuation",
    currency=CURRENCY,
    project=project,
    responsible=responsible,
    report_date=date.today().isoformat(),
    verdict=verdict,
    rationale=rationale,
    npv_base=float(npv_base)  if np.isfinite(npv_base)  else None,
    irr_base=float(irr_base)  if irr_base is not None   else None,
    payback_simple=float(pb_simple)     if pb_simple is not None else None,
    payback_discounted=float(pb_disc)   if pb_disc   is not None else None,
    n_years=int(n_years),
    g_exp=float(g_exp), g_inf=float(g_inf),
    wacc=float(wacc), ke=float(ke), kd=float(kd),
    capex0=float(capex0), fcf1=float(fcf_y1_calc),
    ebit=float(ebit), nopat=float(nopat),
    delta_wc=float(delta_wc), capex_y1=float(capex_y1),
    pv_fcf=float(pv_fcf) if np.isfinite(pv_fcf) else None,
    pv_tv=float(pv_tv)   if np.isfinite(pv_tv)  else None,
    tv=float(tv)          if np.isfinite(tv)      else None,
    sims=int(sims),
    valid_rate=float(valid_rate) if np.isfinite(valid_rate) else None,
    prob_neg=float(prob_neg)     if np.isfinite(prob_neg)   else None,
    p5=float(p5)       if np.isfinite(p5)   else None,
    p50=float(p50)     if np.isfinite(p50)  else None,
    p95=float(p95)     if np.isfinite(p95)  else None,
    mean=float(mean_mc) if np.isfinite(mean_mc) else None,
    std=float(std_mc)   if np.isfinite(std_mc)  else None,
    cvar5=float(cvar5)  if np.isfinite(cvar5)   else None,
    checks=[(a, bool(b)) for a, b in checks],
    fcf_years=[float(x) for x in fcf_series],
)

col_dl1, col_dl2 = st.columns(2, gap="medium")

with col_dl1:
    onepager_txt = rep.build_onepager_text(onepager)
    st.download_button(
        "⬇️ Descargar One-Pager (TXT)",
        data=onepager_txt.encode("utf-8"),
        file_name="one_pager_usil.txt",
        mime="text/plain",
        use_container_width=True,
    )

with col_dl2:
    if rep.REPORTLAB_OK:
        hist_counts, hist_edges = None, None
        if npv_valid.size:
            hist_counts, hist_edges = np.histogram(npv_valid, bins=36)
        pdf_bytes = rep.generate_onepager_pdf(onepager, hist_counts, hist_edges)
        st.download_button(
            "⬇️ Descargar One-Pager (PDF premium)",
            data=pdf_bytes,
            file_name="one_pager_usil.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.info("Para exportar PDF, instalar `reportlab`.")

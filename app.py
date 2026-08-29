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
# CSS premium dark — métricas compactas
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
  border: 1px solid var(--line); padding: 10px 12px; border-radius: 12px;
}
/* Tamaño compacto para valores de métricas */
[data-testid="stMetricValue"] { font-size: 1.05rem !important; line-height: 1.3 !important; }
[data-testid="stMetricLabel"] { font-size: .78rem !important; }
[data-testid="stMetricDelta"] { font-size: .76rem !important; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }
hr { border-color: var(--line); }
.card {
  background: linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02));
  border: 1px solid var(--line); border-radius: 16px; padding: 14px 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,.22);
}
.card h3 { margin: 0 0 6px 0; font-size: .98rem; }
.small { color: var(--muted); font-size: .82rem; }
.pill {
  display:inline-block; padding: 5px 12px; border-radius: 999px;
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
CURRENCY   = _curr_sel.split()[0]

_IS_PYG = (CURRENCY == "PYG")
_DEF = {
    "capex0":   3_500_000_000.0  if _IS_PYG else 1_000_000.0,
    "step_big": 50_000_000.0     if _IS_PYG else 50_000.0,
    "step_med": 100_000_000.0    if _IS_PYG else 100_000.0,
    "step_sm":  25_000_000.0     if _IS_PYG else 25_000.0,
    "step_wc":  10_000_000.0     if _IS_PYG else 10_000.0,
    "debt":     2_000_000_000.0  if _IS_PYG else 600_000.0,
    "equity":   3_000_000_000.0  if _IS_PYG else 900_000.0,
    "sales":    10_000_000_000.0 if _IS_PYG else 3_000_000.0,
    "cvar":     6_000_000_000.0  if _IS_PYG else 1_800_000.0,
    "cfix":     2_750_000_000.0  if _IS_PYG else 825_000.0,
    "dep":      1_500_000_000.0  if _IS_PYG else 450_000.0,
    "capex_y1": 250_000_000.0    if _IS_PYG else 75_000.0,
    "d_ar":     90_000_000.0     if _IS_PYG else 27_000.0,
    "d_inv":    80_000_000.0     if _IS_PYG else 24_000.0,
    "d_ap":     30_000_000.0     if _IS_PYG else 9_000.0,
}

# ─────────────────────────────────────────────────────────────────────────────
# Formateadores
# ─────────────────────────────────────────────────────────────────────────────
def fmt_money(x) -> str:
    """Formato completo con todos los dígitos."""
    try:
        v = float(x)
        if not np.isfinite(v):
            return "—"
    except Exception:
        return "—"
    if _dec == 0:
        return f"{_sym} " + f"{v:,.0f}".replace(",", ".")
    return f"{_sym} {v:,.{_dec}f}"

def fmt_money_short(x) -> str:
    """Formato para tarjetas KPI. PYG: unidades completas. USD: abreviado."""
    try:
        v = float(x)
        if not np.isfinite(v):
            return "—"
    except Exception:
        return "—"
    if _IS_PYG:
        return fmt_money(v)
    sign = "−" if v < 0 else ""
    av = abs(v)
    if av >= 1_000_000:
        return f"{sign}{_sym} {av/1_000_000:.2f}M"
    if av >= 1_000:
        return f"{sign}{_sym} {av/1_000:.1f}K"
    return f"{sign}" + fmt_money(v)

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
    valid  = w_s > (g_inf + MIN_SPREAD)
    npv_s  = np.full(sims, np.nan)
    idx    = np.where(valid)[0]
    if idx.size:
        fv, wv, cv = fcf_p[idx], w_s[idx], capex_s[idx]
        fv = fv.copy()
        fv[:, -1] += (fv[:, -1] * (1 + g_inf)) / (wv - g_inf)
        npv_s[idx] = np.sum(fv / (1 + wv)[:, None] ** yrs[None, :], axis=1) - cv
    return npv_s

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — Inputs con tooltips explicativos (hover)
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar.expander("ℹ️ ¿Cómo usar esta aplicación?", expanded=False):
    st.markdown("""
**Pasos:**
1. Seleccioná la **moneda** (PYG o USD)
2. Completá los datos en cada sección del sidebar
3. Los resultados se actualizan en tiempo real
4. Pasá el mouse sobre el ícono **ℹ️** de cada indicador para ver su explicación
5. Descargá el reporte en TXT o PDF al final
""")

st.sidebar.divider()
st.sidebar.header("🧩 Identificación")
programa    = st.sidebar.text_input("Programa", "MBA USIL")
project     = st.sidebar.text_input("Proyecto", "Proyecto ABC")
responsible = st.sidebar.text_input("Responsable", "Docente: Jorge Rojas")
integrantes = st.sidebar.text_area("Integrantes", "",
    help="Nombres de los integrantes del equipo (se imprimirán en el PDF).")

st.sidebar.divider()
st.sidebar.header("0) Inversión inicial")
capex0 = st.sidebar.number_input(
    f"CAPEX Año 0 ({CURRENCY})",
    value=_DEF["capex0"], step=_DEF["step_big"], min_value=1.0,
    help="Monto total invertido para arrancar el proyecto: maquinaria, obra civil, licencias, capital inicial, etc."
)

st.sidebar.divider()
st.sidebar.header("1) CAPM / WACC")
rf = st.sidebar.number_input("Rf (%)", value=4.5, step=0.1,
    help="Tasa libre de riesgo: rendimiento de un bono del gobierno sin riesgo de default (ej. Bono del Tesoro EE.UU. a 10 años). Referencia global: 4–5%.") / 100
erp = st.sidebar.number_input("ERP (%)", value=5.5, step=0.1,
    help="Prima de riesgo del mercado: retorno adicional que da el mercado accionario sobre la tasa libre de riesgo. Histórico EE.UU.: 5–6%.") / 100
crp = st.sidebar.number_input("CRP (%)", value=2.0, step=0.1,
    help="Prima de riesgo país: compensación adicional por invertir en un país emergente. Paraguay ≈ 2%. Consultá Damodaran.com para valores actualizados.") / 100
beta_u = st.sidebar.number_input("βU (desapalancada)", value=0.90, step=0.05,
    help="Beta desapalancada: mide el riesgo del negocio sin el efecto de la deuda. β=1 = mismo riesgo que el mercado. β<1 = menos riesgoso. Consultá betas por sector en Damodaran.com.")
tax_rate = st.sidebar.number_input("Impuesto T (%)", value=10.0, step=0.5,
    help="Tasa del impuesto a la renta corporativa. Paraguay (IRACIS): 10%. Perú: 29.5%. Argentina: 35%.") / 100

st.sidebar.divider()
st.sidebar.header("2) Estructura de capital")
debt = st.sidebar.number_input(f"Deuda (D) [{CURRENCY}]", value=_DEF["debt"], step=_DEF["step_big"], min_value=0.0,
    help="Deuda financiera total del proyecto (préstamos bancarios, bonos, etc.).")
equity_bk = st.sidebar.number_input(f"Capital propio (E) [{CURRENCY}]", value=_DEF["equity"], step=_DEF["step_big"], min_value=1.0,
    help="Aporte de los socios/accionistas. E + D = inversión total financiada.")
kd = st.sidebar.number_input("Kd (%)", value=7.0, step=0.25,
    help="Costo de la deuda: tasa de interés anual del préstamo antes de impuestos. El modelo la ajusta por el beneficio fiscal (× (1−T)).") / 100

st.sidebar.divider()
st.sidebar.header("3A) Contable Año 1 → FCF₁")
sales_y1 = st.sidebar.number_input(f"Ventas Año 1 [{CURRENCY}]", value=_DEF["sales"], step=_DEF["step_med"], min_value=0.0,
    help="Ingresos totales proyectados para el primer año de operación.")
cvar_y1 = st.sidebar.number_input(f"Costos variables [{CURRENCY}]", value=_DEF["cvar"], step=_DEF["step_med"], min_value=0.0,
    help="Costos que varían con el volumen de ventas: materia prima, comisiones, transporte, etc.")
cfix_y1 = st.sidebar.number_input(f"Costos fijos [{CURRENCY}]", value=_DEF["cfix"], step=_DEF["step_big"], min_value=0.0,
    help="Costos que no cambian con el volumen: alquileres, sueldos administrativos, seguros, etc.")
dep_y1 = st.sidebar.number_input(f"Depreciación (no caja) [{CURRENCY}]", value=_DEF["dep"], step=_DEF["step_big"], min_value=0.0,
    help="Depreciación anual de activos fijos. Es un gasto contable que NO implica salida de caja, por eso se suma de vuelta al calcular el FCF.")
capex_y1 = st.sidebar.number_input(f"CAPEX Año 1 (mant.) [{CURRENCY}]", value=_DEF["capex_y1"], step=_DEF["step_sm"], min_value=0.0,
    help="Inversiones de mantenimiento y crecimiento del Año 1 (reposición de equipos, expansiones). SÍ implica salida de caja.")
st.sidebar.markdown("**Δ Capital de trabajo**")
d_ar  = st.sidebar.number_input(f"Δ AR (cuentas cobrar) [{CURRENCY}]", value=_DEF["d_ar"], step=_DEF["step_wc"],
    help="Aumento en cuentas por cobrar: dinero que te deben los clientes. Un aumento reduce el FCF (dinero inmovilizado).")
d_inv = st.sidebar.number_input(f"Δ INV (inventarios) [{CURRENCY}]",   value=_DEF["d_inv"], step=_DEF["step_wc"],
    help="Aumento en inventarios. Un aumento reduce el FCF (inversión en stock).")
d_ap  = st.sidebar.number_input(f"Δ AP (cuentas pagar) [{CURRENCY}]",  value=_DEF["d_ap"],  step=_DEF["step_wc"],
    help="Aumento en cuentas por pagar: lo que le debés a proveedores. Un aumento MEJORA el FCF (financiamiento gratuito de corto plazo).")

st.sidebar.divider()
st.sidebar.header("3B) Proyección + perpetuidad")
n_years = int(st.sidebar.slider("Años de proyección (N)", 3, 10, 5,
    help="Horizonte explícito de proyección. Más allá de este período se asume una perpetuidad (Valor Terminal)."))
g_exp = st.sidebar.number_input("g explícito (%) ciclo 1..N", value=5.0, step=0.25,
    help="Tasa de crecimiento anual de los FCF durante los N años proyectados. Basarse en proyecciones de ventas y el sector.") / 100
g_inf = st.sidebar.number_input("g perpetuidad (%)", value=2.0, step=0.10,
    help="Tasa de crecimiento a largo plazo (para siempre). Generalmente igual o menor a la inflación esperada del país. DEBE ser menor que el WACC.") / 100

st.sidebar.divider()
st.sidebar.header("4) Monte Carlo")
sims = int(st.sidebar.slider("Simulaciones", 5_000, 60_000, 15_000, 1_000,
    help="Cantidad de escenarios aleatorios a simular. Más simulaciones = mayor precisión, pero más tiempo de cálculo."))
st.sidebar.caption("Distribuciones triangulares · RNG sin semilla fija.")
g_min_mc    = st.sidebar.number_input("g mín (%)",        value=2.0, step=0.25, help="Peor caso de crecimiento en la simulación.") / 100
g_mode_mc   = st.sidebar.number_input("g base (%)",       value=5.0, step=0.25, help="Caso más probable de crecimiento.") / 100
g_max_mc    = st.sidebar.number_input("g máx (%)",        value=8.0, step=0.25, help="Mejor caso de crecimiento en la simulación.") / 100
wacc_range  = st.sidebar.number_input("WACC rango ± (%)", value=2.0, step=0.25, help="El WACC varía entre (WACC - rango) y (WACC + rango) en la simulación.") / 100
capex_min_mc  = st.sidebar.number_input(f"CAPEX mín [{CURRENCY}]", value=max(capex0*0.90, 1.0), step=_DEF["step_big"], help="Inversión inicial en el mejor escenario (menor costo).")
capex_mode_mc = st.sidebar.number_input(f"CAPEX base [{CURRENCY}]", value=capex0,              step=_DEF["step_big"], help="Inversión inicial más probable.")
capex_max_mc  = st.sidebar.number_input(f"CAPEX máx [{CURRENCY}]",  value=capex0 * 1.10,       step=_DEF["step_big"], help="Inversión inicial en el peor escenario (mayor costo).")
mult_min  = st.sidebar.number_input("Shock FCF₁ mín",  value=0.85, step=0.01, help="En el peor caso, el FCF del Año 1 será este porcentaje del valor calculado (ej. 0.85 = 15% menor).")
mult_mode = st.sidebar.number_input("Shock FCF₁ base", value=1.00, step=0.01, help="Factor de ajuste central (1.00 = sin cambio).")
mult_max  = st.sidebar.number_input("Shock FCF₁ máx",  value=1.15, step=0.01, help="En el mejor caso, el FCF del Año 1 será este porcentaje del valor calculado (ej. 1.15 = 15% mayor).")

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
        "APROBADO":  "El proyecto satisface criterios conservadores: creación de valor y downside controlado bajo incertidumbre razonable.",
        "RECHAZADO": "El proyecto no cumple criterios mínimos. Se recomienda rediseñar supuestos clave o estructura de inversión antes de avanzar.",
        "OBSERVADO": "El proyecto muestra potencial, pero requiere reforzar supuestos críticos y mitigaciones antes de aprobación final.",
    }[verdict]

# ─────────────────────────────────────────────────────────────────────────────
# Advertencias de validación
# ─────────────────────────────────────────────────────────────────────────────
if (cvar_y1 + cfix_y1) > sales_y1:
    st.warning("⚠️ Costos operativos (variables + fijos) superan las ventas Año 1. EBIT será negativo.")
if fcf_y1_calc < 0:
    st.warning(f"⚠️ FCF Año 1 calculado es negativo ({fmt_money(fcf_y1_calc)}). Verificar el bridge contable.")
if not valid_tv:
    st.error(f"⛔ WACC ({fmt_pct(wacc)}) no supera g∞ + spread ({fmt_pct(g_inf + MIN_SPREAD)}). Valor terminal inválido.")
if irr_base is not None and irr_base < wacc:
    st.warning(f"⚠️ TIR ({fmt_pct(irr_base)}) < WACC ({fmt_pct(wacc)}): el proyecto destruye valor respecto al costo de capital.")

# ─────────────────────────────────────────────────────────────────────────────
# Header del dashboard
# ─────────────────────────────────────────────────────────────────────────────
st.title("📊 ValuationSuite USIL — One-Pager Ejecutivo")
st.caption(f"DCF · Monte Carlo · Sensibilidad · Moneda: {CURRENCY} · Pasá el mouse sobre ℹ️ para ver explicaciones")

hL, hR = st.columns([0.78, 0.22], gap="large")
with hL:
    st.markdown(f"""
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:14px;">
        <div>
          <div style="font-size:.98rem;font-weight:800;letter-spacing:.02em;">
            ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA ({CURRENCY})
          </div>
          <div class="small">Universidad San Ignacio de Loyola (USIL) — MBA — Proyectos de Inversión / Valuation</div>
          <div class="small">Proyecto: <b>{project}</b> &nbsp;|&nbsp; Responsable: <b>{responsible}</b></div>
        </div>
        <div class="small" style="text-align:right;white-space:nowrap;">Fecha: <b>{date.today().isoformat()}</b></div>
      </div>
    </div>
    """, unsafe_allow_html=True)
with hR:
    pill_cls = "good" if verdict == "APROBADO" else ("bad" if verdict == "RECHAZADO" else "warn")
    st.markdown(f"""
    <div class="card" style="text-align:center;">
      <div class="small">Dictamen automático</div>
      <div class="pill {pill_cls}" style="font-size:1rem;">{verdict}</div>
      <div class="small" style="margin-top:6px;">Checklist + Monte Carlo</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# KPIs — 8 métricas con tooltips al pasar el mouse (help=)
# ─────────────────────────────────────────────────────────────────────────────
r1c1, r1c2, r1c3, r1c4 = st.columns(4, gap="medium")
r1c1.metric("VAN (base)", fmt_money_short(npv_base) if np.isfinite(npv_base) else "—", "Determinístico",
    help="Valor Actual Neto: mide si el proyecto crea o destruye valor. VAN > 0 = rentable ✅ | VAN < 0 = destruye valor ❌. Es la métrica más importante. Fórmula: suma de FCF descontados al WACC + Valor Terminal − Inversión Inicial.")
r1c2.metric("TIR (base)", fmt_pct(irr_base) if irr_base is not None else "N/A", "Determinístico",
    help="Tasa Interna de Retorno: rentabilidad anual del proyecto. Comparala con el WACC: si TIR > WACC, el proyecto rinde más de lo que cuesta financiarlo ✅. Si TIR < WACC, destruye valor ❌.")
r1c3.metric("TIR − WACC", fmt_pct(irr_spread) if irr_spread is not None else "N/A", "Spread sobre costo capital",
    help="Spread: cuánto rinde el proyecto POR ENCIMA de su costo de capital. Positivo = crea valor. Cuanto mayor, más atractivo. Equivale al 'margen financiero' del proyecto.")
r1c4.metric("WACC", fmt_pct(wacc), f"Ke {fmt_pct(ke)} · Kd {fmt_pct(kd)}",
    help="Costo Promedio Ponderado del Capital: tasa mínima de retorno que debe generar el proyecto para satisfacer a inversores y bancos. Combina Ke (costo del capital propio, calculado con CAPM) y Kd (costo de la deuda, ajustado por escudo fiscal).")

r2c1, r2c2, r2c3, r2c4 = st.columns(4, gap="medium")
r2c1.metric("Payback", f"{pb_simple:.1f} años" if pb_simple is not None else "N/A", "Simple",
    help="Período de recupero simple: años necesarios para recuperar la inversión inicial con los flujos de caja sin descontar. Más corto = mejor. Limitación: ignora el valor del dinero en el tiempo.")
r2c2.metric("Payback (desc.)", f"{pb_disc:.1f} años" if pb_disc is not None else "N/A", "Descontado al WACC",
    help="Período de recupero descontado: igual que el payback simple, pero descuenta los flujos al WACC antes de acumularlos. Más conservador y preciso: reconoce que el dinero futuro vale menos que el dinero hoy.")
r2c3.metric("P(VAN<0)", f"{prob_neg*100:.1f}%" if np.isfinite(prob_neg) else "—", "Monte Carlo",
    help="Probabilidad de pérdida: % de simulaciones donde el VAN resultó negativo. < 10% = riesgo bajo ✅ | 10–20% = aceptable (límite del comité) | > 20% = riesgo elevado ⚠️. El comité aprueba si P(VAN<0) ≤ 20%.")
r2c4.metric("P50 (VAN)", fmt_money_short(p50) if np.isfinite(p50) else "—", "Monte Carlo",
    help="Mediana del VAN simulado: la mitad de los 15.000+ escenarios simulados tienen VAN por encima de este valor. Es el resultado 'más probable' o central. Si P50 > 0, en la mayoría de escenarios el proyecto es rentable.")

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
        f"- Horizonte: **{n_years} años** + perpetuidad &nbsp;·&nbsp; g: **{fmt_pct(g_exp)}** &nbsp;·&nbsp; g∞: **{fmt_pct(g_inf)}**\n"
        f"- WACC: **{fmt_pct(wacc)}** &nbsp;·&nbsp; Ke: **{fmt_pct(ke)}** &nbsp;·&nbsp; Kd: **{fmt_pct(kd)}** &nbsp;·&nbsp; T: **{fmt_pct(tax_rate)}**\n"
        f"- βU: **{beta_u:.2f}** → βL: **{beta_l:.2f}** &nbsp;·&nbsp; CAPEX₀: **{fmt_money_short(capex0)}**\n"
        f"- FCF₁ (calculado): **{fmt_money_short(fcf_y1_calc)}**"
    )
    st.markdown("**Puente contable → FCF₁**")
    st.markdown(
        f"EBIT: {fmt_money_short(ebit)} → NOPAT: {fmt_money_short(nopat)}\n"
        f"+ Dep: {fmt_money_short(dep_y1)} − CAPEX mant.: {fmt_money_short(capex_y1)} − ΔCT: {fmt_money_short(delta_wc)}"
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
            text=[fmt_money_short(pv_fcf), fmt_money_short(pv_tv),
                  fmt_money_short(-capex0), fmt_money_short(npv_base)],
            textposition="outside",
        ))
        fig_wf.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=25, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(color="#eaf1ff", size=10),
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
        "<div class='small'>Verde = FCF positivo · Rojo = FCF negativo · Línea punteada: PV acumulado al WACC</div>",
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
        marker=dict(size=5),
        yaxis="y2",
    ))
    fig_fcf.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(x=0.02, y=0.98, bgcolor="rgba(0,0,0,0)", font=dict(color="#eaf1ff", size=9)),
        font=dict(color="#eaf1ff", size=10),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.07)"),
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
    )
    st.plotly_chart(fig_fcf, use_container_width=True, config={"displayModeBar": False})
    if np.isfinite(tv):
        st.caption(f"TV (año {n_years}): {fmt_money_short(tv)} · PV(TV): {fmt_money_short(pv_tv)}")
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
            f"<div class='small'>P5: <b>{fmt_money_short(p5)}</b> · P50: <b>{fmt_money_short(p50)}</b> · "
            f"P95: <b>{fmt_money_short(p95)}</b> · CVaR5: <b>{fmt_money_short(cvar5)}</b></div>",
            unsafe_allow_html=True,
        )
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(x=npv_valid, nbinsx=40, marker_color="#66a9ff", opacity=0.80))
        fig_hist.add_vrect(x0=float(npv_valid.min()), x1=0, fillcolor="rgba(255,93,93,0.08)", line_width=0)
        fig_hist.add_vline(x=0, line_color="rgba(255,93,93,0.85)", line_width=1.8,
                           annotation_text="VAN=0", annotation_position="top right",
                           annotation=dict(font_color="#ff5d5d", font_size=9))
        for pct_val, label in [(p5, "P5"), (p50, "P50"), (p95, "P95")]:
            if np.isfinite(pct_val):
                fig_hist.add_vline(x=float(pct_val), line_dash="dash",
                                   line_color="rgba(234,241,255,0.50)", line_width=1.5,
                                   annotation_text=label,
                                   annotation=dict(font_color="#eaf1ff", font_size=9))
        fig_hist.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(color="#eaf1ff", size=10),
            bargap=0.04,
        )
        fig_hist.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
        fig_hist.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
        st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})
        st.markdown(
            "<div class='small'>P5 = adverso plausible · P50 = central · P95 = favorable · CVaR5 = severidad media del 5% peor.</div>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("Monte Carlo sin resultados válidos. Revisar WACC vs g∞.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    "<div class='small' style='text-align:center;margin-top:6px;'>"
    "Uso académico (MBA). Resultados dependen de supuestos; no sustituyen due diligence. · ValuationSuite USIL v2.0</div>",
    unsafe_allow_html=True,
)

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Análisis de Sensibilidad — WACC × g_exp
# ─────────────────────────────────────────────────────────────────────────────
st.header("🔍 Análisis de Sensibilidad — WACC × g")
st.caption("VAN recalculado variando WACC (filas) y g explícito (columnas). Verde = VAN > 0 · Rojo = VAN < 0 · Borde azul = caso base.")

with st.expander("ℹ️ ¿Cómo leer esta tabla?", expanded=False):
    st.markdown("""
**Filas = WACC** (costo de capital). Si el WACC sube (más riesgo o tasas más altas), el VAN baja.

**Columnas = g** (crecimiento de los flujos). Si el negocio crece más, el VAN sube.

- 🟢 **Verde**: proyecto rentable bajo esa combinación.
- 🔴 **Rojo**: proyecto no rentable bajo esa combinación.
- **Celda con borde azul** = tu caso base (valores actuales del sidebar).
- **Regla práctica**: si la mayoría de celdas son verdes, el proyecto es robusto.
""")

WACC_DELTAS  = [-0.030, -0.015, 0.000,  0.015,  0.030]
G_EXP_DELTAS = [-0.020, -0.010, 0.000,  0.010,  0.020]
wacc_labels  = [f"{(wacc + dw)*100:.1f}%" for dw in WACC_DELTAS]
g_exp_labels = [f"{(g_exp + dg)*100:.1f}%" for dg in G_EXP_DELTAS]
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
            row.append(float(np.sum(fs / (1+w)**years) + tv_s/(1+w)**n_years - capex0))
        else:
            row.append(float("nan"))
    sens_rows.append(row)

g_th = "".join(f'<th style="padding:5px 8px;text-align:right;color:#66a9ff;font-size:.8rem;">{lbl}</th>' for lbl in g_exp_labels)
tbody = ""
for ri, (wacc_lbl, row_data) in enumerate(zip(wacc_labels, sens_rows)):
    is_base_row = (ri == 2)
    row_bg = "background:rgba(102,169,255,0.06);" if is_base_row else ""
    tbody += f'<tr style="{row_bg}">'
    tbody += f'<td style="padding:5px 8px;color:#eaf1ff;font-size:.8rem;font-weight:{"700" if is_base_row else "400"};">{wacc_lbl}</td>'
    for ci, val in enumerate(row_data):
        is_base_cell = (ri == 2 and ci == 2)
        base_border  = "border:2px solid #66a9ff;" if is_base_cell else ""
        if not np.isfinite(val):
            cs, ct = "background:rgba(255,255,255,0.04);color:#555;", "—"
        elif val > 0:
            alpha = 0.10 + min(val / (npv_ref * 3 + 1), 1.0) * 0.35
            cs = f"background:rgba(39,209,124,{alpha:.2f});color:#27d17c;font-weight:700;"
            ct = fmt_money_short(val)
        else:
            alpha = 0.10 + min(abs(val) / (npv_ref * 3 + 1), 1.0) * 0.35
            cs = f"background:rgba(255,93,93,{alpha:.2f});color:#ff5d5d;font-weight:700;"
            ct = fmt_money_short(val)
        tbody += f'<td style="padding:5px 8px;text-align:right;font-size:.8rem;{cs}{base_border}">{ct}</td>'
    tbody += "</tr>"

st.markdown(f"""
<div class="card" style="overflow-x:auto;">
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr>
        <th style="padding:5px 8px;text-align:left;color:#66a9ff;font-size:.8rem;">WACC \\ g exp</th>
        {g_th}
      </tr>
    </thead>
    <tbody>{tbody}</tbody>
  </table>
  <div class="small" style="margin-top:8px;">Filas = WACC base ± 1.5 / 3 pp · Columnas = g base ± 1 / 2 pp</div>
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
    programa=programa,
    integrantes=integrantes,
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
    st.download_button("⬇️ Descargar One-Pager (TXT)", data=onepager_txt.encode("utf-8"),
                       file_name="one_pager_usil.txt", mime="text/plain", use_container_width=True)
with col_dl2:
    if rep.REPORTLAB_OK:
        hist_counts, hist_edges = None, None
        if npv_valid.size:
            hist_counts, hist_edges = np.histogram(npv_valid, bins=36)
        pdf_bytes = rep.generate_onepager_pdf(onepager, hist_counts, hist_edges)
        st.download_button("⬇️ Descargar One-Pager (PDF premium)", data=pdf_bytes,
                           file_name="one_pager_usil.pdf", mime="application/pdf", use_container_width=True)
    else:
        st.info("Para exportar PDF, instalar `reportlab`.")

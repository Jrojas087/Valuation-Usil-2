# app.py — ValuationSuite USIL v3.0
# Evaluación de proyectos: flujo desagregado · WACC en la moneda del flujo · VT opcional · Monte Carlo sobre
# drivers operativos · punto de equilibrio · alertas. Modo compatibilidad = fórmulas v2.0 (solo para contrastar).

from dataclasses import replace
from html import escape
from datetime import date

import numpy as np
import plotly.graph_objects as go
import streamlit as st

import glosario as gl
import report_usil as rep
import valuation_engine as ve

# ─────────────────────────────────────────────────────────────────────────────
# Page config + estilo (se mantiene el diseño oscuro de la v2.0)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ValuationSuite USIL — Evaluación Financiera",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
.small { color: var(--muted); font-size: .82rem; }
.pill {
  display:inline-block; padding: 5px 12px; border-radius: 999px;
  border: 1px solid var(--line); background: rgba(102,169,255,.10);
  font-weight: 700; letter-spacing: .02em;
}
.pill.good { background: rgba(39,209,124,.14); }
.pill.warn { background: rgba(255,204,102,.14); }
.pill.bad  { background: rgba(255,93,93,.14); }
table.edu { width:100%; border-collapse:collapse; }
table.edu th { color:#66a9ff; text-align:left; font-size:.8rem; padding:6px 8px; border-bottom:1px solid var(--line); }
table.edu td { padding:7px 8px; border-bottom:1px solid var(--line); vertical-align:top; font-size:.82rem; }
table.edu td.n { font-weight:700; white-space:nowrap; }
table.edu td.v { text-align:right; font-weight:700; white-space:nowrap; color:#eaf1ff; }
table.edu td.e { color:var(--muted); font-size:.77rem; line-height:1.4; }
table.edu code { font-size:.74rem; color:#9cc4ff; background:rgba(255,255,255,.06); padding:1px 4px; border-radius:4px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Modo y moneda
# ─────────────────────────────────────────────────────────────────────────────
compat = st.sidebar.toggle(
    "Modo compatibilidad (fórmulas v2.0)", value=False,
    help="Reproduce los cálculos de la versión 2.0 (perpetuidad siempre activa, TIR con VT, Ke sin convertir de moneda, "
         "Monte Carlo sobre g/WACC/CAPEX). Tiene defectos conocidos: úsalo solo para contrastar, no para decidir.")

_CURR_OPTIONS = {
    "PYG 🇵🇾  Guaraní Paraguayo": ("Gs.", 0),
    "USD 🇺🇸  Dólar Estadounidense": ("$", 2),
}
_curr_sel = st.sidebar.selectbox("💱 Moneda del flujo de caja", list(_CURR_OPTIONS.keys()), index=0,
                                 help="Moneda en la que están expresados TODOS los flujos. La tasa de descuento se calcula en esta misma moneda.")
_sym, _dec = _CURR_OPTIONS[_curr_sel]
CURRENCY = _curr_sel.split()[0]
_IS_PYG = CURRENCY == "PYG"
_money_fmt = "%.0f" if _dec == 0 else "%.2f"

_DEF = {
    "capex0":   3_500_000_000.0  if _IS_PYG else 1_000_000.0,
    "step_big": 50_000_000.0     if _IS_PYG else 50_000.0,
    "step_med": 100_000_000.0    if _IS_PYG else 100_000.0,
    "step_wc":  10_000_000.0     if _IS_PYG else 10_000.0,
    "debt":     1_400_000_000.0  if _IS_PYG else 400_000.0,
    "equity":   2_100_000_000.0  if _IS_PYG else 600_000.0,
    "sales":    10_000_000_000.0 if _IS_PYG else 3_000_000.0,
    "cvar":     5_600_000_000.0  if _IS_PYG else 1_680_000.0,
    "cfix":     2_300_000_000.0  if _IS_PYG else 690_000.0,
    "ar":       90_000_000.0     if _IS_PYG else 27_000.0,
    "inv":      80_000_000.0     if _IS_PYG else 24_000.0,
    "ap":       30_000_000.0     if _IS_PYG else 9_000.0,
    "kd":       11.0             if _IS_PYG else 7.0,
}


def fmt_money(x) -> str:
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
        return f"{sign}{_sym} {av / 1_000_000:.2f}M"
    if av >= 1_000:
        return f"{sign}{_sym} {av / 1_000:.1f}K"
    return f"{sign}" + fmt_money(v)


def fmt_pct(x, nd=2) -> str:
    try:
        v = float(x)
        return f"{v * 100:.{nd}f}%" if np.isfinite(v) else "—"
    except Exception:
        return "—"


def _money_hint(x) -> None:
    st.sidebar.caption(f"= {fmt_money(x)}")


def edu_table(headers, rows) -> str:
    """Tabla HTML didáctica. Cada fila: [nombre, valor..., explicación_html]. Nombre y valores se escapan;
    la última celda es HTML ya escapado (viene de glosario.celda_html)."""
    th = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = ""
    for r in rows:
        tds = f'<td class="n">{escape(str(r[0]))}</td>'
        tds += "".join(f'<td class="v">{escape(str(c))}</td>' for c in r[1:-1])
        tds += f'<td class="e">{r[-1]}</td>'
        body += f"<tr>{tds}</tr>"
    return f'<table class="edu"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def _acad(key: str, extra: str = "") -> str:
    """Tooltip: explicación académica (glosario) + nota práctica de cómo se usa aquí."""
    return gl.ayuda(key) + (f"\n\n**En esta calculadora:** {extra}" if extra else "")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — inputs
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar.expander("ℹ️ ¿Cómo usar esta aplicación?", expanded=False):
    st.markdown("""
1. Elegí la **moneda del flujo** (la tasa se calcula en esa moneda).
2. Cargá inversión, tasa de descuento, estructura de capital y operación.
3. Por defecto **no hay valor terminal**: el proyecto se evalúa con los flujos de su horizonte. Activalo solo si podés justificarlo.
4. Revisá las **alertas**, la **variable crítica** y el **escenario pesimista** antes de interpretar el VAN.
5. Descargá el one-pager (TXT o PDF).
""")

st.sidebar.divider()
st.sidebar.header("🧩 Identificación")
programa = st.sidebar.text_input("Programa", "MBA USIL", help="Programa académico o curso al que pertenece el trabajo (por ejemplo, MBA USIL). Se imprime en el encabezado del reporte.")
project = st.sidebar.text_input("Proyecto", "Proyecto ABC", help="Nombre del proyecto de inversión que se evalúa. Aparece en el encabezado y en el nombre de los escenarios guardados.")
responsible = st.sidebar.text_input("Responsable", "Docente: Jorge Rojas", help="Persona o docente responsable del análisis. Se imprime en el reporte.")
integrantes = st.sidebar.text_area("Integrantes", "", help="Nombres de los integrantes del equipo (se imprimirán en el PDF).")

st.sidebar.divider()
st.sidebar.header("0) Inversión inicial")
capex0 = st.sidebar.number_input(
    f"CAPEX Año 0 ({CURRENCY})", value=_DEF["capex0"], step=_DEF["step_big"], min_value=1.0, format=_money_fmt,
    help="Inversión total para arrancar: activos fijos, obra civil, licencias, puesta en marcha. Incluí solo flujos INCREMENTALES: "
         "excluí costos hundidos y sumá costos de oportunidad.")
_money_hint(capex0)

st.sidebar.divider()
st.sidebar.header("1) Costo del capital propio (CAPM)")
st.sidebar.caption("Parámetros en USD (p. ej. Damodaran). El modelo los convierte a la moneda del flujo.")
rf = st.sidebar.number_input("Rf (%) — USD", value=4.5, step=0.1,
    help=_acad("rf", "ingresá la Rf en USD (bono del Tesoro de EE. UU. a 10 años); debe ser coherente con la moneda de la ERP y de la β.")) / 100
erp = st.sidebar.number_input("ERP (%)", value=5.5, step=0.1,
    help=_acad("erp", "valor en USD; citá la fuente y el año de la estimación.")) / 100
crp = st.sidebar.number_input("CRP (%) — riesgo país", value=2.0, step=0.1,
    help=_acad("crp", "se suma al Ke; no la dupliques ajustando también los flujos.")) / 100
size_prem = st.sidebar.number_input("Prima por tamaño (%) — opcional", value=0.0, step=0.1,
    help=_acad("size", "dejá 0 si no podés justificarla.")) / 100
beta_u = st.sidebar.number_input("βU (desapalancada)", value=0.90, step=0.05,
    help=_acad("beta_u", "se reapalanca con la estructura objetivo de la sección 2 (fórmula de Hamada); el resultado figura en la tabla de la tasa de descuento."))
tax_rate = st.sidebar.number_input("IRE (%)", value=10.0, step=0.5,
    help=_acad("ire", "se aplica sobre el EBIT positivo y también reduce el costo de la deuda (escudo fiscal).")) / 100

st.sidebar.markdown("**Inflación (conversión de moneda)**")
pi_usd = st.sidebar.number_input("π USD (%)", value=2.5, step=0.1,
    help=_acad("pi", "π USD es la inflación esperada de largo plazo en dólares (referencia habitual: 2 % a 2,5 %). "
                     "Si el flujo está en USD no hay conversión: la π del flujo es esta misma.")) / 100
if _IS_PYG:
    pi_flow = st.sidebar.number_input("π Gs (%)", value=3.5, step=0.1,
        help=_acad("pi", "π Gs es la inflación esperada de largo plazo en guaraníes: usá una proyección oficial y citá la fuente "
                         "(el benchmark del curso usa 3,5 %). Cuanto mayor sea π Gs frente a π USD, más alta resulta la tasa en guaraníes. "
                         "Debe ser coherente con el crecimiento de ventas y costos (nominales); también indexa el CAPEX de reposición.")) / 100
    convert = st.sidebar.checkbox("Convertir Ke a guaraníes", value=True,
        help="Desmarcarlo aplica el Ke en USD a flujos en guaraníes (error de moneda de la v2.0). Dispara la alerta V07.")
else:
    pi_flow, convert = pi_usd, True

st.sidebar.divider()
st.sidebar.header("2) Estructura de capital OBJETIVO")
st.sidebar.caption("Proporciones objetivo de deuda y capital propio: definen los pesos del WACC y reapalancan la beta.")
debt = st.sidebar.number_input(f"Deuda (D) [{CURRENCY}]", value=_DEF["debt"], step=_DEF["step_big"], min_value=0.0, format=_money_fmt,
    help=_acad("weights", "ingresá la deuda de la estructura objetivo a valores de mercado, no la contable ni la financiación puntual de este proyecto."))
_money_hint(debt)
equity_bk = st.sidebar.number_input(f"Capital propio (E) [{CURRENCY}]", value=_DEF["equity"], step=_DEF["step_big"], min_value=1.0, format=_money_fmt,
    help=_acad("weights", "capital propio de la estructura objetivo; solo importan las proporciones D/V y E/V, no los montos."))
_money_hint(equity_bk)
kd = st.sidebar.number_input(f"Kd (%) — en {CURRENCY}", value=_DEF["kd"], step=0.25,
    help=_acad("kd", "ingresá el Kd ANTES de impuestos, EN LA MONEDA DEL FLUJO: el rendimiento de mercado actual (YTM) de deuda comparable, "
                     "no la tasa cupón histórica. El modelo aplica (1 − IRE).")) / 100

st.sidebar.divider()
st.sidebar.header("3A) Operación — Año 1 a capacidad plena")
st.sidebar.caption("Datos del primer año con el negocio a plena capacidad: son la base para proyectar ingresos, costos y capital de trabajo.")
sales_y1 = st.sidebar.number_input(f"Ventas Año 1 [{CURRENCY}]", value=_DEF["sales"], step=_DEF["step_med"], min_value=0.0, format=_money_fmt,
    help=_acad("ingresos", "ingresos del primer año si el proyecto operara a plena capacidad; la rampa de arranque se aplica aparte."))
_money_hint(sales_y1)
cvar_y1 = st.sidebar.number_input(f"Costos variables [{CURRENCY}]", value=_DEF["cvar"], step=_DEF["step_med"], min_value=0.0, format=_money_fmt,
    help=_acad("costos_var", "se proyectan como % de las ventas a precios base."))
_money_hint(cvar_y1)
cfix_y1 = st.sidebar.number_input(f"Costos fijos [{CURRENCY}]", value=_DEF["cfix"], step=_DEF["step_big"], min_value=0.0, format=_money_fmt,
    help=_acad("costos_fijos", "excluí depreciación e intereses (se tratan aparte)."))
_money_hint(cfix_y1)
dep_years = int(st.sidebar.number_input("Vida contable de los activos (años)", value=8, min_value=1, max_value=50, step=1,
    help=_acad("dep", "línea recta del CAPEX inicial y de cada reposición, a lo largo de esta vida contable.")))
maint_pct = st.sidebar.number_input("Reposición anual (% de la depreciación)", value=100.0, step=5.0, min_value=0.0,
    help=_acad("capex_repl", "reposición de cada año como % de la depreciación de la base inicial; debe ser ≥ 100 % para sostener el negocio."))
st.sidebar.markdown("**Capital de trabajo — saldos al cierre del Año 1**")
d_ar = st.sidebar.number_input(f"Cuentas por cobrar [{CURRENCY}]", value=_DEF["ar"], step=_DEF["step_wc"], format=_money_fmt,
    help=_acad("dnwc", "saldo de clientes al cierre del Año 1; el capital de trabajo total se proyecta proporcional a las ventas."))
d_inv = st.sidebar.number_input(f"Inventarios [{CURRENCY}]", value=_DEF["inv"], step=_DEF["step_wc"], format=_money_fmt,
    help=_acad("dnwc", "saldo de inventarios al cierre del Año 1."))
d_ap = st.sidebar.number_input(f"Cuentas por pagar [{CURRENCY}]", value=_DEF["ap"], step=_DEF["step_wc"], format=_money_fmt,
    help=_acad("dnwc", "saldo de proveedores al cierre del Año 1: financia parte del capital de trabajo y por eso resta."))
nwc_y1 = d_ar + d_inv - d_ap
st.sidebar.caption(f"Capital de trabajo neto Año 1 = {fmt_money(nwc_y1)}")
ramp_years = int(st.sidebar.number_input("Años de rampa de arranque", value=0, min_value=0, max_value=5, step=1,
    help="Años que tarda el proyecto en llegar a plena capacidad. 0 = sin rampa."))
ramp_start = st.sidebar.slider("Nivel del Año 1 (% de la capacidad plena)", 10, 100, 100, 5,
    help="Solo aplica si hay años de rampa.", disabled=ramp_years == 0) / 100

st.sidebar.divider()
st.sidebar.header("3B) Proyección")
st.sidebar.caption("Horizonte de evaluación y crecimientos nominales (en la moneda del flujo).")
n_years = int(st.sidebar.slider("Años de proyección (N)", 3, 10, 5, help="Horizonte explícito del flujo."))
g_exp = st.sidebar.number_input("g ventas (%)", value=5.0, step=0.25,
    help=_acad("ingresos", "crecimiento NOMINAL anual de las ventas; debe ser coherente con la inflación de la moneda del flujo.")) / 100
g_fix = st.sidebar.number_input("g costos fijos (%)", value=3.5, step=0.25,
    help=_acad("costos_fijos", "crecimiento nominal anual de los costos fijos (típicamente la inflación).")) / 100

st.sidebar.divider()
st.sidebar.header("3C) Valor terminal (VT)")
st.sidebar.caption("Qué se supone que ocurre con el proyecto después del último año proyectado.")
_MODES = {
    "Sin valor terminal (recomendado)": "none",
    "Valor de desecho": "salvage",
    "Perpetuidad (requiere justificación)": "perpetuity",
}
mode_label = st.sidebar.selectbox("Tratamiento al final del horizonte", list(_MODES.keys()),
    help="Para activos de vida finita (flota, pantallas, contratos acotados) no corresponde perpetuidad. "
         "El VAN y la TIR se muestran siempre con y sin VT.")
terminal_mode = _MODES[mode_label]
salvage_value, vt_just, vt_text = 0.0, False, ""
if terminal_mode == "salvage":
    salvage_value = st.sidebar.number_input(f"Valor de desecho bruto [{CURRENCY}]", value=0.0, step=_DEF["step_big"], min_value=0.0, format=_money_fmt,
        help="Precio esperado de venta de los activos al año N. Se descuenta el IRE sobre la ganancia contable.")
if terminal_mode == "perpetuity":
    vt_just = st.sidebar.checkbox("Justifico la continuidad del negocio", value=False,
        help="Sin esta confirmación el modelo evalúa SIN valor terminal (alerta V09).")
    vt_text = st.sidebar.text_area("Justificación", "", help="Por qué el negocio continuará más allá del horizonte (contratos, mercado, reinversión).")
g_inf = st.sidebar.number_input("g perpetuidad (%)", value=2.0, step=0.10,
    help="Crecimiento de largo plazo del FCF normalizado. No debería superar el crecimiento nominal de la economía. "
         "El modelo lo limita a WACC − 2 pp.") / 100
recover_nwc = st.sidebar.checkbox("Recuperar capital de trabajo al final", value=True, disabled=terminal_mode == "perpetuity",
    help="Si el proyecto termina, el capital de trabajo se liquida.")

st.sidebar.divider()
st.sidebar.header("4) Monte Carlo — drivers operativos")
st.sidebar.caption("Se sortean miles de combinaciones de precio, volumen, costos, CAPEX y WACC dentro de los rangos, para medir cuánto se dispersa el VAN.")
sims = int(st.sidebar.slider("Simulaciones", 5_000, 60_000, 15_000, 1_000,
    help="Cantidad de escenarios aleatorios que se simulan. Más simulaciones dan resultados más estables (P5, P50, P95) pero tardan un poco más. 10.000 a 20.000 suele bastar."))
dist = {"Triangular": "triangular", "Normal truncada": "normal"}[st.sidebar.selectbox("Distribución", ["Triangular", "Normal truncada"],
    help="Normal truncada: media = caso base, σ = (rango)/4, acotada al rango.")]
fixed_seed = st.sidebar.checkbox("Semilla fija (reproducible)", value=True,
    help="Con semilla fija, los mismos datos producen siempre los mismos resultados y el mismo reporte. Desmarcala para ver la variación natural entre corridas.")
with st.sidebar.expander("Rangos de los drivers (% vs. caso base)", expanded=False):
    def _rng(label, lo, hi, helptxt):
        a = st.number_input(f"{label} mín (%)", value=float(lo), step=1.0, key=f"{label}_lo",
                            help=helptxt + " Este es el límite inferior del rango (variación mínima respecto del caso base; negativo = baja).")
        b = st.number_input(f"{label} máx (%)", value=float(hi), step=1.0, key=f"{label}_hi",
                            help=helptxt + " Este es el límite superior del rango (variación máxima respecto del caso base).")
        return (1 + a / 100, 1.0, 1 + b / 100)
    r_price = _rng("Precio", -8, 8, "Variación del precio de venta.")
    r_vol = _rng("Volumen / ocupación", -10, 10, "Variación del volumen vendido (afecta ingresos y costos variables).")
    r_vc = _rng("Costo variable unitario", -8, 10, "Variación del costo variable por unidad.")
    r_fix = _rng("Costos fijos", -5, 10, "Variación de los costos fijos.")
    r_cap = _rng("CAPEX inicial", -5, 15, "Variación del CAPEX (sobrecostos son típicos: rango sesgado al alza).")
    wacc_range = st.number_input("WACC ± (pp)", value=2.0, step=0.25, help="El WACC varía ± este valor en la simulación.") / 100
    rho_pv = st.slider("Correlación precio–volumen", -0.9, 0.9, 0.0, 0.1, help="Negativa si la demanda es elástica.")
    rho_cf = st.slider("Correlación costo variable–costos fijos", -0.9, 0.9, 0.0, 0.1, help="Positiva si ambos responden a la inflación de costos.")
    pess_label = st.selectbox("Escenario pesimista", ["Extremos del rango", "P10 adverso de cada driver"],
        help="Todos los drivers en su lado adverso a la vez (determinístico).")
if compat:
    st.sidebar.caption("Monte Carlo v2.0 (solo modo compatibilidad)")
    g_min_mc = st.sidebar.number_input("g mín (%)", value=2.0, step=0.25, help="Peor caso de crecimiento en el Monte Carlo de la v2.0.") / 100
    g_mode_mc = st.sidebar.number_input("g base (%)", value=5.0, step=0.25, help="Crecimiento más probable en el Monte Carlo de la v2.0.") / 100
    g_max_mc = st.sidebar.number_input("g máx (%)", value=8.0, step=0.25, help="Mejor caso de crecimiento en el Monte Carlo de la v2.0.") / 100

# ─────────────────────────────────────────────────────────────────────────────
# Encabezado
# ─────────────────────────────────────────────────────────────────────────────
st.title("📊 ValuationSuite USIL — One-Pager Ejecutivo")
st.caption(f"Flujo de caja libre · WACC en {CURRENCY} · Monte Carlo sobre drivers · Moneda: {CURRENCY}")
seed = 20260 if fixed_seed else None

# ═════════════════════════════════════════════════════════════════════════════
# MODO COMPATIBILIDAD (fórmulas v2.0)
# ═════════════════════════════════════════════════════════════════════════════
if compat:
    st.error("⛔ MODO COMPATIBILIDAD v2.0 — fórmulas con defectos conocidos (perpetuidad siempre activa, TIR inflada por el VT, "
             "Ke sin convertir de moneda, Monte Carlo sin drivers operativos). Solo para contrastar con la versión corregida.")
    wl = ve.legacy_wacc(rf, erp, crp, beta_u, tax_rate, debt, equity_bk, kd)
    dep_c = capex0 / dep_years
    br = ve.legacy_fcf1(sales_y1, cvar_y1, cfix_y1, dep_c, dep_c * maint_pct / 100, nwc_y1, tax_rate)
    res = ve.legacy_dcf(capex0, n_years, wl["wacc"], g_inf, br["fcf1"], g_exp)
    npv_mc = ve.legacy_monte_carlo(sims, br["fcf1"], n_years, g_inf, (g_min_mc, g_mode_mc, g_max_mc),
                                   (max(wl["wacc"] - wacc_range, 0.001), max(wl["wacc"], 0.001), wl["wacc"] + wacc_range),
                                   (max(capex0 * 0.9, 1.0), capex0, capex0 * 1.1), (0.85, 1.0, 1.15), seed)
    st_mc = ve.mc_stats(npv_mc)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VAN (con VT)", fmt_money_short(res["van"]), "v2.0", help="VAN como lo calculaba la v2.0: incluye siempre el valor terminal por perpetuidad. Compará con el VAN sin VT para ver cuánto depende del valor terminal.")
    c2.metric("TIR (con VT)", fmt_pct(res["irr"]) if res["irr"] is not None else "N/A", "v2.0 (N/A si > 200 %)", help="TIR de la v2.0: suma el valor terminal como caja del año N, por eso suele inflarse. La v2.0 mostraba N/A si superaba 200 %.")
    c3.metric("WACC (sin convertir moneda)", ve.fmt_rate(wl["wacc"]), f"Ke {ve.fmt_rate(wl['ke'])} · Kd {ve.fmt_rate(kd)}",
              help="WACC de la v2.0: el Ke calculado en USD se aplicaba tal cual a flujos en otra moneda (sin diferencial de inflación). Por eso el Ke puede quedar por debajo del Kd.")
    c4.metric("Payback", f"{ve.fmt_years(res['payback'])} años", f"desc. {ve.fmt_years(res['payback_disc'])}",
              help="Años para recuperar la inversión con flujos sin descontar (y descontados al WACC debajo). Es un indicador secundario: ignora el valor del dinero en el tiempo y lo que ocurre después.")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("VAN sin VT", fmt_money_short(res["van_sin_vt"]), help="VAN considerando solo los flujos del horizonte, sin valor terminal. Si es negativo mientras el VAN con VT es positivo, el resultado depende de la perpetuidad.")
    c6.metric("Peso del VT", fmt_pct(res["vt_pct"], 1) if res["valid_tv"] else "—", help="Porción del valor presente explicada por el valor terminal. Más de 50 % indica que el resultado depende de lo que pase después del horizonte.")
    c7.metric("P(VAN<0)", fmt_pct(st_mc["prob_neg"], 1), "Monte Carlo v2.0", help="Probabilidad de VAN negativo según el Monte Carlo de la v2.0, que solo variaba g, WACC, CAPEX y un multiplicador del FCF₁: no ve riesgos de precio, volumen ni costos.")
    c8.metric("P50 (VAN)", fmt_money_short(st_mc["p50"]), "Monte Carlo v2.0", help="Mediana del VAN simulado: la mitad de los escenarios queda por encima y la mitad por debajo.")
    if res["valid_tv"] and st_mc["n"]:
        verdict, checks = ve.legacy_committee_check(res["van"], st_mc["prob_neg"], st_mc["p50"], st_mc["p5"])
        st.markdown(f"**Dictamen v2.0:** `{verdict}` — " + " · ".join(("✅ " if ok else "❌ ") + lab for lab, ok in checks))
    else:
        st.warning("El VT no puede calcularse: WACC ≤ g∞ + 0,5 pp.")
    if npv_mc[np.isfinite(npv_mc)].size:
        fig = go.Figure(go.Histogram(x=npv_mc[np.isfinite(npv_mc)], nbinsx=40, marker_color="#66a9ff", opacity=0.8))
        fig.add_vline(x=0, line_color="rgba(255,93,93,.85)")
        fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", showlegend=False, font=dict(color="#eaf1ff", size=10))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.info("La exportación del one-pager y la comparación de escenarios están disponibles solo en el modo corregido.")
    st.stop()

# ═════════════════════════════════════════════════════════════════════════════
# MODO CORREGIDO
# ═════════════════════════════════════════════════════════════════════════════
wacc_in = ve.WaccInputs(rf=rf, erp=erp, crp=crp, beta_u=beta_u, tax=tax_rate, debt=float(debt), equity=float(equity_bk), kd=kd,
                        size_premium=size_prem, infl_flow=pi_flow, infl_usd=pi_usd, flow_currency=CURRENCY, convert=convert)
proj = ve.Project(n_years=n_years, capex0=float(capex0), revenue_y1=float(sales_y1), var_cost_y1=float(cvar_y1),
                  fixed_cost_y1=float(cfix_y1), g_revenue=g_exp, g_fixed=g_fix, tax=tax_rate, dep_years=dep_years,
                  maint_capex_pct=maint_pct / 100, infl_capex=pi_flow, nwc_y1=float(nwc_y1), recover_nwc=recover_nwc,
                  salvage_value=float(salvage_value), ramp_years=ramp_years, ramp_start=ramp_start,
                  terminal_mode=terminal_mode, g_inf=g_inf, vt_justified=vt_just, vt_justification=vt_text, name=project)
corr = {}
if rho_pv:
    corr[("price", "volume")] = rho_pv
if rho_cf:
    corr[("unit_vc", "fixed")] = rho_cf
spec = ve.MCSpec(sims=sims, dist=dist, ranges=dict(price=r_price, volume=r_vol, unit_vc=r_vc, fixed=r_fix, capex=r_cap),
                 wacc_range=wacc_range, corr=corr, seed=seed, pess_quantile=0.0 if pess_label.startswith("Extremos") else 0.10)
try:
    ev = ve.evaluate(proj, wacc_in, spec)
except ValueError as e:
    st.error(f"No se pudo evaluar: {e}")
    st.stop()

m, wb, flw, val = ev.metrics, ev.wacc, ev.flows, ev.valuation
status_cls = {"favorable": "good", "mixto": "warn", "desfavorable": "bad"}[ev.reading.status]

hL, hR = st.columns([0.62, 0.38], gap="large")
with hL:
    st.markdown(f"""
    <div class="card">
      <div style="font-size:.98rem;font-weight:800;letter-spacing:.02em;">ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA ({CURRENCY})</div>
      <div class="small">Universidad San Ignacio de Loyola (USIL) — MBA — Proyectos de Inversión / Valuation</div>
      <div class="small">Proyecto: <b>{project}</b> &nbsp;|&nbsp; Responsable: <b>{responsible}</b> &nbsp;|&nbsp; Fecha: <b>{date.today().isoformat()}</b></div>
    </div>""", unsafe_allow_html=True)
with hR:
    st.markdown(f"""
    <div class="card" style="text-align:center;">
      <div class="small">Lectura de resultados</div>
      <div class="pill {status_cls}" style="font-size:.92rem;">{ev.reading.headline}</div>
      <div class="small" style="margin-top:6px;">{ev.reading.detail}</div>
      <div class="small" style="margin-top:4px;opacity:.8;">Resume VAN, TIR frente al WACC y probabilidad de pérdida. No es una aprobación: depende de los supuestos cargados.</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")
crit_txt = rep.describe_break(ev.critical, CURRENCY)
st.markdown(f"**Variable crítica:** {crit_txt}")
st.caption("Es la variable que, con el menor cambio relativo, lleva el VAN a cero: el supuesto que más conviene validar con datos reales.")

if ev.alerts:
    order = {"alta": 0, "media": 1, "info": 2}
    with st.container(border=True):
        st.markdown(f"**Alertas activas ({len(ev.alerts)})**")
        st.caption("Cada alerta señala un supuesto o un resultado que merece revisión. Severidad alta = puede cambiar la conclusión.")
        for a in sorted(ev.alerts, key=lambda a: (order[a.severity], a.code)):
            msg = f"**{a.code} · {a.title}.** {a.detail}"
            (st.error if a.severity == "alta" else st.warning if a.severity == "media" else st.info)(msg)
else:
    st.success("Sin alertas activas.")

# ── KPIs ─────────────────────────────────────────────────────────────────────
mode_txt = rep.MODE_LABEL[m.mode]
k = st.columns(4, gap="medium")
k[0].metric(f"VAN — {mode_txt}", fmt_money_short(m.van_main), "Indicador de decisión", help=gl.ayuda("van"))
k[1].metric("VAN sin VT", fmt_money_short(m.van_sin_vt), "Solo flujos del horizonte", help=gl.ayuda("van_sin_vt"))
k[2].metric("VAN con VT" + (" (referencial)" if m.con_vt_is_reference else ""), fmt_money_short(m.van_con_vt),
            "VT desactivado en la decisión" if m.con_vt_is_reference else "Tratamiento elegido", help=gl.ayuda("van_con_vt"))
k[3].metric("Peso del VT", fmt_pct(m.vt_weight, 1), "% del valor presente", help=gl.ayuda("vt_weight"))
k = st.columns(4, gap="medium")
k[0].metric("TIR sin VT (principal)", fmt_pct(m.irr_sin_vt), f"vs WACC {fmt_pct(m.wacc, 2)}", help=gl.ayuda("tir"))
k[1].metric("TIR con VT (secundaria)", fmt_pct(m.irr_con_vt), "Rotulada: incluye VT", help=gl.ayuda("tir_vt"))
k[2].metric("TIR modificada (sin VT)", fmt_pct(m.mirr_sin_vt), "Reinversión al WACC", help=gl.ayuda("tirm"))
k[3].metric("Índice de rentabilidad", f"{m.ir_sin_vt:.2f}", "VP flujos / CAPEX (sin VT)", help=gl.ayuda("ir"))
k = st.columns(4, gap="medium")
k[0].metric("Payback simple", f"{ve.fmt_years(m.payback)} años", "Indicador secundario", help=gl.ayuda("payback"))
k[1].metric("Payback descontado", f"{ve.fmt_years(m.payback_disc)} años", "Al WACC", help=gl.ayuda("payback_disc"))
k[2].metric("Valor anual equivalente", fmt_money_short(m.eaa), "EAA del VAN", help=gl.ayuda("eaa"))
k[3].metric("WACC (tasa usada)", ve.fmt_rate(m.wacc), f"Ke {ve.fmt_rate(wb.ke_flow)} · Kd {ve.fmt_rate(wb.kd_pre)}",
            help=gl.ayuda("wacc"))
if ev.mc is not None:
    s = ev.mc.stats
    k = st.columns(4, gap="medium")
    k[0].metric("P(VAN<0)", fmt_pct(s["prob_neg"], 1), "Monte Carlo", help=gl.ayuda("p_neg"))
    k[1].metric("P50 (VAN)", fmt_money_short(s["p50"]), f"Caso base en P{s['base_percentile'] * 100:.0f}",
                help=gl.ayuda("p50") + "\n\n---\n\n" + gl.ayuda("p5") + "\n\n---\n\n" + gl.ayuda("base_pct"))
    k[2].metric("CVaR5", fmt_money_short(s["cvar5"]), "Promedio del 5 % peor", help=gl.ayuda("cvar5"))
    k[3].metric("VAN pesimista", fmt_money_short(ev.pess_van_main), "Determinístico", help=gl.ayuda("van_pess"))

st.markdown("")

# ── WACC y variable crítica ──────────────────────────────────────────────────
cA, cB = st.container(), st.container()
with cA:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### 🧮 Tasa de descuento en {wb.rate_currency}")
    st.caption("Ke en USD (CAPM) → Ke en la moneda del flujo (diferencial de inflación) → WACC ponderado con la estructura objetivo, con el Kd después de IRE.")
    wacc_rows = [
        ("rf", "Rf (USD)", ve.fmt_rate(wb.rf)),
        ("beta_u", "β desapalancada (βU)", f"{wb.beta_u:.3f}"),
        ("beta_l", "β apalancada (βL)", f"{wb.beta_l:.3f}"),
        ("erp", "ERP", ve.fmt_rate(wb.erp)),
        ("crp", "CRP (riesgo país)", ve.fmt_rate(wb.crp)),
        ("size", "Prima por tamaño", ve.fmt_rate(wb.size_premium)),
        ("ke_usd", "Ke en USD", ve.fmt_rate(wb.ke_usd)),
        ("pi", f"π {wb.flow_currency} / π USD", f"{fmt_pct(wb.infl_flow)} / {fmt_pct(wb.infl_usd)}"),
        ("ke_flow", f"Ke en {wb.flow_currency}", ve.fmt_rate(wb.ke_flow)),
        ("kd", "Kd antes / después de IRE", f"{ve.fmt_rate(wb.kd_pre)} / {ve.fmt_rate(wb.kd_post)}"),
        ("weights", "Pesos E/V · D/V", f"{fmt_pct(wb.wE)} · {fmt_pct(wb.wD)}"),
        ("wacc", "WACC", ve.fmt_rate(wb.wacc)),
    ]
    st.markdown(edu_table(["Componente", "Valor", "Qué es, cómo se calcula y cómo leerlo"],
                          [[lab, val, gl.celda_html(k_)] for k_, lab, val in wacc_rows]), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
with cB:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎯 Punto de equilibrio (VAN = 0)")
    st.caption("Valor de cada variable que anula el VAN, manteniendo las demás constantes. La variable crítica es la más frágil.")
    be_html = []
    for b_ in ev.breakevens:
        if b_.unit == "money":
            base_t, lim_t = fmt_money(b_.base_value), ("—" if b_.limit_value is None else fmt_money(b_.limit_value))
        elif b_.unit == "pct":
            base_t, lim_t = fmt_pct(b_.base_value), ("—" if b_.limit_value is None else fmt_pct(b_.limit_value))
        else:
            base_t, lim_t = "100%", ("—" if b_.limit_value is None else f"{b_.limit_value * 100:.1f}%")
        chg_t = "—" if b_.rel_change is None else f"{b_.rel_change * 100:+.1f}%"
        crit_t = " ◄ crítica" if ev.critical is not None and b_.driver == ev.critical.driver else ""
        be_html.append([b_.label + crit_t, base_t, lim_t, chg_t, gl.celda_html(gl.BE_KEYS[b_.driver])])
    st.markdown(edu_table(["Variable", "Base", "Valor límite", "Cambio", "Qué significa y cómo leerlo"], be_html),
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")

# ── Waterfall + FCF ──────────────────────────────────────────────────────────
cC, cD = st.columns(2, gap="large")
pv_term = ve.pv_terminal(val)
with cC:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🏗️ Estructura del valor")
    st.caption("VAN = valor presente de los flujos del horizonte + valor de cierre (según el tratamiento elegido) − CAPEX inicial.")
    term_name = {"none": "Recupero\ncapital de trabajo", "salvage": "Desecho +\nrecupero CT", "perpetuity": "VT\n(perpetuidad)"}[m.mode]
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative", "relative", "relative", "total"],
        x=["PV FCF\n(1..N)", term_name, "− CAPEX₀", "VAN"],
        y=[m.pv_ops, pv_term, -capex0, 0],
        connector={"line": {"color": "rgba(255,255,255,0.12)", "width": 1}},
        increasing={"marker": {"color": "#27d17c"}}, decreasing={"marker": {"color": "#ff5d5d"}},
        totals={"marker": {"color": "#66a9ff"}},
        text=[fmt_money_short(m.pv_ops), fmt_money_short(pv_term), fmt_money_short(-capex0), fmt_money_short(m.van_main)],
        textposition="outside"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=25, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False, font=dict(color="#eaf1ff", size=10))
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)
with cD:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📈 Flujo de caja libre (FCF)")
    st.caption("Barras: FCF de cada año (verde positivo, rojo negativo). Línea punteada: valor presente acumulado de esos flujos al WACC.")
    f_ops = flw.fcf_ops[0]
    yrs = flw.years
    cum_pv = np.cumsum(f_ops / (1 + wb.wacc) ** yrs)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[f"Año {i}" for i in yrs], y=f_ops.tolist(), name="FCF",
                         marker_color=["#27d17c" if v >= 0 else "#ff5d5d" for v in f_ops]))
    fig.add_trace(go.Scatter(x=[f"Año {i}" for i in yrs], y=cum_pv.tolist(), mode="lines+markers", name="PV acumulado",
                             line=dict(color="#66a9ff", width=2, dash="dot"), yaxis="y2"))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", legend=dict(x=0.02, y=0.98, bgcolor="rgba(0,0,0,0)", font=dict(color="#eaf1ff", size=9)),
                      font=dict(color="#eaf1ff", size=10), yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.07)"),
                      yaxis2=dict(overlaying="y", side="right", showgrid=False))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

with st.expander("🔎 Detalle del flujo de caja (puente EBITDA → FCF)", expanded=False):
    st.caption("Año por año: el IRE se calcula solo si el EBIT es positivo; la depreciación se suma de vuelta porque no es caja; la reposición mantiene el negocio y el capital de trabajo crece con las ventas.")
    lines = [("Ingresos", flw.revenue[0]), ("− Costos variables", -flw.var_cost[0]), ("− Costos fijos", -flw.fixed_cost[0]),
             ("= EBITDA", flw.ebitda[0]), ("− Depreciación", -flw.dep[0]), ("= EBIT", flw.ebit[0]),
             ("− IRE (solo si EBIT > 0)", -flw.tax[0]), ("+ Depreciación", flw.dep[0]),
             ("− Δ capital de trabajo", -flw.d_nwc[0]), ("− CAPEX de reposición", -flw.capex_repl[0]), ("= FCF", flw.fcf_ops[0])]
    tbl = {"Concepto": [l for l, _ in lines]}
    for j, y_ in enumerate(yrs):
        tbl[f"Año {y_}"] = [fmt_money(v[j]) for _, v in lines]
    st.dataframe(tbl, hide_index=True, width="stretch")
    st.markdown("**¿Qué significa cada línea?**")
    _lineas = [("Ingresos", "ingresos"), ("− Costos variables", "costos_var"), ("− Costos fijos", "costos_fijos"),
               ("= EBITDA", "ebitda"), ("− Depreciación", "dep"), ("= EBIT", "ebit"), ("− IRE (solo si EBIT > 0)", "ire_row"),
               ("+ Depreciación", "dep_back"), ("− Δ capital de trabajo", "dnwc"), ("− CAPEX de reposición", "capex_repl"),
               ("= FCF", "fcf")]
    st.markdown(edu_table(["Línea", "Qué es, fórmula y cómo leerla"], [[n_, gl.celda_html(k_)] for n_, k_ in _lineas]),
                unsafe_allow_html=True)

# ── Monte Carlo ──────────────────────────────────────────────────────────────
if ev.mc is not None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🎲 Riesgo — Monte Carlo sobre drivers operativos")
    st.caption("Histograma del VAN en miles de escenarios. P5 = adverso plausible, P50 = central, P95 = favorable, CVaR5 = promedio del 5 % peor. Línea verde: caso base; amarilla: escenario pesimista.")
    s = ev.mc.stats
    st.markdown(f"<div class='small'>Sims: <b>{s['n']:,}</b> · distribución: <b>{dist}</b> · P(VAN&lt;0): <b>{fmt_pct(s['prob_neg'], 1)}</b> · "
                f"P5: <b>{fmt_money_short(s['p5'])}</b> · P50: <b>{fmt_money_short(s['p50'])}</b> · P95: <b>{fmt_money_short(s['p95'])}</b> · "
                f"media: <b>{fmt_money_short(s['mean'])}</b> · CVaR5: <b>{fmt_money_short(s['cvar5'])}</b></div>", unsafe_allow_html=True)
    x = ev.mc.npv_main
    fig = go.Figure(go.Histogram(x=x, nbinsx=40, marker_color="#66a9ff", opacity=0.8))
    fig.add_vline(x=0, line_color="rgba(255,93,93,.85)", line_width=1.8, annotation_text="VAN=0", annotation=dict(font_color="#ff5d5d", font_size=9))
    fig.add_vline(x=float(m.van_main), line_color="#27d17c", line_dash="dot", line_width=1.6, annotation_text="Caso base",
                  annotation_position="bottom right", annotation=dict(font_color="#27d17c", font_size=9))
    fig.add_vline(x=float(ev.pess_van_main), line_color="#ffcc66", line_dash="dot", line_width=1.6, annotation_text="Pesimista",
                  annotation_position="bottom left", annotation=dict(font_color="#ffcc66", font_size=9))
    for v_, lab in [(s["p5"], "P5"), (s["p50"], "P50"), (s["p95"], "P95")]:
        fig.add_vline(x=float(v_), line_dash="dash", line_color="rgba(234,241,255,.5)", annotation_text=lab, annotation=dict(font_color="#eaf1ff", font_size=9))
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False, font=dict(color="#eaf1ff", size=10), bargap=0.04)
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,.07)")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if ev.pess_van_main < 0:
        st.warning(f"El escenario pesimista determinístico tiene VAN {fmt_money(ev.pess_van_main)}: la simulación (P(VAN<0) = {fmt_pct(s['prob_neg'], 1)}) no cubre combinaciones adversas simultáneas.")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ── Sensibilidad WACC × g ────────────────────────────────────────────────────
st.header("🔍 Análisis de sensibilidad — WACC × g de ventas")
st.caption(f"VAN ({mode_txt}) recalculado variando WACC (filas) y g de ventas (columnas). Verde = VAN > 0 · Rojo = VAN < 0 · Borde azul = caso base.")
with st.expander("ℹ️ ¿Cómo leer esta tabla?", expanded=False):
    st.markdown("""
**Filas = WACC** (costo de capital): si sube, el VAN baja. **Columnas = g de ventas**: si el negocio crece más, el VAN sube.

- 🟢 **Verde**: el proyecto crea valor con esa combinación. 🔴 **Rojo**: lo destruye.
- **Borde azul** = tu caso base (valores actuales de la barra lateral).
- **Regla práctica**: si la mayoría de las celdas son verdes, el resultado es robusto frente a esos dos supuestos.
""")
WACC_D = [-0.030, -0.015, 0.0, 0.015, 0.030]
G_D = [-0.020, -0.010, 0.0, 0.010, 0.020]
sens = []
for dw in WACC_D:
    row = []
    for dg in G_D:
        pp = replace(proj, g_revenue=g_exp + dg)
        row.append(float(ve.valuate(ve.project_flows(pp), max(wb.wacc + dw, 0.01), pp).van_main[0]))
    sens.append(row)
ref = abs(m.van_main) if m.van_main else 1.0
g_th = "".join(f'<th style="padding:5px 8px;text-align:right;color:#66a9ff;font-size:.8rem;">{(g_exp + dg) * 100:.1f}%</th>' for dg in G_D)
tb = ""
for ri, (dw, rowv) in enumerate(zip(WACC_D, sens)):
    base_row = ri == 2
    tb += f'<tr style="{"background:rgba(102,169,255,0.06);" if base_row else ""}"><td style="padding:5px 8px;font-size:.8rem;font-weight:{"700" if base_row else "400"};">{(wb.wacc + dw) * 100:.2f}%</td>'
    for ci, v in enumerate(rowv):
        border = "border:2px solid #66a9ff;" if (ri == 2 and ci == 2) else ""
        alpha = 0.10 + min(abs(v) / (ref * 3 + 1), 1.0) * 0.35
        col, bgc = ("#27d17c", f"rgba(39,209,124,{alpha:.2f})") if v > 0 else ("#ff5d5d", f"rgba(255,93,93,{alpha:.2f})")
        tb += f'<td style="padding:5px 8px;text-align:right;font-size:.8rem;font-weight:700;color:{col};background:{bgc};{border}">{fmt_money_short(v)}</td>'
    tb += "</tr>"
st.markdown(f"""<div class="card" style="overflow-x:auto;"><table style="width:100%;border-collapse:collapse;">
<thead><tr><th style="padding:5px 8px;text-align:left;color:#66a9ff;font-size:.8rem;">WACC \\ g ventas</th>{g_th}</tr></thead>
<tbody>{tb}</tbody></table>
<div class="small" style="margin-top:8px;">Filas = WACC base ± 1,5 / 3 pp · Columnas = g base ± 1 / 2 pp</div></div>""", unsafe_allow_html=True)

st.divider()

# ── Comparador de escenarios ─────────────────────────────────────────────────
st.header("🧪 Comparar escenarios")
st.caption("Guardá el escenario actual, cambiá los datos y volvé a guardar para compararlos lado a lado. Si los horizontes difieren, compará por valor anual equivalente.")
if "scenarios" not in st.session_state:
    st.session_state["scenarios"] = []
wacc_key = (CURRENCY, rf, erp, crp, size_prem, beta_u, tax_rate, pi_flow, pi_usd, convert, float(debt), float(equity_bk), kd)
cc1, cc2, cc3 = st.columns([0.5, 0.25, 0.25], gap="medium")
sc_name = cc1.text_input("Nombre del escenario", f"Escenario {len(st.session_state['scenarios']) + 1}", label_visibility="collapsed",
                         help="Nombre con el que se guardará el escenario actual para compararlo con otros (por ejemplo, «Optimista» o «5 años»).")
if cc2.button("Guardar este escenario", width="stretch",
              help="Guarda los resultados actuales (VAN, TIR, WACC, valor anual equivalente) en la tabla de abajo. Cambiá los datos y volvé a guardar para comparar."):
    st.session_state["scenarios"].append(dict(name=sc_name, n_years=n_years, wacc=m.wacc, wacc_key=wacc_key, van=m.van_main,
                                              irr=m.irr_sin_vt, eaa=m.eaa, pneg=ev.mc.stats["prob_neg"] if ev.mc else float("nan")))
if cc3.button("Borrar escenarios", width="stretch", help="Vacía la tabla de escenarios guardados."):
    st.session_state["scenarios"] = []
sc = st.session_state["scenarios"]
if sc:
    st.dataframe({"Escenario": [r_["name"] for r_ in sc], "Horizonte": [r_["n_years"] for r_ in sc],
                  "WACC": [ve.fmt_rate(r_["wacc"]) for r_ in sc], f"VAN ({CURRENCY})": [fmt_money(r_["van"]) for r_ in sc],
                  "TIR sin VT": [fmt_pct(r_["irr"]) for r_ in sc], "Valor anual equivalente": [fmt_money(r_["eaa"]) for r_ in sc],
                  "P(VAN<0)": [fmt_pct(r_["pneg"], 1) for r_ in sc]}, hide_index=True, width="stretch",
                 column_config={"WACC": st.column_config.TextColumn("WACC", help=gl.ayuda("wacc")),
                                f"VAN ({CURRENCY})": st.column_config.TextColumn(f"VAN ({CURRENCY})", help=gl.ayuda("van")),
                                "TIR sin VT": st.column_config.TextColumn("TIR sin VT", help=gl.ayuda("tir")),
                                "Valor anual equivalente": st.column_config.TextColumn("Valor anual equivalente", help=gl.ayuda("eaa")),
                                "P(VAN<0)": st.column_config.TextColumn("P(VAN<0)", help=gl.ayuda("p_neg"))})
    for a in ve.compare_scenarios(sc):
        (st.error if a.severity == "alta" else st.warning)(f"**{a.code} · {a.title}.** {a.detail}")
else:
    st.caption("Guardá varios escenarios para compararlos. Si los horizontes difieren, comparar por valor anual equivalente.")

st.divider()

# ── Glosario académico ───────────────────────────────────────────────────────
with st.expander("📚 Glosario académico — conceptos y fórmulas de esta calculadora", expanded=False):
    st.caption("Material de estudio: cada concepto con su definición, su fórmula, cómo interpretarlo y su base teórica.")
    _grupos = [
        ("Costo del capital (WACC)", ["rf", "beta_u", "beta_l", "erp", "crp", "size", "ke_usd", "pi", "ke_flow", "kd", "weights", "wacc", "ire"]),
        ("Flujo de caja libre", ["ingresos", "costos_var", "costos_fijos", "ebitda", "dep", "ebit", "ire_row", "dnwc", "capex_repl", "fcf"]),
        ("Criterios de decisión", ["van", "van_sin_vt", "van_con_vt", "vt_weight", "tir", "tir_vt", "tirm", "ir", "payback", "payback_disc", "eaa"]),
        ("Riesgo", ["p_neg", "p50", "p5", "cvar5", "van_pess", "base_pct"]),
        ("Punto de equilibrio", ["be_price", "be_volume", "be_unit_vc", "be_fixed", "be_capex", "be_wacc"]),
    ]
    for _titulo, _keys in _grupos:
        st.markdown(f"**{_titulo}**")
        st.markdown(edu_table(["Concepto", "Definición, fórmula y cómo leerlo"], [[gl.G[k_]["nombre"], gl.celda_html(k_)] for k_ in _keys]),
                    unsafe_allow_html=True)

# ── Export ───────────────────────────────────────────────────────────────────
st.header("📥 Export")
st.caption("Descargá el resumen de una página con indicadores, desglose de la tasa, alertas, escenario pesimista y la sección de supuestos y limitaciones.")
onepager = rep.OnePager(
    ev=ev, currency=CURRENCY, institution="Universidad San Ignacio de Loyola (USIL)",
    program="Maestría en Administración de Negocios (MBA)", course="Proyectos de Inversión / Valuation",
    project=project, responsible=responsible, programa=programa, integrantes=integrantes,
    report_date=date.today().isoformat())
d1, d2 = st.columns(2, gap="medium")
with d1:
    st.download_button("⬇️ Descargar One-Pager (TXT)", data=rep.build_onepager_text(onepager).encode("utf-8"),
                       file_name="one_pager_usil.txt", mime="text/plain", width="stretch")
with d2:
    if rep.REPORTLAB_OK:
        hc, he = (np.histogram(ev.mc.npv_main, bins=36) if ev.mc is not None else (None, None))
        st.download_button("⬇️ Descargar One-Pager (PDF)", data=rep.generate_onepager_pdf(onepager, hc, he),
                           file_name="one_pager_usil.pdf", mime="application/pdf", width="stretch")
    else:
        st.info("Para exportar PDF, instalar `reportlab`.")

st.markdown(
    "<div class='small' style='text-align:center;margin-top:10px;'>Uso académico (MBA). Estimaciones basadas en supuestos del usuario; "
    "no son una recomendación de inversión. · ValuationSuite USIL v" + ve.ENGINE_VERSION + "</div>", unsafe_allow_html=True)

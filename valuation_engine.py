# valuation_engine.py — ValuationSuite USIL v3.0
# Motor de evaluación de proyectos SIN dependencias de Streamlit (testeable y reutilizable).
#
# Contenido
#   1. Modo COMPATIBILIDAD (legacy_*): fórmulas de la v2.0, con sus defectos D1–D8 conocidos.
#      Existe solo para reproducir resultados históricos (tests T6 / backtest). No usar para decidir.
#   2. WACC en la moneda del flujo (C3).
#   3. Motor de flujo de caja desagregado (C5) + valor terminal opcional (C1).
#   4. Métricas: VAN/TIR con y sin VT, TIRM, IR, payback (C1, C2, C7).
#   5. Monte Carlo sobre drivers operativos (C4).
#   6. Punto de equilibrio / variable crítica (C8).
#   7. Validaciones con alertas (C6) y lectura de resultados (C8).

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from statistics import NormalDist
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import numpy_financial as npf

ENGINE_VERSION = "3.0"
MIN_SPREAD = 0.005          # solo modo compatibilidad: WACC > g∞ + 0,5 pp
G_INF_MARGIN = 0.02         # C4: g∞ ≤ WACC − 2 pp (modo corregido)

# Umbrales de las validaciones C6 (documentados y editables en un único lugar).
THRESHOLDS = dict(
    irr_high=0.50,               # TIR > 50 %
    payback_fast_years=2.0,      # payback < 2 años ...
    capex_significant_ratio=0.25,  # ... con CAPEX₀ ≥ 25 % de las ventas del Año 1
    vt_weight=0.50,              # VT > 50 % del valor
    g_explicit_max=0.10,         # g explícito > 10 % ...
    g_explicit_years=3,          # ... por más de 3 años
    fcf_ebit_min=0.30,           # FCF/EBIT razonable: [0,30 ; 1,50]
    fcf_ebit_max=1.50,
    prob_neg_ok=0.20,
)

DRIVERS = ("price", "volume", "unit_vc", "fixed", "capex", "wacc")
DRIVER_LABELS = {
    "price": "Precio (ingresos Año 1)",
    "volume": "Volumen / ocupación",
    "unit_vc": "Costo variable (Año 1)",
    "fixed": "Costos fijos (Año 1)",
    "capex": "CAPEX inicial",
    "wacc": "WACC",
}


# ═════════════════════════════════════════════════════════════════════════════
# Utilidades de formato numérico
# ═════════════════════════════════════════════════════════════════════════════
def round_half_up(x: float, ndigits: int = 2) -> float:
    """Redondeo comercial (no trunca, no usa redondeo bancario)."""
    q = Decimal(1).scaleb(-ndigits)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))


def fmt_years(x: Optional[float], nd: int = 2) -> str:
    """Payback redondeado (C7): 1,48 → '1,48' y 1,4186 → '1,42'; nunca truncado."""
    if x is None or not math.isfinite(x):
        return "N/D"
    return f"{round_half_up(x, nd):.{nd}f}"


def fmt_num(x: Optional[float], nd: int = 0) -> str:
    """Número con separador de miles '.' y decimal ',' (convención es-PY)."""
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_rate(x: Optional[float], nd: int = 4) -> str:
    """Tasa con la precisión con que se usa en el cálculo (C7)."""
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x * 100:.{nd}f}%"


# ═════════════════════════════════════════════════════════════════════════════
# 1) MODO COMPATIBILIDAD — fórmulas v2.0 (NO usar para decidir)
# ═════════════════════════════════════════════════════════════════════════════
def legacy_wacc(rf: float, erp: float, crp: float, beta_u: float, tax: float,
                debt: float, equity: float, kd: float) -> dict:
    """CAPM en USD aplicado tal cual al flujo (D3): sin diferencial de inflación."""
    V = max(debt + equity, 1e-9)
    wD, wE = debt / V, equity / V
    beta_l = beta_u * (1 + (1 - tax) * (debt / max(equity, 1e-9)))
    ke = rf + beta_l * erp + crp
    return dict(ke=ke, beta_l=beta_l, wD=wD, wE=wE, wacc=wE * ke + wD * kd * (1 - tax))


def legacy_safe_irr(cashflows: Sequence[float]) -> Optional[float]:
    """TIR con las mismas reglas de la v2.0 (descarta < −99 % y > 200 %)."""
    try:
        irr = float(npf.irr(cashflows))
        if not np.isfinite(irr) or irr < -0.99 or irr > 2.0:
            return None
        return irr
    except Exception:
        return None


def legacy_payback(capex0: float, flows: Sequence[float], wacc: Optional[float] = None) -> Optional[float]:
    """Payback simple (wacc=None) o descontado, con interpolación lineal intra-año."""
    cum = -capex0
    for i, f in enumerate(flows, 1):
        v = f if wacc is None else f / (1 + wacc) ** i
        prev = cum
        cum += v
        if cum >= 0:
            return float(i - 1 + ((0 - prev) / v if v != 0 else 0.0))
    return None


def legacy_fcf1(sales: float, cvar: float, cfix: float, dep: float, capex_y1: float,
                delta_wc: float, tax: float) -> dict:
    """Puente contable de la v2.0. NOTA (D5): NOPAT = EBIT·(1−T) aun con EBIT < 0 (crédito fiscal ficticio)."""
    ebit = sales - cvar - cfix - dep
    nopat = ebit * (1 - tax)
    return dict(ebit=ebit, nopat=nopat, fcf1=nopat + dep - capex_y1 - delta_wc)


def legacy_dcf(capex0: float, n_years: int, wacc: float, g_inf: float,
               fcf1: Optional[float] = None, g: Optional[float] = None,
               fcfs: Optional[Sequence[float]] = None) -> dict:
    """VAN = Σ FCF_t/(1+WACC)^t + [FCF_N(1+g∞)/(WACC−g∞)]/(1+WACC)^N − CAPEX₀.
    FCF_t = FCF₁(1+g)^(t−1) (o la serie `fcfs`). TIR incluye el VT como caja del año N."""
    yrs = np.arange(1, n_years + 1)
    f = np.asarray(fcfs, float) if fcfs is not None else float(fcf1) * (1 + float(g)) ** (yrs - 1)
    valid = wacc > g_inf + MIN_SPREAD
    pv_fcf = float(np.sum(f / (1 + wacc) ** yrs))
    out = dict(fcf=f, pv_fcf=pv_fcf, valid_tv=bool(valid), wacc=wacc,
               van_sin_vt=pv_fcf - capex0,
               irr_sin_vt=_irr_or_none([-capex0, *f]),
               payback=legacy_payback(capex0, f), payback_disc=legacy_payback(capex0, f, wacc))
    if valid:
        tv = float(f[-1] * (1 + g_inf) / (wacc - g_inf))
        pv_tv = tv / (1 + wacc) ** n_years
        cfs = [-capex0, *f]
        cfs[-1] += tv
        out.update(tv=tv, pv_tv=pv_tv, van=pv_fcf + pv_tv - capex0, vt_pct=pv_tv / (pv_fcf + pv_tv),
                   irr=legacy_safe_irr(cfs), irr_raw=_irr_or_none(cfs))
    else:
        out.update(tv=float("nan"), pv_tv=float("nan"), van=float("nan"), vt_pct=float("nan"),
                   irr=None, irr_raw=None)
    return out


def legacy_committee_check(npv_base, prob_neg, p50, p5):
    """Criterio de la v2.0 (D8): 4 chequeos → APROBADO / OBSERVADO / RECHAZADO."""
    checks = [("VAN base > 0", npv_base > 0), ("P(VAN<0) ≤ 20%", prob_neg <= 0.20),
              ("P50(VAN) > 0", p50 > 0), ("P5(VAN) > 0", p5 > 0)]
    ok = sum(b for _, b in checks)
    return ("APROBADO" if ok == len(checks) else "RECHAZADO" if ok == 0 else "OBSERVADO"), checks


def legacy_monte_carlo(sims, fcf_y1, n_years, g_inf, g_rng, w_rng, capex_rng, mult_rng, seed=None):
    """Monte Carlo v2.0: solo g, WACC, CAPEX y un multiplicador de FCF₁ (D4)."""
    rng = np.random.default_rng(seed)
    g_s = rng.triangular(*g_rng, sims)
    w_s = rng.triangular(*w_rng, sims)
    c_s = rng.triangular(*capex_rng, sims)
    m_s = rng.triangular(*mult_rng, sims)
    yrs = np.arange(1, n_years + 1)
    fcf = (fcf_y1 * m_s)[:, None] * (1 + g_s)[:, None] ** (yrs[None, :] - 1)
    ok = w_s > g_inf + MIN_SPREAD
    npv = np.full(sims, np.nan)
    i = np.where(ok)[0]
    if i.size:
        fv = fcf[i].copy()
        fv[:, -1] += fv[:, -1] * (1 + g_inf) / (w_s[i] - g_inf)
        npv[i] = np.sum(fv / (1 + w_s[i])[:, None] ** yrs[None, :], axis=1) - c_s[i]
    return npv


def _irr_or_none(cfs) -> Optional[float]:
    try:
        v = float(npf.irr(list(cfs)))
        return v if np.isfinite(v) else None
    except Exception:
        return None


def mc_stats(npv: np.ndarray, base: Optional[float] = None) -> dict:
    """Estadísticos de una distribución de VAN (incluye CVaR5 y posición del caso base)."""
    x = np.asarray(npv, float)
    valid = np.isfinite(x)
    x = x[valid]
    if x.size == 0:
        nan = float("nan")
        return dict(n=0, valid_rate=0.0, prob_neg=nan, mean=nan, std=nan, p5=nan, p50=nan, p95=nan,
                    cvar5=nan, base_percentile=nan)
    p5, p50, p95 = np.percentile(x, [5, 50, 95])
    tail = x[x <= p5]
    return dict(n=int(x.size), valid_rate=float(valid.mean()), prob_neg=float((x < 0).mean()),
                mean=float(x.mean()), std=float(x.std()), p5=float(p5), p50=float(p50), p95=float(p95),
                cvar5=float(tail.mean()) if tail.size else float(p5),
                base_percentile=float((x < base).mean()) if base is not None else float("nan"))


# ═════════════════════════════════════════════════════════════════════════════
# 2) WACC EN LA MONEDA DEL FLUJO (C3)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class WaccInputs:
    rf: float                    # tasa libre de riesgo (USD)
    erp: float                   # prima de riesgo de mercado (USD)
    crp: float                   # prima de riesgo país
    beta_u: float                # beta desapalancada
    tax: float                   # IRE
    debt: float
    equity: float
    kd: float                    # costo de la deuda ANTES de impuestos, en la moneda del flujo
    size_premium: float = 0.0    # prima por tamaño (opcional)
    infl_flow: float = 0.0       # π de la moneda del flujo
    infl_usd: float = 0.0        # π del USD
    flow_currency: str = "PYG"
    convert: bool = True         # False = comportamiento v2.0 (sin conversión; dispara V07)


@dataclass
class WaccBreakdown:
    rf: float
    beta_u: float
    beta_l: float
    erp: float
    crp: float
    size_premium: float
    ke_usd: float
    infl_flow: float
    infl_usd: float
    ke_flow: float
    kd_pre: float
    kd_post: float
    tax: float
    wE: float
    wD: float
    wacc: float
    flow_currency: str
    rate_currency: str           # moneda en que está expresada la tasa
    converted: bool

    @property
    def mismatch(self) -> bool:
        """V07: la tasa no está en la moneda del flujo."""
        return self.flow_currency != "USD" and not self.converted


def wacc_breakdown(w: WaccInputs) -> WaccBreakdown:
    """Ke_flow = (1+Ke_USD)(1+π_flow)/(1+π_USD) − 1 ; Kd después de IRE ; pesos E/V y D/V explícitos."""
    V = max(w.debt + w.equity, 1e-9)
    wD, wE = w.debt / V, w.equity / V
    beta_l = w.beta_u * (1 + (1 - w.tax) * (w.debt / max(w.equity, 1e-9)))
    ke_usd = w.rf + beta_l * w.erp + w.crp + w.size_premium
    in_usd = w.flow_currency == "USD"
    pi_flow = w.infl_usd if in_usd else w.infl_flow
    converted = in_usd or w.convert
    ke_flow = (1 + ke_usd) * (1 + pi_flow) / (1 + w.infl_usd) - 1 if converted else ke_usd
    kd_post = w.kd * (1 - w.tax)
    rate_cur = w.flow_currency if converted else "USD (sin convertir)"
    return WaccBreakdown(rf=w.rf, beta_u=w.beta_u, beta_l=beta_l, erp=w.erp, crp=w.crp,
                         size_premium=w.size_premium, ke_usd=ke_usd, infl_flow=pi_flow,
                         infl_usd=w.infl_usd, ke_flow=ke_flow, kd_pre=w.kd, kd_post=kd_post,
                         tax=w.tax, wE=wE, wD=wD, wacc=wE * ke_flow + wD * kd_post,
                         flow_currency=w.flow_currency, rate_currency=rate_cur, converted=converted)


def wacc_from_reported(wacc: float, ke_usd: Optional[float] = None, kd_pre: Optional[float] = None,
                       tax: float = 0.10, flow_currency: str = "PYG", infl_flow: float = 0.0,
                       infl_usd: float = 0.0, convert: bool = True) -> WaccBreakdown:
    """Reconstruye un desglose a partir de tasas ya reportadas (para el backtest de fixtures).
    Los pesos se DESPEJAN: wD = (Ke − WACC)/(Ke − Kd(1−T)). Es una derivación, no un dato."""
    ke = wacc if ke_usd is None else ke_usd
    kdp = (kd_pre or 0.0) * (1 - tax)
    wD = 0.0
    if kd_pre is not None and abs(ke - kdp) > 1e-12:
        wD = min(max((ke - wacc) / (ke - kdp), 0.0), 1.0)
    wE = 1 - wD
    in_usd = flow_currency == "USD"
    pi_f = infl_usd if in_usd else infl_flow
    conv = in_usd or convert
    ke_f = (1 + ke) * (1 + pi_f) / (1 + infl_usd) - 1 if conv else ke
    w_new = wE * ke_f + wD * kdp
    return WaccBreakdown(rf=float("nan"), beta_u=float("nan"), beta_l=float("nan"), erp=float("nan"),
                         crp=float("nan"), size_premium=0.0, ke_usd=ke, infl_flow=pi_f, infl_usd=infl_usd,
                         ke_flow=ke_f, kd_pre=kd_pre if kd_pre is not None else float("nan"), kd_post=kdp,
                         tax=tax, wE=wE, wD=wD, wacc=w_new if conv else wacc, flow_currency=flow_currency,
                         rate_currency=flow_currency if conv else "USD (sin convertir)", converted=conv)


# ═════════════════════════════════════════════════════════════════════════════
# 3) MOTOR DE FLUJO DE CAJA DESAGREGADO (C5) + VALOR TERMINAL (C1)
# ═════════════════════════════════════════════════════════════════════════════
TERMINAL_MODES = ("none", "salvage", "perpetuity")


@dataclass
class Project:
    n_years: int
    capex0: float
    revenue_y1: float = 0.0           # ventas del Año 1 A CAPACIDAD PLENA (antes de rampa)
    var_cost_y1: float = 0.0
    fixed_cost_y1: float = 0.0
    g_revenue: float = 0.05           # crecimiento anual de ventas
    g_fixed: Optional[float] = None   # crecimiento de costos fijos (None → igual a g_revenue)
    tax: float = 0.10                 # IRE: solo sobre EBIT > 0
    dep_years: int = 10               # vida contable (línea recta)
    maint_capex_pct: float = 1.0      # reposición anual = % × depreciación de la base inicial (≥ 100 %)
    infl_capex: float = 0.0           # indexación del CAPEX de reposición
    nwc_y1: float = 0.0               # capital de trabajo (AR+INV−AP) al cierre del Año 1, a plena capacidad
    recover_nwc: bool = True          # se recupera al final si el proyecto termina
    salvage_value: float = 0.0        # valor de desecho BRUTO en el año N
    ramp_years: int = 0               # años de rampa (0 = sin rampa)
    ramp_start: float = 1.0           # nivel del Año 1 (fracción de la capacidad plena)
    terminal_mode: str = "none"       # none | salvage | perpetuity
    g_inf: float = 0.02
    vt_justified: bool = False        # C1(iii): la perpetuidad exige justificar la continuidad
    vt_justification: str = ""
    # Modo FCF directo (fixtures / usuarios que ya traen su flujo): omite el desglose.
    fcf_direct: Optional[Sequence[float]] = None
    ebit_reported: Optional[float] = None   # EBIT del Año 1 informado (solo para la validación V06)
    name: str = ""

    def effective_mode(self) -> str:
        if self.terminal_mode == "perpetuity" and not self.vt_justified:
            return "none"
        return self.terminal_mode if self.terminal_mode in TERMINAL_MODES else "none"


@dataclass
class Flows:
    """Flujos por escenario: arrays (S, N). S = 1 en el caso determinístico."""
    years: np.ndarray
    revenue: np.ndarray
    var_cost: np.ndarray
    fixed_cost: np.ndarray
    ebitda: np.ndarray
    dep: np.ndarray
    ebit: np.ndarray
    tax: np.ndarray
    d_nwc: np.ndarray
    capex_repl: np.ndarray
    fcf_ops: np.ndarray            # FCF operativo (sin ítems terminales)
    capex0: np.ndarray             # (S,)
    nwc_end: np.ndarray            # (S,) capital de trabajo a recuperar
    salvage_net: np.ndarray        # (S,) desecho neto de IRE
    book_end: np.ndarray           # (S,) valor libro al año N
    tax_rate: float

    def norm_fcf(self, g) -> np.ndarray:
        """FCF normalizado del año N+1 (C1-iii): reinversión ≥ depreciación (estado estacionario)."""
        g = np.asarray(g, float)
        eb = self.ebitda[:, -1] * (1 + g)
        capex_n = np.maximum(self.capex_repl[:, -1], self.dep[:, -1]) * (1 + g)
        tax_n = self.tax_rate * np.maximum(eb - capex_n, 0.0)
        return eb - tax_n - capex_n - self.nwc_end * g


def _b(x, S):
    return np.broadcast_to(np.atleast_1d(np.asarray(x, float)), (S,)).copy()


def project_flows(p: Project, price_m=1.0, vol_m=1.0, vc_m=1.0, fix_m=1.0, capex_m=1.0) -> Flows:
    """Calcula el flujo para uno o muchos escenarios de drivers (multiplicadores sobre el caso base)."""
    S = max(np.atleast_1d(np.asarray(a)).size for a in (price_m, vol_m, vc_m, fix_m, capex_m))
    price_m, vol_m, vc_m, fix_m, capex_m = (_b(a, S) for a in (price_m, vol_m, vc_m, fix_m, capex_m))
    N = int(p.n_years)
    t = np.arange(1, N + 1)
    capex0 = p.capex0 * capex_m
    zeros = np.zeros((S, N))

    if p.fcf_direct is not None:
        fcf = np.asarray(p.fcf_direct, float)[None, :] * vol_m[:, None]
        return Flows(years=t, revenue=zeros, var_cost=zeros, fixed_cost=zeros, ebitda=fcf.copy(),
                     dep=zeros, ebit=fcf.copy(), tax=zeros, d_nwc=zeros, capex_repl=zeros, fcf_ops=fcf,
                     capex0=capex0, nwc_end=np.zeros(S), salvage_net=np.zeros(S),
                     book_end=np.zeros(S), tax_rate=0.0)

    g_fix = p.g_revenue if p.g_fixed is None else p.g_fixed
    k = int(p.ramp_years)
    ramp = np.ones(N) if k <= 0 else np.minimum(1.0, p.ramp_start + (1 - p.ramp_start) * (t - 1) / k)
    rev_base = p.revenue_y1 * (1 + p.g_revenue) ** (t - 1) * ramp                  # (N,)
    vc_ratio = p.var_cost_y1 / p.revenue_y1 if p.revenue_y1 else 0.0
    revenue = rev_base[None, :] * (price_m * vol_m)[:, None]
    var_cost = vc_ratio * rev_base[None, :] * (vol_m * vc_m)[:, None]
    fixed = (p.fixed_cost_y1 * (1 + g_fix) ** (t - 1))[None, :] * fix_m[:, None]
    ebitda = revenue - var_cost - fixed

    # Depreciación línea recta de la base inicial y de cada reposición (desde el año siguiente).
    L = max(int(p.dep_years), 1)
    base = capex0 / L
    repl = p.maint_capex_pct * base[:, None] * (1 + p.infl_capex) ** (t - 1)[None, :]
    dep = np.zeros((S, N))
    for ti in range(1, N + 1):
        if ti <= L:
            dep[:, ti - 1] += base
    for si in range(1, N + 1):
        for ti in range(si + 1, min(N, si + L) + 1):
            dep[:, ti - 1] += repl[:, si - 1] / L

    ebit = ebitda - dep
    tax = p.tax * np.maximum(ebit, 0.0)                         # IRE solo si EBIT > 0
    nwc_ratio = p.nwc_y1 / p.revenue_y1 if p.revenue_y1 else 0.0
    nwc = nwc_ratio * revenue
    d_nwc = np.diff(np.concatenate([np.zeros((S, 1)), nwc], axis=1), axis=1)
    fcf = ebitda - tax - d_nwc - repl

    book_end = capex0 + repl.sum(1) - dep.sum(1)
    gain = np.maximum(p.salvage_value - book_end, 0.0)
    salvage_net = p.salvage_value - p.tax * gain
    return Flows(years=t, revenue=revenue, var_cost=var_cost, fixed_cost=fixed, ebitda=ebitda, dep=dep,
                 ebit=ebit, tax=tax, d_nwc=d_nwc, capex_repl=repl, fcf_ops=fcf, capex0=capex0,
                 nwc_end=nwc[:, -1], salvage_net=salvage_net, book_end=book_end, tax_rate=p.tax)


@dataclass
class Valuation:
    """Valores presentes y VAN por escenario (arrays (S,))."""
    pv_ops: np.ndarray
    pv_nwc: np.ndarray
    pv_salvage: np.ndarray
    pv_vt: np.ndarray
    vt: np.ndarray
    g_eff: np.ndarray
    van_sin_vt: np.ndarray
    van_con_vt: np.ndarray       # con el VT del modo elegido (o perpetuidad de REFERENCIA si el modo es 'none')
    van_main: np.ndarray         # VAN del modo elegido (decisión)
    vt_weight: np.ndarray
    con_vt_is_reference: bool
    mode: str


def valuate(fl: Flows, w, p: Project) -> Valuation:
    w = _b(w, fl.fcf_ops.shape[0])
    N = fl.fcf_ops.shape[1]
    df = (1 + w)[:, None] ** (-fl.years[None, :].astype(float))
    dfN = df[:, -1]
    mode = p.effective_mode()
    pv_ops = (fl.fcf_ops * df).sum(1)
    pv_nwc = (fl.nwc_end * dfN) if p.recover_nwc else np.zeros_like(dfN)
    pv_salv = fl.salvage_net * dfN
    g_eff = np.minimum(p.g_inf, w - G_INF_MARGIN)
    vt = fl.norm_fcf(g_eff) / (w - g_eff)
    pv_vt = vt * dfN
    van_sin = pv_ops + pv_nwc - fl.capex0
    van_salv = van_sin + pv_salv
    van_perp = pv_ops + pv_vt - fl.capex0
    van_main = {"none": van_sin, "salvage": van_salv, "perpetuity": van_perp}[mode]
    if mode == "salvage":
        van_con, weight, ref = van_salv, pv_salv / np.where(pv_ops + pv_nwc + pv_salv == 0, np.nan,
                                                            pv_ops + pv_nwc + pv_salv), False
    else:
        van_con, ref = van_perp, mode == "none"
        weight = pv_vt / np.where(pv_ops + pv_vt == 0, np.nan, pv_ops + pv_vt)
    return Valuation(pv_ops=pv_ops, pv_nwc=pv_nwc, pv_salvage=pv_salv, pv_vt=pv_vt, vt=vt, g_eff=g_eff,
                     van_sin_vt=van_sin, van_con_vt=van_con, van_main=van_main, vt_weight=weight,
                     con_vt_is_reference=ref, mode=mode)


def pv_terminal(val: Valuation) -> float:
    """Valor presente de los ítems de cierre del modo elegido (recupero de CT / desecho / VT perpetuo)."""
    return float({"none": val.pv_nwc, "salvage": val.pv_nwc + val.pv_salvage, "perpetuity": val.pv_vt}[val.mode][0])


@dataclass
class Metrics:
    wacc: float
    van_main: float
    van_sin_vt: float
    van_con_vt: float
    con_vt_is_reference: bool
    vt_weight: float
    pv_ops: float
    pv_vt: float
    vt: float
    irr_sin_vt: Optional[float]         # TIR PRINCIPAL (C2)
    irr_con_vt: Optional[float]         # indicador secundario, rotulado "con VT"
    mirr_sin_vt: Optional[float]
    mirr_con_vt: Optional[float]
    ir_sin_vt: float
    ir_con_vt: float
    payback: Optional[float]
    payback_disc: Optional[float]
    mode: str
    eaa: Optional[float] = None         # valor anual equivalente del VAN (comparar proyectos de distinta vida)
    sign_changes: int = 0               # cambios de signo del flujo (>1 ⇒ la TIR puede no ser única)


def equivalent_annual_annuity(van: float, rate: float, n_years: int) -> Optional[float]:
    """EAA = VAN · r / (1 − (1+r)^−N). Permite comparar proyectos mutuamente excluyentes con vidas distintas."""
    if rate <= 0 or n_years <= 0:
        return None
    return van * rate / (1 - (1 + rate) ** (-n_years))


def _sign_changes(cfs) -> int:
    sg = [np.sign(x) for x in cfs if x != 0]
    return int(sum(1 for a, b in zip(sg, sg[1:]) if a != b))


def _metrics(fl: Flows, val: Valuation, wacc: float, p: Project) -> Metrics:
    ops = fl.fcf_ops[0]
    c0 = float(fl.capex0[0])
    nwc = float(fl.nwc_end[0]) if p.recover_nwc else 0.0
    sin = [-c0, *ops]
    sin[-1] += nwc
    mode = val.mode
    if mode == "salvage":
        con = [-c0, *ops]
        con[-1] += nwc + float(fl.salvage_net[0])
    else:
        con = [-c0, *ops]
        con[-1] += float(val.vt[0])

    def mirr(cfs):
        try:
            v = float(npf.mirr(cfs, wacc, wacc))
            return v if np.isfinite(v) else None
        except Exception:
            return None

    return Metrics(
        wacc=float(wacc), van_main=float(val.van_main[0]), van_sin_vt=float(val.van_sin_vt[0]),
        van_con_vt=float(val.van_con_vt[0]), con_vt_is_reference=val.con_vt_is_reference,
        vt_weight=float(val.vt_weight[0]), pv_ops=float(val.pv_ops[0]), pv_vt=float(val.pv_vt[0]),
        vt=float(val.vt[0]), irr_sin_vt=_irr_or_none(sin), irr_con_vt=_irr_or_none(con),
        mirr_sin_vt=mirr(sin), mirr_con_vt=mirr(con),
        ir_sin_vt=float(1 + val.van_sin_vt[0] / c0), ir_con_vt=float(1 + val.van_con_vt[0] / c0),
        payback=legacy_payback(c0, sin[1:]), payback_disc=legacy_payback(c0, sin[1:], wacc), mode=mode,
        eaa=equivalent_annual_annuity(float(val.van_main[0]), float(wacc), len(ops)),
        sign_changes=_sign_changes(sin))


# ═════════════════════════════════════════════════════════════════════════════
# 4) MONTE CARLO SOBRE DRIVERS OPERATIVOS (C4)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class MCSpec:
    sims: int = 10_000
    dist: str = "triangular"                     # "triangular" | "normal" (normal truncada al rango)
    # (mín, moda, máx) como MULTIPLICADORES del caso base. En modo FCF directo, 'volume' escala el FCF.
    ranges: Dict[str, Tuple[float, float, float]] = field(default_factory=lambda: {
        "price": (0.92, 1.00, 1.08), "volume": (0.90, 1.00, 1.10), "unit_vc": (0.92, 1.00, 1.10),
        "fixed": (0.95, 1.00, 1.10), "capex": (0.95, 1.00, 1.15)})
    wacc_range: float = 0.02                     # WACC ∈ [WACC − r, WACC + r]
    corr: Dict[Tuple[str, str], float] = field(default_factory=dict)   # correlaciones opcionales
    seed: Optional[int] = None
    pess_quantile: float = 0.0                   # 0 = extremos del rango; 0,10 = P10 adverso de cada driver

    def pessimistic(self) -> dict:
        """Escenario pesimista determinístico: cada driver en su lado adverso, todos a la vez.
        pess_quantile = 0 → extremo del rango; q > 0 → cuantil q (lado adverso) de su distribución."""
        r, q = self.ranges, float(self.pess_quantile)
        if q <= 0:
            return dict(price=r["price"][0], volume=r["volume"][0], unit_vc=r["unit_vc"][2],
                        fixed=r["fixed"][2], capex=r["capex"][2], wacc=self.wacc_range)

        def qv(key, u):
            return float(_quantile(self.dist, np.array([u]), *r[key])[0])
        return dict(price=qv("price", q), volume=qv("volume", q), unit_vc=qv("unit_vc", 1 - q),
                    fixed=qv("fixed", 1 - q), capex=qv("capex", 1 - q),
                    wacc=float(_quantile(self.dist, np.array([1 - q]), -self.wacc_range, 0.0, self.wacc_range)[0]))


@dataclass
class MCResult:
    npv_main: np.ndarray
    npv_sin_vt: np.ndarray
    stats: dict
    stats_sin_vt: dict
    spec: MCSpec


_PHI = np.vectorize(NormalDist().cdf, otypes=[float])
_PHI_INV = np.vectorize(NormalDist().inv_cdf, otypes=[float])


def _quantile(dist: str, u: np.ndarray, lo: float, mode: float, hi: float) -> np.ndarray:
    if hi <= lo:
        return np.full_like(u, mode)
    if dist == "normal":
        mu, sd = mode, (hi - lo) / 4.0
        a, b = NormalDist(mu, sd).cdf(lo), NormalDist(mu, sd).cdf(hi)
        z = _PHI_INV(np.clip(a + u * (b - a), 1e-12, 1 - 1e-12))
        return np.clip(mu + sd * z, lo, hi)
    fc = (mode - lo) / (hi - lo)
    return np.where(u < fc, lo + np.sqrt(u * (hi - lo) * (mode - lo)),
                    hi - np.sqrt((1 - u) * (hi - lo) * (hi - mode)))


def _draw(spec: MCSpec) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(spec.seed)
    S = int(spec.sims)
    keys = list(DRIVERS)
    if spec.corr:
        R = np.eye(len(keys))
        for (a, b), rho in spec.corr.items():
            i, j = keys.index(a), keys.index(b)
            R[i, j] = R[j, i] = rho
        try:
            Lc = np.linalg.cholesky(R)
        except np.linalg.LinAlgError as e:
            raise ValueError("La matriz de correlaciones no es definida positiva.") from e
        U = _PHI(rng.standard_normal((S, len(keys))) @ Lc.T)
    else:
        U = rng.random((S, len(keys)))
    out = {}
    for c, key in enumerate(keys):
        if key == "wacc":
            r = spec.wacc_range
            out[key] = _quantile(spec.dist, U[:, c], -r, 0.0, r)
        else:
            lo, mo, hi = spec.ranges[key]
            out[key] = _quantile(spec.dist, U[:, c], lo, mo, hi)
    return out


def run_monte_carlo(p: Project, wacc: float, spec: MCSpec, base_van: Optional[float] = None) -> MCResult:
    d = _draw(spec)
    fl = project_flows(p, d["price"], d["volume"], d["unit_vc"], d["fixed"], d["capex"])
    val = valuate(fl, np.maximum(wacc + d["wacc"], 0.01), p)
    return MCResult(npv_main=val.van_main, npv_sin_vt=val.van_sin_vt,
                    stats=mc_stats(val.van_main, base_van), stats_sin_vt=mc_stats(val.van_sin_vt, float(base_van) if base_van is not None else None),
                    spec=spec)


# ═════════════════════════════════════════════════════════════════════════════
# 5) PUNTO DE EQUILIBRIO / VARIABLE CRÍTICA (C8)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class BreakEven:
    driver: str
    label: str
    base_value: float
    limit_value: Optional[float]
    rel_change: Optional[float]     # variación relativa que anula el VAN (p. ej. −0,12 = −12 %)
    unit: str                       # 'money' | 'pct' | 'index'
    note: str = ""


def _van_main_grid(p: Project, wacc: float, driver: str, grid: np.ndarray) -> np.ndarray:
    kw = dict(price_m=1.0, vol_m=1.0, vc_m=1.0, fix_m=1.0, capex_m=1.0)
    w = wacc
    if driver == "wacc":
        w = np.maximum(wacc + grid, 0.01)
        kw["price_m"] = np.ones_like(grid)          # fuerza S = len(grid)
    else:
        kw[{"price": "price_m", "volume": "vol_m", "unit_vc": "vc_m", "fixed": "fix_m", "capex": "capex_m"}[driver]] = grid
    fl = project_flows(p, **kw)
    return valuate(fl, w, p).van_main


def _root(grid: np.ndarray, f: np.ndarray, anchor: float) -> Optional[float]:
    """Raíz más cercana a `anchor` (interpolación lineal) de f sobre la grilla."""
    idx = np.where(np.sign(f[:-1]) * np.sign(f[1:]) <= 0)[0]
    best = None
    for i in idx:
        x0, x1, f0, f1 = grid[i], grid[i + 1], f[i], f[i + 1]
        x = x0 if f1 == f0 else x0 - f0 * (x1 - x0) / (f1 - f0)
        if best is None or abs(x - anchor) < abs(best - anchor):
            best = x
    return best


def breakeven(p: Project, wacc: float) -> List[BreakEven]:
    """Valor de cada driver que hace VAN = 0 (ceteris paribus), sobre el VAN del modo elegido."""
    out: List[BreakEven] = []
    base_money = dict(price=p.revenue_y1, unit_vc=p.var_cost_y1, fixed=p.fixed_cost_y1, capex=p.capex0)
    for d in DRIVERS:
        if d == "wacc":
            grid = np.linspace(-wacc + 0.011, 0.60, 1500)
            x = _root(grid, _van_main_grid(p, wacc, d, grid), 0.0)
            lim = None if x is None else wacc + x
            out.append(BreakEven(d, DRIVER_LABELS[d], wacc, lim, None if lim is None else lim / wacc - 1, "pct"))
            continue
        if p.fcf_direct is not None and d in ("price", "unit_vc", "fixed"):
            continue          # sin desglose no existen estos drivers
        grid = np.linspace(0.0, 10.0, 2001)
        x = _root(grid, _van_main_grid(p, wacc, d, grid), 1.0)
        if d == "volume":
            out.append(BreakEven(d, "FCF (nivel)" if p.fcf_direct is not None else DRIVER_LABELS[d],
                                 1.0, x, None if x is None else x - 1.0, "index"))
        else:
            b = base_money[d]
            out.append(BreakEven(d, DRIVER_LABELS[d], b, None if x is None else b * x,
                                 None if x is None else x - 1.0, "money"))
    return out


def critical_variable(bes: Sequence[BreakEven]) -> Optional[BreakEven]:
    """Driver cuyo cambio relativo para llevar el VAN a 0 es el MENOR (el más frágil)."""
    cand = [b for b in bes if b.rel_change is not None]
    return min(cand, key=lambda b: abs(b.rel_change)) if cand else None


# ═════════════════════════════════════════════════════════════════════════════
# 6) VALIDACIONES (C6) Y LECTURA DE RESULTADOS (C8)
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class Alert:
    code: str
    severity: str        # "alta" | "media" | "info"
    title: str
    detail: str


def run_validations(p: Project, wb: WaccBreakdown, m: Metrics, fl: Flows, mc: Optional[MCResult] = None,
                    pess_van: Optional[float] = None, val_g_clipped: bool = False) -> List[Alert]:
    T = THRESHOLDS
    A: List[Alert] = []
    if wb.ke_flow < wb.kd_pre and wb.wD > 0:
        A.append(Alert("V01", "alta", "Ke < Kd",
                       f"El costo del capital propio ({fmt_rate(wb.ke_flow)}) es menor que el de la deuda "
                       f"({fmt_rate(wb.kd_pre)}): el accionista no puede exigir menos que el banco. "
                       "Revisar inflaciones, moneda de la deuda y primas."))
    for label, irr in (("sin VT", m.irr_sin_vt), ("con VT", m.irr_con_vt)):
        if irr is not None and irr > T["irr_high"] and (label == "sin VT" or not m.con_vt_is_reference):
            A.append(Alert("V02", "alta", f"TIR {label} > 50 %",
                           f"TIR {label} = {fmt_rate(irr, 2)}. Rendimientos de este orden suelen indicar flujos "
                           "sobreestimados, inversión subestimada o perpetuidad sin reinversión."))
            break
    sig = (p.revenue_y1 <= 0) or (p.capex0 >= T["capex_significant_ratio"] * p.revenue_y1)
    if m.payback is not None and m.payback < T["payback_fast_years"] and sig:
        A.append(Alert("V03", "media", "Payback < 2 años con inversión significativa",
                       f"Payback simple = {fmt_years(m.payback)} años. Verificar que el CAPEX incluya todo "
                       "(capital de trabajo, reposición, puesta en marcha)."))
    if m.vt_weight == m.vt_weight and m.vt_weight > T["vt_weight"] and not (m.mode == "none"):
        A.append(Alert("V04", "alta", "El valor terminal explica más del 50 % del valor",
                       f"VT = {m.vt_weight * 100:.1f}% del valor presente. El resultado depende de lo que ocurra "
                       "después del horizonte explícito."))
    elif m.mode == "none" and m.vt_weight == m.vt_weight and m.vt_weight > T["vt_weight"]:
        A.append(Alert("V04", "info", "Si se activara la perpetuidad, el VT pesaría más del 50 %",
                       f"Peso referencial del VT = {m.vt_weight * 100:.1f}%. El VT está desactivado en la decisión."))
    if p.g_revenue > T["g_explicit_max"] and p.n_years > T["g_explicit_years"]:
        A.append(Alert("V05", "media", "Crecimiento explícito > 10 % por más de 3 años",
                       f"g = {p.g_revenue * 100:.2f}% durante {p.n_years} años. Un crecimiento sostenido de ese "
                       "nivel requiere justificar capacidad, mercado y capital de trabajo."))
    ebit1 = p.ebit_reported if p.ebit_reported is not None else float(fl.ebit[0, 0])
    fcf1 = float(fl.fcf_ops[0, 0])
    if p.fcf_direct is None or p.ebit_reported is not None:
        if ebit1 > 0:
            r = fcf1 / ebit1
            if not (T["fcf_ebit_min"] <= r <= T["fcf_ebit_max"]):
                A.append(Alert("V06", "media", "EBIT y FCF incoherentes",
                               f"FCF₁/EBIT₁ = {r:.2f} (rango razonable {T['fcf_ebit_min']:.2f}–{T['fcf_ebit_max']:.2f}). "
                               "Conciliar impuestos, depreciación, CAPEX de reposición y capital de trabajo."))
        elif fcf1 > 0:
            A.append(Alert("V06", "media", "EBIT ≤ 0 pero FCF > 0",
                           f"EBIT₁ = {fmt_num(ebit1)} y FCF₁ = {fmt_num(fcf1)}: el flujo positivo no surge de la operación."))
    if wb.mismatch:
        A.append(Alert("V07", "alta", "Moneda de la tasa distinta a la del flujo",
                       f"La tasa está en {wb.rate_currency} y el flujo en {wb.flow_currency}. Convertir con el "
                       "diferencial de inflación o expresar el flujo en USD."))
    if p.terminal_mode == "perpetuity" and not p.vt_justified:
        A.append(Alert("V09", "alta", "Perpetuidad no habilitada",
                       "Se pidió valor terminal por perpetuidad sin justificar la continuidad del negocio: "
                       "la evaluación se hizo SIN valor terminal."))
    if m.mode == "perpetuity" and p.fcf_direct is None and p.maint_capex_pct < 1.0:
        A.append(Alert("V10", "media", "Reposición < depreciación en la perpetuidad",
                       "El motor normaliza el CAPEX terminal al máximo entre reposición y depreciación, pero la "
                       "reposición explícita (<100 %) sobrestima los flujos de los años 1..N."))
    if val_g_clipped:
        A.append(Alert("V12", "media", "g∞ acotado",
                       f"g∞ se limitó a WACC − {G_INF_MARGIN * 100:.0f} pp en parte de las simulaciones/escenarios."))
    if pess_van is not None and pess_van < 0:
        sev = "alta"
        low = mc is not None and mc.stats["prob_neg"] <= T["prob_neg_ok"]
        A.append(Alert("V11", sev, "El escenario pesimista determinístico tiene VAN negativo",
                       f"VAN pesimista = {fmt_num(pess_van)}"
                       + (f", aunque P(VAN<0) del Monte Carlo es solo {mc.stats['prob_neg'] * 100:.1f}%. "
                          "La simulación no cubre combinaciones adversas simultáneas." if low else ".")))
    # ── Criterios de presupuesto de capital / valoración (lineamientos CFA) ─────────────────────────
    if m.sign_changes > 1:
        A.append(Alert("V14", "media", "Flujos no convencionales: la TIR puede no ser única",
                       f"El flujo cambia de signo {m.sign_changes} veces. Con más de un cambio pueden existir varias TIR "
                       "o ninguna; en ese caso la regla del VAN prevalece sobre la TIR."))
    if wb.infl_flow > 0 and p.g_revenue < wb.infl_flow - 0.005:
        A.append(Alert("V15", "media", "Ingresos crecen menos que la inflación: ¿flujos reales con tasa nominal?",
                       f"g = {p.g_revenue * 100:.2f}% < π = {wb.infl_flow * 100:.2f}%. La tasa de descuento es nominal; "
                       "los flujos deben estar en términos nominales (misma base de inflación) o la tasa debe ser real."))
    if m.mode == "perpetuity" and wb.infl_flow > 0 and p.g_inf > wb.infl_flow + 0.02:
        A.append(Alert("V16", "media", "g∞ supera la inflación + 2 pp",
                       f"g∞ = {p.g_inf * 100:.2f}% frente a π = {wb.infl_flow * 100:.2f}%. En perpetuidad el crecimiento no "
                       "debería superar el crecimiento nominal de largo plazo de la economía."))
    if wb.wD > 0 and wb.rf == wb.rf:
        rf_flow = (1 + wb.rf) * (1 + wb.infl_flow) / (1 + wb.infl_usd) - 1
        if wb.kd_pre < rf_flow:
            A.append(Alert("V17", "media", "Kd por debajo de la tasa libre de riesgo",
                           f"Kd = {fmt_rate(wb.kd_pre)} < Rf en la moneda del flujo ({fmt_rate(rf_flow)}). El costo de la deuda "
                           "debe ser el rendimiento de mercado actual para esa deuda (no la tasa cupón histórica)."))
    if (fl.fcf_ops[0] < 0).any():
        yrs = ", ".join(str(int(y)) for y, v in zip(fl.years, fl.fcf_ops[0]) if v < 0)
        A.append(Alert("V13", "info", "FCF negativo en algún año", f"Años con FCF < 0: {yrs}."))
    return A


def compare_scenarios(rows: Sequence[dict]) -> List[Alert]:
    """V08 + C7: alertas al comparar escenarios guardados (cada fila: name, n_years, wacc, wacc_key)."""
    A: List[Alert] = []
    if len({r["n_years"] for r in rows}) > 1:
        A.append(Alert("V08", "alta", "Horizontes distintos entre escenarios comparados",
                       "Los VAN no son comparables directamente (proyectos mutuamente excluyentes con vidas distintas): comparar el "
                       "valor anual equivalente (EAA) o igualar horizontes con cadena de reemplazo."))
    keys: Dict[tuple, set] = {}
    for r in rows:
        keys.setdefault(r.get("wacc_key"), set()).add(round(r["wacc"], 10))
    for k, v in keys.items():
        if len(v) > 1:
            A.append(Alert("C7", "media", "El WACC cambió sin cambio en sus inputs",
                           "Dos escenarios con los mismos inputs de tasa muestran WACC distinto."))
    return A


@dataclass
class Reading:
    """Reemplaza el 'DICTAMEN: APROBADO' (C8)."""
    status: str            # favorable | mixto | desfavorable
    headline: str
    detail: str


def read_results(m: Metrics, mc: Optional[MCResult], alerts: Sequence[Alert],
                 crit: Optional[BreakEven]) -> Reading:
    prob = mc.stats["prob_neg"] if mc is not None else float("nan")
    irr_ok = m.irr_sin_vt is not None and m.irr_sin_vt > m.wacc
    prob_ok = (prob != prob) or prob <= THRESHOLDS["prob_neg_ok"]
    if m.van_main > 0 and irr_ok and prob_ok:
        status, head = "favorable", "Indicadores favorables bajo los supuestos cargados"
    elif m.van_main > 0:
        status, head = "mixto", "Indicadores mixtos bajo los supuestos cargados"
    else:
        status, head = "desfavorable", "Indicadores desfavorables bajo los supuestos cargados"
    n_high = sum(a.severity == "alta" for a in alerts)
    det = f"{len(alerts)} alerta(s) activa(s), {n_high} de severidad alta." if alerts else "Sin alertas activas."
    return Reading(status, head, det)


# ═════════════════════════════════════════════════════════════════════════════
# 7) EVALUACIÓN COMPLETA
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class Evaluation:
    project: Project
    wacc: WaccBreakdown
    flows: Flows
    valuation: Valuation
    metrics: Metrics
    mc: Optional[MCResult]
    pess_van_main: float
    pess_van_sin_vt: float
    pess_mult: dict
    breakevens: List[BreakEven]
    critical: Optional[BreakEven]
    alerts: List[Alert]
    reading: Reading

    def row(self, name: str = "") -> dict:
        """Fila resumida para comparar escenarios (ver compare_scenarios)."""
        return dict(name=name or self.project.name, n_years=self.project.n_years, wacc=self.metrics.wacc,
                    van=self.metrics.van_main, eaa=self.metrics.eaa)


def evaluate(p: Project, w, mc: Optional[MCSpec] = None, pess_mult: Optional[dict] = None) -> Evaluation:
    """Evaluación corregida. `w` puede ser WaccInputs o un WaccBreakdown ya armado."""
    wb = w if isinstance(w, WaccBreakdown) else wacc_breakdown(w)
    fl = project_flows(p)
    val = valuate(fl, wb.wacc, p)
    met = _metrics(fl, val, wb.wacc, p)
    spec = mc or None
    res = run_monte_carlo(p, wb.wacc, spec, met.van_main) if spec else None
    pm = pess_mult or (spec.pessimistic() if spec else {})
    if pm:
        flp = project_flows(p, pm["price"], pm["volume"], pm["unit_vc"], pm["fixed"], pm["capex"])
        vp = valuate(flp, wb.wacc + pm["wacc"], p)
        pess_main, pess_sin = float(vp.van_main[0]), float(vp.van_sin_vt[0])
    else:
        pess_main = pess_sin = float("nan")
    bes = breakeven(p, wb.wacc)
    crit = critical_variable(bes)
    clipped = bool(val.g_eff[0] < p.g_inf - 1e-12) and val.mode == "perpetuity"
    alerts = run_validations(p, wb, met, fl, res, pess_main if pess_main == pess_main else None, clipped)
    return Evaluation(project=p, wacc=wb, flows=fl, valuation=val, metrics=met, mc=res,
                      pess_van_main=pess_main, pess_van_sin_vt=pess_sin, pess_mult=pm, breakevens=bes,
                      critical=crit, alerts=alerts, reading=read_results(met, res, alerts, crit))

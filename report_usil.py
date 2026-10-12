# report_usil.py — v3.0
# One-pager ejecutivo (TXT + PDF ReportLab) construido desde una `valuation_engine.Evaluation`.

from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass
from typing import Optional

import valuation_engine as ve

REPORTLAB_OK = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics as _pdfmetrics
    from reportlab.pdfgen import canvas
except Exception:
    REPORTLAB_OK = False

MODE_LABEL = {"none": "sin valor terminal", "salvage": "con valor de desecho", "perpetuity": "con perpetuidad"}

# Divulgación de supuestos y limitaciones (distinguir hecho de opinión, no garantizar resultados).
DISCLOSURE = [
    "Los resultados son estimaciones que dependen de los supuestos cargados; no son una recomendación de inversión ni una garantía.",
    "Hechos: los indicadores (VAN, TIR, WACC) son cálculos. Opiniones: la lectura y las alertas son juicios del modelo según umbrales fijos.",
    "Flujos al proyecto (FCFF) descontados al WACC con estructura de capital objetivo; costos hundidos y financieros excluidos del flujo.",
    "No valora opciones reales (expansión, abandono); el IRE no arrastra pérdidas; el riesgo país entra como prima en el Ke.",
    "El Monte Carlo refleja solo las distribuciones y correlaciones elegidas por el usuario.",
]


# ─── Formateadores ────────────────────────────────────────────────────────────
def fmt_pct(x: Optional[float], nd: int = 2) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x * 100:.{nd}f}%"


def _fmt_cur(x: Optional[float], currency: str) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    v = float(x)
    if currency == "PYG":
        return "Gs. {:,.0f}".format(v).replace(",", ".")
    if currency == "USD":
        return f"$ {v:,.2f}"
    return f"{currency} {v:,.2f}"


def _fmt_cur_short(x: Optional[float], currency: str) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    v = float(x)
    if currency == "PYG":
        return _fmt_cur(v, currency)
    sign = "-" if v < 0 else ""
    av = abs(v)
    sym = "$" if currency == "USD" else currency
    if av >= 1_000_000:
        return f"{sign}{sym} {av / 1_000_000:.2f}M"
    if av >= 1_000:
        return f"{sign}{sym} {av / 1_000:.1f}K"
    return _fmt_cur(v, currency)


def wrap(s: str, width: int) -> list[str]:
    return textwrap.wrap(s, width=width, break_long_words=False, replace_whitespace=False)


def describe_break(be: Optional[ve.BreakEven], cur: str) -> str:
    """Variable crítica con su valor límite (valor que hace VAN = 0)."""
    if be is None:
        return "No se encontró un valor límite dentro del rango explorado."
    if be.limit_value is None or be.rel_change is None:
        return f"{be.label}: sin valor límite en el rango explorado."
    chg = f"{be.rel_change * 100:+.1f}%"
    if be.unit == "money":
        return f"{be.label}: VAN = 0 con {_fmt_cur(be.limit_value, cur)} ({chg} vs. base {_fmt_cur(be.base_value, cur)})."
    if be.unit == "pct":
        return f"{be.label}: VAN = 0 con {fmt_pct(be.limit_value, 2)} ({chg} vs. base {fmt_pct(be.base_value, 2)})."
    return f"{be.label}: VAN = 0 con {be.limit_value * 100:.1f}% del nivel base ({chg})."


# ─── Ajuste de texto a un ancho máximo ─────────────────────────────────────────
def _fit_font(s: str, max_w: float, base: float, min_size: float = 6.0, bold: bool = False) -> float:
    if not s:
        return base
    font = "Helvetica-Bold" if bold else "Helvetica"
    size = base
    while size > min_size and _pdfmetrics.stringWidth(s, font, size) > max_w:
        size -= 0.3
    return round(max(size, min_size), 1)


def _truncate_ellipsis(s: str, max_w: float, size: float, bold: bool = False) -> str:
    font = "Helvetica-Bold" if bold else "Helvetica"
    if _pdfmetrics.stringWidth(s, font, size) <= max_w:
        return s
    ell = "…"
    lo, hi = 0, len(s)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _pdfmetrics.stringWidth(s[:mid] + ell, font, size) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (s[:lo].rstrip() + ell) if lo > 0 else ell


# ─── Modelo ───────────────────────────────────────────────────────────────────
@dataclass
class OnePager:
    ev: ve.Evaluation
    currency: str
    institution: str
    program: str
    course: str
    project: str
    responsible: str
    programa: str
    integrantes: str
    report_date: str
    compat_banner: str = ""        # texto si se exporta en modo compatibilidad


def _alerts_sorted(ev: ve.Evaluation):
    order = {"alta": 0, "media": 1, "info": 2}
    return sorted(ev.alerts, key=lambda a: (order.get(a.severity, 3), a.code))


# ─── TXT ──────────────────────────────────────────────────────────────────────
def build_onepager_text(r: OnePager) -> str:
    ev, C = r.ev, r.currency
    m, wb, p = ev.metrics, ev.wacc, ev.project

    def fc(x): return _fmt_cur(x, C)

    L = [
        "ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA",
        r.institution,
        f"Programa: {r.programa}  |  {r.course}",
        f"Moneda del flujo: {C}  |  Fecha: {r.report_date}",
        f"Proyecto: {r.project}  |  Responsable: {r.responsible}",
        *([f"Integrantes: {r.integrantes}"] if r.integrantes.strip() else []),
        "",
    ]
    if r.compat_banner:
        L += [f"*** {r.compat_banner} ***", ""]
    L += [
        ev.reading.headline,
        ev.reading.detail,
        "Variable crítica: " + describe_break(ev.critical, C),
        "",
        f"INDICADORES PRINCIPALES  (decisión: {MODE_LABEL.get(m.mode, m.mode)})",
        f"- VAN (indicador de decisión): {fc(m.van_main)}",
        f"- VAN sin VT: {fc(m.van_sin_vt)}",
        f"- VAN con VT{' (REFERENCIAL: el VT está desactivado en la decisión)' if m.con_vt_is_reference else ''}: {fc(m.van_con_vt)}",
        f"- Peso del VT en el valor: {fmt_pct(m.vt_weight, 1)}",
        f"- TIR sin VT (principal): {fmt_pct(m.irr_sin_vt)}  |  TIR con VT (secundaria): {fmt_pct(m.irr_con_vt)}",
        f"- TIR modificada (sin VT): {fmt_pct(m.mirr_sin_vt)}  |  Índice de rentabilidad (sin VT): {m.ir_sin_vt:.2f}",
        f"- Payback simple: {ve.fmt_years(m.payback)} años  |  descontado: {ve.fmt_years(m.payback_disc)} años  (indicadores secundarios)",
        f"- Valor anual equivalente (EAA): {fc(m.eaa)}",
        "",
        f"TASA DE DESCUENTO EN {wb.rate_currency.upper()}",
        f"- Rf (USD) {fmt_pct(wb.rf, 4)} | β desapalancada {wb.beta_u:.3f} → apalancada {wb.beta_l:.3f} | ERP {fmt_pct(wb.erp, 4)} | CRP {fmt_pct(wb.crp, 4)} | prima tamaño {fmt_pct(wb.size_premium, 4)}"
        if wb.rf == wb.rf else "- (Tasa reconstruida desde valores reportados; sin desglose CAPM)",
        f"- Ke en USD {fmt_pct(wb.ke_usd, 4)} | π {C} {fmt_pct(wb.infl_flow, 2)} | π USD {fmt_pct(wb.infl_usd, 2)} → Ke en {wb.flow_currency} {fmt_pct(wb.ke_flow, 4)}",
        f"- Kd antes de IRE {fmt_pct(wb.kd_pre, 4)} | después de IRE ({fmt_pct(wb.tax, 1)}) {fmt_pct(wb.kd_post, 4)}",
        f"- Pesos: E/V {fmt_pct(wb.wE, 2)} | D/V {fmt_pct(wb.wD, 2)}",
        f"- WACC: {fmt_pct(wb.wacc, 4)}",
        "",
        "SUPUESTOS CLAVE",
        f"- Horizonte {p.n_years} años | g ventas {fmt_pct(p.g_revenue)} | g∞ {fmt_pct(p.g_inf)} | IRE {fmt_pct(p.tax, 1)}",
        f"- CAPEX inicial {fc(p.capex0)} | valor terminal: {MODE_LABEL.get(p.effective_mode(), p.terminal_mode)}"
        + (f" | justificación: {p.vt_justification}" if p.effective_mode() == "perpetuity" and p.vt_justification else ""),
        "",
        "FLUJO DE CAJA LIBRE (FCF) POR AÑO",
    ]
    for i, f in enumerate(ev.flows.fcf_ops[0], 1):
        L.append(f"- Año {i}: {fc(f)}")
    L += [f"- VT (año {p.n_years}): {fc(m.vt) if p.effective_mode() == 'perpetuity' or m.con_vt_is_reference else '—'}", ""]
    L.append("ESCENARIO PESIMISTA DETERMINÍSTICO (extremos adversos de todos los drivers a la vez)")
    if ev.pess_mult:
        pm = ev.pess_mult
        L.append("- Precio ×{price:.2f} | volumen ×{volume:.2f} | costo variable ×{unit_vc:.2f} | costos fijos ×{fixed:.2f} | CAPEX ×{capex:.2f} | WACC +{wacc_pp:.2f} pp".format(
            wacc_pp=pm["wacc"] * 100, **{k: v for k, v in pm.items() if k != "wacc"}))
        L.append(f"- VAN pesimista: {fc(ev.pess_van_main)}  (sin VT: {fc(ev.pess_van_sin_vt)})")
    L.append("")
    if ev.mc is not None:
        s = ev.mc.stats
        L += ["RIESGO — MONTE CARLO (sobre drivers operativos)",
              f"- Simulaciones: {s['n']:,} | distribución: {ev.mc.spec.dist} | P(VAN<0): {fmt_pct(s['prob_neg'], 1)}",
              f"- P5 / P50 / P95: {fc(s['p5'])} / {fc(s['p50'])} / {fc(s['p95'])}",
              f"- Media {fc(s['mean'])} | σ {fc(s['std'])} | CVaR5 {fc(s['cvar5'])}",
              f"- El caso base está en el percentil {fmt_pct(s['base_percentile'], 1)} de la distribución", ""]
    L.append("ALERTAS ACTIVAS")
    if ev.alerts:
        for a in _alerts_sorted(ev):
            L.append(f"- [{a.severity.upper()}] {a.code} · {a.title}: {a.detail}")
    else:
        L.append("- Sin alertas activas.")
    L += ["", "SUPUESTOS Y LIMITACIONES", *[f"- {d}" for d in DISCLOSURE]]
    return "\n".join(L)


# ─── PDF ──────────────────────────────────────────────────────────────────────
def generate_onepager_pdf(r: OnePager, hist_counts=None, hist_edges=None) -> bytes:
    if not REPORTLAB_OK:
        raise RuntimeError("ReportLab no disponible.")
    ev, C = r.ev, r.currency
    m, wb, p = ev.metrics, ev.wacc, ev.project

    def fc(x): return _fmt_cur(x, C)
    def fcs(x): return _fmt_cur_short(x, C)

    buf = io.BytesIO()
    cv = canvas.Canvas(buf, pagesize=letter)
    W, H = letter

    bg = colors.HexColor("#050914"); card = colors.HexColor("#0b1733"); card2 = colors.HexColor("#0d1b3d")
    linec = colors.Color(1, 1, 1, alpha=0.09); text = colors.HexColor("#EAF1FF")
    muted = colors.Color(234 / 255, 241 / 255, 1, alpha=0.65); accent = colors.HexColor("#66A9FF")
    good = colors.HexColor("#27D17C"); warn_c = colors.HexColor("#FFCC66"); bad = colors.HexColor("#FF5D5D")

    def rr(x, y, w, h, rad=8, fill=card):
        cv.setFillColor(fill); cv.setStrokeColor(linec); cv.setLineWidth(0.6)
        cv.roundRect(x, y, w, h, rad, stroke=1, fill=1)

    def tx(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col); cv.setFont("Helvetica-Bold" if bold else "Helvetica", size); cv.drawString(x, y, str(s))

    def txr(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col); cv.setFont("Helvetica-Bold" if bold else "Helvetica", size); cv.drawRightString(x, y, str(s))

    def txc(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col); cv.setFont("Helvetica-Bold" if bold else "Helvetica", size); cv.drawCentredString(x, y, str(s))

    def hdiv(x1, y, x2):
        cv.setStrokeColor(linec); cv.setLineWidth(0.4); cv.setDash(); cv.line(x1, y, x2, y)

    def sec(x, y, label, size=7.6):
        cv.setFillColor(accent); cv.rect(x, y - 1, 3, size + 2, stroke=0, fill=1)
        tx(x + 6, y, label, size=size, bold=True, col=accent)

    def tx_fit(x, y, s, max_w, size=8.5, min_size=5.6, bold=False, col=text):
        f = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        tx(x, y, _truncate_ellipsis(s, max_w, f, bold=bold), size=f, bold=bold, col=col)

    def txr_fit(x, y, s, max_w, size=8.5, min_size=5.6, bold=False, col=text):
        f = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        txr(x, y, _truncate_ellipsis(s, max_w, f, bold=bold), size=f, bold=bold, col=col)

    def txc_fit(x, y, s, max_w, size=8.5, min_size=6.0, bold=False, col=text):
        f = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        txc(x, y, _truncate_ellipsis(s, max_w, f, bold=bold), size=f, bold=bold, col=col)

    def kv(xl, xr, y, label, value, size=7.0, col=text, bold=False):
        tx(xl, y, label, size=size, col=muted)
        txr_fit(xr, y, value, (xr - xl) * 0.62, size=size, bold=bold, col=col)

    def para(x, y, s, w, size=7.0, leading=9.2, col=muted, max_lines=None, min_y=None):
        lines = wrap(s, w)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]; lines[-1] = lines[-1].rstrip() + " …"
        for ln in lines:
            if min_y is not None and y < min_y:
                break
            tx(x, y, ln, size=size, col=col); y -= leading
        return y

    cv.setFillColor(bg); cv.rect(0, 0, W, H, stroke=0, fill=1)
    mg = int(0.375 * inch); top = H - mg; left = mg; right = W - mg; cw = right - left; GAP = 6

    status_col = {"favorable": good, "mixto": warn_c, "desfavorable": bad}.get(ev.reading.status, accent)

    # ═ 1. HEADER ═
    h1 = 78
    rr(left, top - h1, cw, h1, 10, card2)
    cv.setFillColor(accent); cv.roundRect(left, top - h1, 5, h1, 3, stroke=0, fill=1)
    il, ir_ = left + 14, right - 14
    tx(il, top - 15, f"ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA  ({C})", size=10.5, bold=True)
    txr(ir_, top - 15, f"Fecha: {r.report_date}", size=7.4, col=muted)
    hdiv(il, top - 21, ir_)
    y0 = top - 33
    tx_fit(il, y0, r.institution, ir_ - il, size=7.4, col=muted); y0 -= 11
    tx_fit(il, y0, r.programa, ir_ - il, size=8.6, bold=True, col=accent); y0 -= 11
    tx_fit(il, y0, f"Proyecto: {r.project}   ·   Responsable: {r.responsible}", ir_ - il, size=7.4); y0 -= 10.5
    if r.integrantes.strip():
        integs = " · ".join(x.strip() for x in r.integrantes.strip().replace("\n", ",").split(",") if x.strip())
        tx_fit(il, y0, f"Integrantes: {integs}", ir_ - il, size=7.0, col=muted)
    y = top - h1 - GAP

    # ═ 2. LECTURA (reemplaza el "dictamen") ═
    h2 = 40
    rr(left, y - h2, cw, h2, 8, card)
    cv.setFillColor(status_col); cv.roundRect(left, y - h2, 4, h2, 2, stroke=0, fill=1)
    tx_fit(left + 12, y - 13, ev.reading.headline, cw - 24, size=9.6, bold=True, col=status_col)
    crit_txt = "Variable crítica — " + describe_break(ev.critical, C)
    tx_fit(left + 12, y - 25, crit_txt, cw - 24, size=7.2, col=text)
    sub = ev.reading.detail + (f"  ·  {r.compat_banner}" if r.compat_banner else "")
    tx_fit(left + 12, y - 35, sub, cw - 24, size=6.6, col=bad if r.compat_banner else muted)
    y -= h2 + GAP

    # ═ 3. KPIs ═
    kh, kn, kg = 56, 4, 6
    kw = (cw - kg * (kn - 1)) / kn
    van_c = good if m.van_main > 0 else bad
    kpis = [
        (f"VAN — {MODE_LABEL.get(m.mode, m.mode)}", fcs(m.van_main), f"IR {m.ir_sin_vt:.2f} · TIRM {fmt_pct(m.mirr_sin_vt)}", van_c),
        ("VAN sin VT" if m.mode != "none" else "VAN con VT (referencial)",
         fcs(m.van_sin_vt if m.mode != "none" else m.van_con_vt),
         f"Peso del VT: {fmt_pct(m.vt_weight, 1)}", good if (m.van_sin_vt if m.mode != "none" else m.van_con_vt) > 0 else bad),
        ("TIR sin VT (principal)", fmt_pct(m.irr_sin_vt), f"con VT (secund.): {fmt_pct(m.irr_con_vt)} · WACC {fmt_pct(m.wacc, 2)}",
         good if (m.irr_sin_vt or 0) > m.wacc else bad),
        ("Payback simple / desc.", f"{ve.fmt_years(m.payback)} / {ve.fmt_years(m.payback_disc)} años",
         f"EAA {fcs(m.eaa)}", accent),
    ]
    kb = y - kh
    for i, (lbl, val, sub, vc) in enumerate(kpis):
        kx = left + i * (kw + kg)
        rr(kx, kb, kw, kh, 7, card)
        cv.setFillColor(vc); cv.roundRect(kx, kb + kh - 4, kw, 4, 2, stroke=0, fill=1)
        aw = kw - 16
        tx_fit(kx + 8, kb + kh - 15, lbl, aw, size=6.6, bold=True, col=muted)
        tx_fit(kx + 8, kb + 22, val, aw, size=12, min_size=7.5, bold=True, col=vc)
        tx_fit(kx + 8, kb + 8, sub, aw, size=5.9, min_size=5.0, col=muted)
    y = kb - GAP

    # ═ 4. WACC (izq) + VALOR Y FLUJOS (der) ═
    h3 = 168
    lw = cw * 0.50 - 3; rw = cw - lw - 6; rx = left + lw + 6
    b3 = y - h3
    rr(left, b3, lw, h3, 8); rr(rx, b3, rw, h3, 8)
    sec(left + 10, b3 + h3 - 14, f"TASA EN {wb.rate_currency.upper()} (WACC)")
    hdiv(left + 10, b3 + h3 - 19, left + lw - 10)
    yy = b3 + h3 - 30
    has_capm = wb.rf == wb.rf
    rows = []
    if has_capm:
        rows += [("Rf (USD)", fmt_pct(wb.rf, 4)), ("β desapalancada → apalancada", f"{wb.beta_u:.3f} → {wb.beta_l:.3f}"),
                 ("ERP", fmt_pct(wb.erp, 4)), ("CRP (riesgo país)", fmt_pct(wb.crp, 4)),
                 ("Prima por tamaño", fmt_pct(wb.size_premium, 4))]
    rows += [("Ke en USD", fmt_pct(wb.ke_usd, 4)), (f"π {wb.flow_currency} / π USD", f"{fmt_pct(wb.infl_flow, 2)} / {fmt_pct(wb.infl_usd, 2)}"),
             (f"Ke en {wb.flow_currency}", fmt_pct(wb.ke_flow, 4)),
             ("Kd antes / después de IRE", f"{fmt_pct(wb.kd_pre, 4)} / {fmt_pct(wb.kd_post, 4)}"),
             ("Pesos E/V · D/V", f"{fmt_pct(wb.wE, 2)} · {fmt_pct(wb.wD, 2)}")]
    for lab, val in rows:
        kv(left + 12, left + lw - 12, yy, lab, val, size=6.9); yy -= 10.2
    hdiv(left + 10, yy + 8, left + lw - 10)
    yy -= 3
    kv(left + 12, left + lw - 12, yy, "WACC (tasa usada)", fmt_pct(wb.wacc, 4), size=8, bold=True, col=accent)
    if wb.mismatch:
        tx_fit(left + 12, yy - 11, "(!) Tasa en USD sin convertir al flujo en " + wb.flow_currency, lw - 24, size=6.6, col=bad)

    sec(rx + 10, b3 + h3 - 14, "VALOR Y FLUJOS")
    hdiv(rx + 10, b3 + h3 - 19, rx + rw - 10)
    vy = b3 + h3 - 30
    term_lbl = {"none": "Recupero de capital de trabajo", "salvage": "Desecho neto + recupero CT", "perpetuity": "PV valor terminal (perpetuidad)"}[m.mode]
    pv_term = ve.pv_terminal(ev.valuation)
    for lab, val, bold, col in [("PV FCF explícitos (1..N)", fc(m.pv_ops), False, text),
                                (f"PV {term_lbl.split('PV ')[-1]}", fc(pv_term), False, text),
                                ("− CAPEX inicial", fc(-ev.flows.capex0[0]), False, text),
                                ("VAN (decisión)", fc(m.van_main), True, van_c)]:
        if bold:
            hdiv(rx + 10, vy + 8, rx + rw - 10); vy -= 3
        kv(rx + 12, rx + rw - 12, vy, lab, val, size=7.0 if not bold else 7.8, bold=bold, col=col); vy -= 10.5
    vy -= 4
    sec(rx + 10, vy, "FCF POR AÑO", size=7.0); vy -= 11
    fl = list(ev.flows.fcf_ops[0])
    for i, v in enumerate(fl, 1):
        if vy < b3 + 10:
            tx(rx + 12, vy + 9, f"(+{len(fl) - i + 1} año(s) más)", size=6.2, col=muted); break
        kv(rx + 12, rx + rw - 12, vy, f"Año {i}", fc(v), size=6.7, col=good if v >= 0 else bad); vy -= 8.6
    y = b3 - GAP

    # ═ 5. ALERTAS + PESIMISTA (izq) | MONTE CARLO (der) ═
    foot_h = 40
    b4 = mg + foot_h
    h4 = y - b4
    rr(left, b4, lw, h4, 8); rr(rx, b4, rw, h4, 8)
    sec(left + 10, b4 + h4 - 14, "ESCENARIO PESIMISTA Y ALERTAS ACTIVAS")
    hdiv(left + 10, b4 + h4 - 19, left + lw - 10)
    yy = b4 + h4 - 30
    pm = ev.pess_mult
    if pm:
        tx_fit(left + 12, yy, f"Precio ×{pm['price']:.2f} · Vol. ×{pm['volume']:.2f} · CV ×{pm['unit_vc']:.2f} · CF ×{pm['fixed']:.2f} · CAPEX ×{pm['capex']:.2f} · WACC +{pm['wacc'] * 100:.1f} pp",
               lw - 24, size=6.2, col=muted); yy -= 10
        kv(left + 12, left + lw - 12, yy, "VAN pesimista (decisión)", fc(ev.pess_van_main), size=7.0,
           col=good if ev.pess_van_main >= 0 else bad, bold=True); yy -= 12
    # Alertas y, a continuación, punto de equilibrio por variable
    bes = list(ev.breakevens)
    nb = len(bes)
    tbl_h = nb * 9.0 + 24
    sev_col = {"alta": bad, "media": warn_c, "info": muted}
    if ev.alerts:
        for a in _alerts_sorted(ev):
            if yy < b4 + 10 + tbl_h + 8:
                tx(left + 12, yy + 8, "(más alertas en el TXT)", size=6.0, col=muted); break
            tx_fit(left + 12, yy, f"[{a.severity.upper()}] {a.code} · {a.title}", lw - 24, size=6.6, col=sev_col.get(a.severity, muted)); yy -= 9
    else:
        tx(left + 12, yy, "Sin alertas activas.", size=7.0, col=good); yy -= 9
    tb_top = max(yy - 6, b4 + 10 + tbl_h)
    hdiv(left + 10, tb_top + 4, left + lw - 10)
    sec(left + 10, tb_top - 8, "PUNTO DE EQUILIBRIO (VAN = 0, ceteris paribus)", size=6.8)
    ty2 = tb_top - 19
    for x in bes:
        is_c = ev.critical is not None and x.driver == ev.critical.driver
        if x.limit_value is None:
            val = "sin valor en el rango"
        elif x.unit == "money":
            val = f"{fcs(x.limit_value)} ({x.rel_change * 100:+.1f}%)"
        elif x.unit == "pct":
            val = f"{fmt_pct(x.limit_value, 2)} ({x.rel_change * 100:+.1f}%)"
        else:
            val = f"{x.limit_value * 100:.1f}% del nivel base ({x.rel_change * 100:+.1f}%)"
        kv(left + 12, left + lw - 12, ty2, x.label + ("  (crítica)" if is_c else ""), val, size=6.3,
           col=accent if is_c else text, bold=is_c)
        ty2 -= 9.0

    sec(rx + 10, b4 + h4 - 14, "RIESGO — MONTE CARLO")
    hdiv(rx + 10, b4 + h4 - 19, rx + rw - 10)
    ml, mr = rx + 10, rx + rw - 10
    my = b4 + h4 - 30
    if ev.mc is not None:
        s = ev.mc.stats
        for lab, val, col in [("Simulaciones", f"{s['n']:,}".replace(",", "."), muted),
                              ("P(VAN<0)", fmt_pct(s["prob_neg"], 1), good if s["prob_neg"] <= 0.2 else bad),
                              ("P5 · P50 · P95", f"{fcs(s['p5'])} · {fcs(s['p50'])} · {fcs(s['p95'])}", muted),
                              ("CVaR5 · σ", f"{fcs(s['cvar5'])} · {fcs(s['std'])}", bad),
                              ("Caso base en percentil", fmt_pct(s["base_percentile"], 1), muted)]:
            kv(ml, mr, my, lab, val, size=6.8, col=col); my -= 9.6
        hx, hy, hw = rx + 12, b4 + 10, rw - 24
        hh = max(my - hy - 4, 20)
        cv.setFillColor(colors.Color(1, 1, 1, alpha=0.04)); cv.roundRect(hx, hy, hw, hh, 4, stroke=0, fill=1)
        if hist_counts is not None and hist_edges is not None and len(hist_counts) > 0:
            maxc = max(hist_counts) or 1
            nb = len(hist_counts); bw = hw / nb
            lo, hi = float(hist_edges[0]), float(hist_edges[-1])
            for i, cnt in enumerate(hist_counts):
                mid = (hist_edges[i] + hist_edges[i + 1]) / 2
                ch = bad if mid < 0 else accent
                cv.setFillColor(colors.Color(ch.red, ch.green, ch.blue, alpha=0.65))
                cv.rect(hx + i * bw, hy, bw * 0.9, (cnt / maxc) * hh, stroke=0, fill=1)

            def x_at(v): return hx + (float(v) - lo) / (hi - lo) * hw if hi > lo else hx
            if lo < 0 < hi:
                cv.setStrokeColor(colors.Color(bad.red, bad.green, bad.blue, alpha=0.85)); cv.setLineWidth(1.2); cv.setDash()
                cv.line(x_at(0), hy, x_at(0), hy + hh)
            for v in (s["p5"], s["p50"], s["p95"]):
                if math.isfinite(v):
                    cv.setStrokeColor(colors.Color(1, 1, 1, alpha=0.38)); cv.setLineWidth(0.8); cv.setDash(3, 3)
                    cv.line(x_at(v), hy, x_at(v), hy + hh); cv.setDash()
            if math.isfinite(m.van_main) and lo < m.van_main < hi:
                cv.setStrokeColor(colors.Color(good.red, good.green, good.blue, alpha=0.9)); cv.setLineWidth(1.0); cv.setDash(1, 2)
                cv.line(x_at(m.van_main), hy, x_at(m.van_main), hy + hh); cv.setDash()
    else:
        tx(ml, my, "Monte Carlo no ejecutado.", size=7.0, col=muted)

    # ═ FOOTER: supuestos y limitaciones ═
    fy = mg + foot_h - 6
    hdiv(left, fy + 3, right)
    ty = fy - 6
    for d in DISCLOSURE[:3] + [DISCLOSURE[3] + " " + DISCLOSURE[4]]:
        tx_fit(left, ty, "• " + d, cw, size=5.9, min_size=4.9, col=muted); ty -= 7.3
    cv.setFillColor(muted); cv.setFont("Helvetica", 5.8)
    cv.drawRightString(right, mg - 4, f"ValuationSuite USIL v{ve.ENGINE_VERSION}  ·  {C}  ·  {r.report_date}")
    cv.showPage(); cv.save()
    return buf.getvalue()

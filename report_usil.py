# report_usil.py — v2.0
# Exporter TXT + PDF (ReportLab) — sin matplotlib

from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

REPORTLAB_OK = True
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
except Exception:
    REPORTLAB_OK = False

# ─── Formateadores ────────────────────────────────────────────────────────────
def fmt_pct(x: Optional[float]) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return f"{x*100:.2f}%"

def fmt_pyg(x: Optional[float]) -> str:
    if x is None or not math.isfinite(x):
        return "—"
    return "Gs. {:,.0f}".format(float(x)).replace(",", ".")

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
    sign = "-" if v < 0 else ""
    av = abs(v)
    if currency == "PYG":
        if av >= 1_000_000_000:
            return f"{sign}Gs. {av/1_000_000_000:,.2f} B".replace(",", ".")
        if av >= 1_000_000:
            return f"{sign}Gs. {av/1_000_000:,.1f} MM".replace(",", ".")
        return _fmt_cur(v, currency)
    else:
        sym = "$" if currency == "USD" else currency
        if av >= 1_000_000:
            return f"{sign}{sym} {av/1_000_000:.2f}M"
        if av >= 1_000:
            return f"{sign}{sym} {av/1_000:.1f}K"
        return _fmt_cur(v, currency)

def wrap(s: str, width: int) -> list[str]:
    return textwrap.wrap(s, width=width, break_long_words=False, replace_whitespace=False)

def badge(verdict: str) -> str:
    return {"APROBADO": "✅", "OBSERVADO": "⚠️", "RECHAZADO": "⛔"}.get(verdict, "—")

# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class OnePager:
    institution: str
    program: str
    course: str
    currency: str
    project: str
    responsible: str
    report_date: str
    verdict: str
    rationale: str
    npv_base: Optional[float]
    irr_base: Optional[float]
    payback_simple: Optional[float]
    payback_discounted: Optional[float]
    n_years: int
    g_exp: float
    g_inf: float
    wacc: float
    ke: float
    kd: float
    capex0: float
    fcf1: float
    ebit: float
    nopat: float
    delta_wc: float
    capex_y1: float
    pv_fcf: Optional[float]
    pv_tv: Optional[float]
    tv: Optional[float]
    sims: int
    valid_rate: Optional[float]
    prob_neg: Optional[float]
    p5: Optional[float]
    p50: Optional[float]
    p95: Optional[float]
    mean: Optional[float]
    std: Optional[float]
    cvar5: Optional[float]
    checks: Sequence[Tuple[str, bool]]
    fcf_years: Sequence[float]

# ─── TXT export ───────────────────────────────────────────────────────────────
def build_onepager_text(r: OnePager) -> str:
    C = r.currency

    def fc(x):  return _fmt_cur(x, C)
    def fp(x):  return fmt_pct(x)

    pb  = "N/A" if r.payback_simple is None else f"{r.payback_simple:.2f} años"
    pbd = "N/A" if r.payback_discounted is None else f"{r.payback_discounted:.2f} años"
    prob = "—"  if r.prob_neg is None else f"{r.prob_neg*100:.1f}%"

    lines = [
        "ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA",
        f"{r.institution} — {r.program} — {r.course}",
        f"Moneda: {C}  |  Fecha: {r.report_date}",
        f"Proyecto: {r.project}  |  Responsable: {r.responsible}",
        "",
        f"DICTAMEN: {r.verdict} {badge(r.verdict)}",
        r.rationale,
        "",
        "KPIs (determinístico)",
        f"- VAN (base): {fc(r.npv_base)}",
        f"- TIR (base): {fp(r.irr_base)}",
        f"- Payback: {pb}  |  Payback descontado: {pbd}",
        "",
        "Supuestos clave",
        f"- Horizonte: {r.n_years} años + perpetuidad",
        f"- g explícito: {fp(r.g_exp)}  |  g∞: {fp(r.g_inf)}",
        f"- WACC: {fp(r.wacc)}  (Ke {fp(r.ke)} | Kd {fp(r.kd)})",
        f"- CAPEX₀: {fc(r.capex0)}  |  FCF₁: {fc(r.fcf1)}",
        "",
        "Flujos proyectados (FCF) — ciclo 1..N",
    ]
    for i, f in enumerate(r.fcf_years, 1):
        lines.append(f"- Año {i}: {fc(f)}")
    lines += [
        f"- TV (año {r.n_years}): {fc(r.tv)}",
        "",
        "Puente contable → FCF₁",
        f"- EBIT: {fc(r.ebit)}  |  NOPAT: {fc(r.nopat)}",
        f"- Depreciación: {fc(r.capex_y1)}  |  ΔCT (AR+INV-AP): {fc(r.delta_wc)}",
        "",
        "Riesgo (Monte Carlo)",
        f"- Simulaciones: {r.sims:,}  |  válidas: {'—' if r.valid_rate is None else f'{r.valid_rate*100:.1f}%'}",
        f"- P(VAN<0): {prob}",
        f"- P5/P50/P95: {fc(r.p5)} / {fc(r.p50)} / {fc(r.p95)}",
        f"- Media: {fc(r.mean)}  |  σ: {fc(r.std)}  |  CVaR5: {fc(r.cvar5)}",
        "",
        "Checklist Comité",
    ]
    for label, ok in r.checks:
        lines.append(("✅ " if ok else "❌ ") + label)
    lines += ["", "Uso académico (MBA). No sustituye due diligence."]
    return "\n".join(lines)

# ─── PDF premium (ReportLab) ─────────────────────────────────────────────────
def generate_onepager_pdf(
    onepager: OnePager,
    hist_counts=None,
    hist_edges=None,
) -> bytes:
    if not REPORTLAB_OK:
        raise RuntimeError("ReportLab no disponible.")

    C = onepager.currency

    def fc(x):  return _fmt_cur(x, C)
    def fcs(x): return _fmt_cur_short(x, C)
    def fp(x):  return fmt_pct(x)

    buf = io.BytesIO()
    cv  = canvas.Canvas(buf, pagesize=letter)
    W, H = letter   # 612 × 792 pt

    # Paleta
    bg     = colors.HexColor("#050914")
    card   = colors.HexColor("#0b1733")
    card2  = colors.HexColor("#0d1b3d")
    linec  = colors.Color(1, 1, 1, alpha=0.09)
    text   = colors.HexColor("#EAF1FF")
    muted  = colors.Color(234/255, 241/255, 1, alpha=0.70)
    accent = colors.HexColor("#66A9FF")
    good   = colors.HexColor("#27D17C")
    warn_c = colors.HexColor("#FFCC66")
    bad    = colors.HexColor("#FF5D5D")

    # helpers
    def rr(x, y, w, h, r=10, fill=card):
        cv.setFillColor(fill)
        cv.setStrokeColor(linec)
        cv.setLineWidth(0.7)
        cv.roundRect(x, y, w, h, r, stroke=1, fill=1)

    def tx(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawString(x, y, str(s))

    def txr(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawRightString(x, y, str(s))

    def para(x, y, s, w=80, size=8, leading=10.5, col=muted):
        yy = y
        for ln in wrap(s, w):
            tx(x, yy, ln, size=size, col=col)
            yy -= leading
        return yy

    # Fondo
    cv.setFillColor(bg)
    cv.rect(0, 0, W, H, stroke=0, fill=1)

    mg    = 0.40 * inch
    top   = H - mg
    left  = mg
    right = W - mg
    cw    = right - left   # ≈ 530 pt

    # ══ BLOQUE 1: HEADER (h=50) ═══════════════════════════════════════════════
    h1_h = 50
    rr(left, top - h1_h, cw, h1_h, r=12, fill=card2)
    tx(left+12, top-16,  f"ONE-PAGER EJECUTIVO — EVALUACIÓN FINANCIERA ({C})", size=10.5, bold=True)
    tx(left+12, top-28,  f"{onepager.institution} — {onepager.program} — {onepager.course}", size=7.8, col=muted)
    tx(left+12, top-39,  f"Proyecto: {onepager.project}   |   Responsable: {onepager.responsible}", size=7.8, col=muted)
    txr(right-12, top-28, f"Fecha: {onepager.report_date}", size=7.8, col=muted)

    pill_col = good if onepager.verdict == "APROBADO" else (bad if onepager.verdict == "RECHAZADO" else warn_c)
    cv.setFillColor(colors.Color(pill_col.red, pill_col.green, pill_col.blue, alpha=0.16))
    cv.setStrokeColor(linec)
    cv.roundRect(right-130, top-44, 116, 20, 10, stroke=1, fill=1)
    tx(right-121, top-38, f"DICTAMEN: {onepager.verdict}", size=9, bold=True, col=pill_col)

    y = top - h1_h - 5   # cursor

    # ══ BLOQUE 2: KPI ROW (h=42) ══════════════════════════════════════════════
    kpi_h = 42
    kpi_n = 6
    gap   = 5
    kpi_w = (cw - gap * (kpi_n - 1)) / kpi_n

    pb  = "N/A" if onepager.payback_simple is None else f"{onepager.payback_simple:.1f}a"
    pbd = "N/A" if onepager.payback_discounted is None else f"{onepager.payback_discounted:.1f}a"
    prob = "—"  if onepager.prob_neg is None else f"{onepager.prob_neg*100:.1f}%"

    kpis = [
        ("VAN (base)",      fcs(onepager.npv_base), "Determinístico"),
        ("TIR (base)",      fp(onepager.irr_base),  "Determinístico"),
        ("Payback",         pb,                      "Simple"),
        ("Payback (desc.)", pbd,                     "Descontado"),
        ("P(VAN<0)",        prob,                    "Monte Carlo"),
        ("P50 (VAN)",       fcs(onepager.p50),       "Monte Carlo"),
    ]
    kpi_y = y - kpi_h
    for i, (lbl, val, sub) in enumerate(kpis):
        kx = left + i * (kpi_w + gap)
        rr(kx, kpi_y, kpi_w, kpi_h, r=9, fill=card)
        tx(kx+7, kpi_y + kpi_h - 13, lbl, size=7.2, col=muted)
        tx(kx+7, kpi_y + 15,          val, size=9,   bold=True)
        tx(kx+7, kpi_y + 5,           sub, size=6.8,  col=muted)

    y = kpi_y - 6

    # ══ BLOQUE 3: DECISION (izq) + VALUE BRIDGE (der) (h=150) ════════════════
    mid_h = 150
    lw    = cw * 0.54 - 4
    rw    = cw * 0.46 - 4
    lx    = left
    rx    = left + lw + 8

    mid_y = y - mid_h
    rr(lx, mid_y, lw, mid_h, r=10, fill=card)
    rr(rx, mid_y, rw, mid_h, r=10, fill=card)

    # — Decisión —
    tx(lx+10, mid_y + mid_h - 14, "Decisión & supuestos", size=9, bold=True)
    yy = para(lx+10, mid_y + mid_h - 27, onepager.rationale, w=65, size=7.8, leading=10)
    yy -= 6
    tx(lx+10, yy, "Supuestos clave", size=8, bold=True, col=text)
    yy -= 10
    for b in [
        f"Horizonte: {onepager.n_years}a + perp.   g: {fp(onepager.g_exp)}   g∞: {fp(onepager.g_inf)}",
        f"WACC: {fp(onepager.wacc)}   Ke: {fp(onepager.ke)}   Kd: {fp(onepager.kd)}",
        f"CAPEX₀: {fcs(onepager.capex0)}   FCF₁: {fcs(onepager.fcf1)}",
        f"EBIT: {fcs(onepager.ebit)}   NOPAT: {fcs(onepager.nopat)}",
    ]:
        tx(lx+12, yy, "• " + b, size=7.5, col=muted)
        yy -= 10

    yy -= 4
    tx(lx+10, yy, "Checklist Comité", size=8, bold=True, col=text)
    yy -= 10
    for label, ok in onepager.checks:
        tx(lx+12, yy, ("✓ " if ok else "✗ ") + label, size=7.5,
           col=good if ok else bad)
        yy -= 10

    # — Value bridge —
    tx(rx+10, mid_y + mid_h - 14, "Estructura del valor", size=9, bold=True)
    tx(rx+10, mid_y + mid_h - 25, "VAN = PV(FCF) + PV(TV) − CAPEX₀", size=7.5, col=muted)

    pv_fcf_v  = onepager.pv_fcf or 0.0
    pv_tv_v   = onepager.pv_tv  or 0.0
    capex0_v  = onepager.capex0 or 0.0
    total_pos = max(pv_fcf_v + pv_tv_v, 1e-9)

    bar_x = rx + 10
    bar_y = mid_y + mid_h - 58
    bar_w = rw - 20
    bar_h = 13

    cv.setFillColor(colors.Color(1, 1, 1, alpha=0.05))
    cv.rect(bar_x, bar_y, bar_w, bar_h, stroke=0, fill=1)

    seg_fcf = bar_w * (pv_fcf_v / total_pos)
    seg_tv  = bar_w * (pv_tv_v  / total_pos)
    cv.setFillColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.60))
    cv.rect(bar_x, bar_y, seg_fcf, bar_h, stroke=0, fill=1)
    cv.setFillColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.30))
    cv.rect(bar_x + seg_fcf, bar_y, seg_tv, bar_h, stroke=0, fill=1)

    vy = bar_y - 13
    for lbl, val in [
        ("PV FCF (ciclo 1..N):", fcs(onepager.pv_fcf)),
        ("PV TV (perpetuidad):", fcs(onepager.pv_tv)),
        ("– CAPEX₀:",           fcs(-capex0_v) if capex0_v else "—"),
        ("VAN (neto):",         fcs(onepager.npv_base)),
    ]:
        tx(rx+10, vy, lbl,  size=7.5, col=muted)
        txr(rx+rw-10, vy, val, size=7.5, bold=lbl.startswith("VAN"), col=text)
        vy -= 11

    y = mid_y - 6

    # ══ BLOQUE 4: FCF (izq) + MONTE CARLO (der) (h=125) ══════════════════════
    bot_h = 125
    bot_y = y - bot_h

    rr(lx, bot_y, lw, bot_h, r=10, fill=card)
    rr(rx, bot_y, rw, bot_h, r=10, fill=card)

    # — FCF bars —
    tx(lx+10, bot_y + bot_h - 14, "Flujos proyectados (FCF ciclo 1..N)", size=8.5, bold=True)
    tx(lx+10, bot_y + bot_h - 25, f"TV (año {onepager.n_years}): {fcs(onepager.tv)}", size=7.5, col=muted)

    f_list  = list(onepager.fcf_years)
    maxf    = max(abs(v) for v in f_list) if f_list else 1.0
    nb      = len(f_list)
    bax     = lx + 10
    bay     = bot_y + 15
    baw     = lw - 20
    bah     = bot_h - 42

    if nb and maxf > 0:
        gapb = 4
        bw   = (baw - gapb * (nb - 1)) / nb
        for i, val in enumerate(f_list):
            bh   = abs(val) / maxf * bah
            bxi  = bax + i * (bw + gapb)
            col_b = good if val >= 0 else bad
            cv.setFillColor(colors.Color(col_b.red, col_b.green, col_b.blue, alpha=0.65))
            if val >= 0:
                cv.rect(bxi, bay, bw, bh, stroke=0, fill=1)
            else:
                cv.rect(bxi, bay - bh, bw, bh, stroke=0, fill=1)
            cv.setFillColor(muted)
            cv.setFont("Helvetica", 6.2)
            cv.drawCentredString(bxi + bw/2, bay - 9, str(i + 1))

    # — Monte Carlo histogram —
    tx(rx+10, bot_y + bot_h - 14, "Riesgo — Monte Carlo", size=8.5, bold=True)

    mly = bot_y + bot_h - 26
    for ml in [
        f"Sims: {onepager.sims:,}   P(VAN<0): {'—' if onepager.prob_neg is None else f'{onepager.prob_neg*100:.1f}%'}",
        f"P5: {fcs(onepager.p5)}  /  P50: {fcs(onepager.p50)}  /  P95: {fcs(onepager.p95)}",
        f"CVaR5: {fcs(onepager.cvar5)}   σ: {fcs(onepager.std)}",
    ]:
        tx(rx+10, mly, ml, size=7.2, col=muted)
        mly -= 10

    hx = rx + 10
    hy = bot_y + 13
    hw = rw - 20
    hh = bot_h - 62

    cv.setFillColor(colors.Color(1, 1, 1, alpha=0.05))
    cv.rect(hx, hy, hw, hh, stroke=0, fill=1)

    if hist_counts is not None and hist_edges is not None and len(hist_counts) > 0:
        maxc = max(hist_counts) if max(hist_counts) > 0 else 1
        nbh  = len(hist_counts)
        bwh  = hw / nbh
        lo, hi = float(hist_edges[0]), float(hist_edges[-1])

        for i, cnt in enumerate(hist_counts):
            bh   = (cnt / maxc) * hh
            bxi  = hx + i * bwh
            mid_val = (hist_edges[i] + hist_edges[i+1]) / 2
            col_h = bad if mid_val < 0 else accent
            cv.setFillColor(colors.Color(col_h.red, col_h.green, col_h.blue, alpha=0.55))
            cv.rect(bxi, hy, bwh * 0.88, bh, stroke=0, fill=1)

        def x_at(v):
            return hx + (float(v) - lo) / (hi - lo) * hw if hi > lo else hx

        if lo < 0 < hi:
            xx = x_at(0)
            cv.setStrokeColor(colors.Color(bad.red, bad.green, bad.blue, alpha=0.80))
            cv.setLineWidth(1.1)
            cv.setDash()
            cv.line(xx, hy, xx, hy + hh)

        for pv_val in [onepager.p5, onepager.p50, onepager.p95]:
            if pv_val is None or not math.isfinite(pv_val):
                continue
            xx = x_at(pv_val)
            cv.setStrokeColor(colors.Color(1, 1, 1, alpha=0.42))
            cv.setLineWidth(0.8)
            cv.setDash(3, 3)
            cv.line(xx, hy, xx, hy + hh)
            cv.setDash()

    # ══ FOOTER ════════════════════════════════════════════════════════════════
    cv.setFillColor(muted)
    cv.setFont("Helvetica", 7.2)
    cv.drawString(left, mg - 6, "Uso académico (MBA). Resultados dependen de supuestos; no sustituyen due diligence.")
    cv.drawRightString(right, mg - 6, f"ValuationSuite USIL v2.0  ({C})")

    cv.showPage()
    cv.save()
    return buf.getvalue()

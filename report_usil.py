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
    from reportlab.pdfbase import pdfmetrics as _pdfmetrics
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
        return _fmt_cur(v, currency)
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

# ─── Ajuste de texto a un ancho máximo (evita overflow fuera de recuadros) ─────
def _fit_font(s: str, max_w: float, base: float, min_size: float = 6.0, bold: bool = False) -> float:
    """Tamaño de fuente (entre min_size y base) que hace caber `s` en max_w puntos."""
    if not s:
        return base
    font = "Helvetica-Bold" if bold else "Helvetica"
    size = base
    while size > min_size and _pdfmetrics.stringWidth(s, font, size) > max_w:
        size -= 0.3
    return round(max(size, min_size), 1)

def _truncate_ellipsis(s: str, max_w: float, size: float, bold: bool = False) -> str:
    """Recorta `s` con '…' si ni siquiera al tamaño mínimo cabe en max_w."""
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

# ─── Data model ───────────────────────────────────────────────────────────────
@dataclass
class OnePager:
    institution: str
    program: str
    course: str
    currency: str
    project: str
    responsible: str
    programa: str
    integrantes: str
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
        f"{r.institution}",
        f"Programa: {r.programa}  |  {r.course}",
        f"Moneda: {C}  |  Fecha: {r.report_date}",
        f"Proyecto: {r.project}  |  Responsable: {r.responsible}",
        *([ f"Integrantes: {r.integrantes}" ] if r.integrantes.strip() else []),
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
        f"- CAPEX inicial: {fc(r.capex0)}  |  FCF Año 1: {fc(r.fcf1)}",
        "",
        "Flujos proyectados (FCF) — ciclo 1..N",
    ]
    for i, f in enumerate(r.fcf_years, 1):
        lines.append(f"- Año {i}: {fc(f)}")
    lines += [
        f"- TV (año {r.n_years}): {fc(r.tv)}",
        "",
        "Puente contable → FCF Año 1",
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

# ─── PDF premium (ReportLab) — rediseño corporativo full-page ─────────────────
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

    # ── Paleta ───────────────────────────────────────────────────────────────
    bg     = colors.HexColor("#050914")
    card   = colors.HexColor("#0b1733")
    card2  = colors.HexColor("#0d1b3d")
    linec  = colors.Color(1, 1, 1, alpha=0.09)
    text   = colors.HexColor("#EAF1FF")
    muted  = colors.Color(234/255, 241/255, 1, alpha=0.65)
    accent = colors.HexColor("#66A9FF")
    good   = colors.HexColor("#27D17C")
    warn_c = colors.HexColor("#FFCC66")
    bad    = colors.HexColor("#FF5D5D")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def rr(x, y, w, h, r=8, fill=card):
        cv.setFillColor(fill)
        cv.setStrokeColor(linec)
        cv.setLineWidth(0.6)
        cv.roundRect(x, y, w, h, r, stroke=1, fill=1)

    def tx(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawString(x, y, str(s))

    def txr(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawRightString(x, y, str(s))

    def txc(x, y, s, size=8.5, bold=False, col=text):
        cv.setFillColor(col)
        cv.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        cv.drawCentredString(x, y, str(s))

    def hdiv(x1, y, x2):
        cv.setStrokeColor(linec)
        cv.setLineWidth(0.4)
        cv.setDash()
        cv.line(x1, y, x2, y)

    def sec(x, y, label, size=8):
        cv.setFillColor(accent)
        cv.rect(x, y - 1, 3, size + 3, stroke=0, fill=1)
        tx(x + 6, y, label, size=size, bold=True, col=accent)

    def para(x, y, s, w=80, size=7.8, leading=10.5, col=muted, min_y=None, max_lines=None):
        """Párrafo envuelto; se corta con '…' si excede max_lines o el límite min_y."""
        lines = wrap(s, w)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip() + " …"
        yy = y
        for ln in lines:
            if min_y is not None and yy < min_y:
                break
            tx(x, yy, ln, size=size, col=col)
            yy -= leading
        return yy

    def tx_fit(x, y, s, max_w, size=8.5, min_size=6.0, bold=False, col=text):
        """Dibuja alineado a la izquierda, reduciendo tamaño (y truncando si hace falta) para caber en max_w."""
        fsz = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        s2 = _truncate_ellipsis(s, max_w, fsz, bold=bold)
        tx(x, y, s2, size=fsz, bold=bold, col=col)
        return fsz

    def txr_fit(x, y, s, max_w, size=8.5, min_size=6.0, bold=False, col=text):
        """Dibuja alineado a la derecha, reduciendo tamaño (y truncando si hace falta) para caber en max_w."""
        fsz = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        s2 = _truncate_ellipsis(s, max_w, fsz, bold=bold)
        txr(x, y, s2, size=fsz, bold=bold, col=col)
        return fsz

    def txc_fit(x, y, s, max_w, size=8.5, min_size=6.5, bold=False, col=text):
        """Dibuja centrado, reduciendo tamaño (y truncando si hace falta) para caber en max_w."""
        fsz = _fit_font(s, max_w, size, min_size=min_size, bold=bold)
        s2 = _truncate_ellipsis(s, max_w, fsz, bold=bold)
        txc(x, y, s2, size=fsz, bold=bold, col=col)
        return fsz

    def kv_row(x_left, x_right, y, label, value, size=7.5, col=text, bold=False, label_col=muted):
        """Fila etiqueta (izq.) / valor (der.) con auto-ajuste del valor al ancho disponible."""
        tx(x_left, y, label, size=size, col=label_col)
        max_w = (x_right - x_left) * 0.62
        txr_fit(x_right, y, value, max_w, size=size, min_size=6.0, bold=bold, col=col)

    # ── Fondo ─────────────────────────────────────────────────────────────────
    cv.setFillColor(bg)
    cv.rect(0, 0, W, H, stroke=0, fill=1)

    mg    = int(0.375 * inch)    # 27 pt
    top   = H - mg               # 765
    left  = mg                   # 27
    right = W - mg               # 585
    cw    = right - left         # 558
    GAP   = 8

    # ── Layout vertical — ocupa la hoja completa ──────────────────────────────
    h1_h  = 100   # header
    kpi_h = 64    # KPI strip
    # Mid + Bot ocupan el resto
    used_fixed = h1_h + GAP + kpi_h + GAP + GAP + GAP + 22   # 22 = footer area
    avail_flex = (top - mg) - used_fixed
    mid_h = int(avail_flex * 0.45)   # Decisión/Value Bridge: contenido más compacto
    bot_h = avail_flex - mid_h       # FCF bars/Monte Carlo: más aire para el histograma

    # ══ BLOQUE 1 — HEADER ════════════════════════════════════════════════════
    rr(left, top - h1_h, cw, h1_h, r=10, fill=card2)
    # Barra accent izquierda
    cv.setFillColor(accent)
    cv.roundRect(left, top - h1_h, 5, h1_h, 3, stroke=0, fill=1)

    id_left  = left + 14
    id_right = right - 14
    id_w     = id_right - id_left

    tx(id_left, top-17, f"ONE-PAGER EJECUTIVO  —  EVALUACIÓN FINANCIERA  ({C})", size=11, bold=True)

    # Pill DICTAMEN — arriba a la derecha, tamaño ajustado al texto (no invade
    # la columna de identificación de abajo, evitando cualquier solapamiento).
    pill_col = good if onepager.verdict == "APROBADO" else (bad if onepager.verdict == "RECHAZADO" else warn_c)
    pill_txt = f"DICTAMEN: {onepager.verdict}"
    ph = 20
    pw = min(_pdfmetrics.stringWidth(pill_txt, "Helvetica-Bold", 9.5) + 26, id_w * 0.42)
    px = id_right - pw
    py = top - 9 - ph
    cv.setFillColor(colors.Color(pill_col.red, pill_col.green, pill_col.blue, alpha=0.18))
    cv.setStrokeColor(colors.Color(pill_col.red, pill_col.green, pill_col.blue, alpha=0.55))
    cv.setLineWidth(1.0)
    cv.roundRect(px, py, pw, ph, 10, stroke=1, fill=1)
    txc_fit(px + pw/2, py + ph/2 - 3.2, pill_txt, pw - 10, size=9.5, min_size=7.0, bold=True, col=pill_col)

    hdiv(id_left, py - 7, id_right)

    # Columna de identificación — ancho completo, con truncado defensivo por si
    # el texto libre (proyecto / responsable / integrantes) fuera muy largo.
    row_y = py - 20
    tx_fit(id_left, row_y, onepager.institution, id_w, size=7.6, min_size=6.5, col=muted)
    txr(id_right, row_y, f"Fecha: {onepager.report_date}", size=7.6, col=muted)
    row_y -= 12
    tx_fit(id_left, row_y, onepager.programa, id_w, size=9, min_size=7.0, bold=True, col=accent)
    row_y -= 12
    tx_fit(id_left, row_y, f"Proyecto: {onepager.project}", id_w, size=7.8, min_size=6.5, col=text)
    row_y -= 11
    tx_fit(id_left, row_y, f"Responsable: {onepager.responsible}", id_w, size=7.5, min_size=6.5, col=muted)
    if onepager.integrantes.strip():
        row_y -= 11
        integs = " · ".join(p.strip() for p in onepager.integrantes.strip().replace("\n", ",").split(",") if p.strip())
        tx_fit(id_left, row_y, f"Integrantes: {integs}", id_w, size=7.2, min_size=6.2, col=muted)

    y = top - h1_h - GAP

    # ══ BLOQUE 2 — KPI STRIP ═════════════════════════════════════════════════
    # 4 tarjetas amplias (en vez de 6 estrechas) para que quepan sin recortarse
    # montos grandes en Gs. (PYG en unidades completas).
    kpi_n   = 4
    kpi_gap = 8
    kpi_w   = (cw - kpi_gap * (kpi_n - 1)) / kpi_n
    kpi_pad = 10

    pb   = "N/A" if onepager.payback_simple is None     else f"{onepager.payback_simple:.1f} años"
    pbd  = "N/A" if onepager.payback_discounted is None else f"{onepager.payback_discounted:.1f} años"
    prob = "—"   if onepager.prob_neg is None           else f"{onepager.prob_neg*100:.1f}%"

    van_good  = (onepager.npv_base or 0) > 0
    p50_good  = (onepager.p50 or 0) > 0
    prob_ok   = onepager.prob_neg is not None and onepager.prob_neg <= 0.20

    kpis = [
        ("VAN (base)", fc(onepager.npv_base), "Escenario determinístico", good if van_good else bad),
        ("TIR (base)", fp(onepager.irr_base), f"vs. WACC {fp(onepager.wacc)}", accent),
        ("Payback",    f"{pb} / {pbd}",       "Simple / descontado", accent),
        ("P(VAN<0)",   prob,                  f"Monte Carlo · P50 {fcs(onepager.p50)}", good if prob_ok else bad),
    ]

    kbot = y - kpi_h
    for i, (lbl, val, sub, val_col) in enumerate(kpis):
        kx = left + i * (kpi_w + kpi_gap)
        rr(kx, kbot, kpi_w, kpi_h, r=7, fill=card)
        cv.setFillColor(val_col)
        cv.roundRect(kx, kbot + kpi_h - 4, kpi_w, 4, 2, stroke=0, fill=1)
        avail_w = kpi_w - 2 * kpi_pad
        tx(kx+kpi_pad, kbot + kpi_h - 16, lbl, size=7.2, bold=True, col=muted)
        tx_fit(kx+kpi_pad, kbot + 24, val, avail_w, size=13, min_size=8.0, bold=True, col=val_col)
        tx_fit(kx+kpi_pad, kbot + 9,  sub, avail_w, size=6.4, min_size=5.5, col=muted)

    y = kbot - GAP

    # ══ BLOQUE 3 — DECISIÓN (izq 54%) + VALUE BRIDGE (der 46%) ══════════════
    lw  = cw * 0.54 - 4
    rw  = cw - lw - 8
    lx  = left
    rx  = left + lw + 8

    mid_y = y - mid_h
    rr(lx, mid_y, lw, mid_h, r=8, fill=card)
    rr(rx, mid_y, rw, mid_h, r=8, fill=card)

    # — Decisión & supuestos —
    card_bottom_l = mid_y + 8   # margen inferior de seguridad de esta tarjeta
    sec(lx+10, mid_y + mid_h - 15, "DECISIÓN & SUPUESTOS")
    hdiv(lx+10, mid_y + mid_h - 21, lx + lw - 10)
    yy = para(lx+10, mid_y + mid_h - 33, onepager.rationale, w=63, size=7.8, leading=10.5,
              min_y=card_bottom_l, max_lines=4)
    yy -= 10

    sec(lx+10, yy, "SUPUESTOS CLAVE", size=7.8)
    yy -= 13
    for b in [
        f"Horizonte: {onepager.n_years} años + perpetuidad   g: {fp(onepager.g_exp)}   g∞: {fp(onepager.g_inf)}",
        f"WACC: {fp(onepager.wacc)}   Ke: {fp(onepager.ke)}   Kd: {fp(onepager.kd)}",
        f"CAPEX inicial: {fc(onepager.capex0)}",
        f"FCF Año 1: {fc(onepager.fcf1)}   EBIT: {fc(onepager.ebit)}",
    ]:
        if yy < card_bottom_l:
            break
        tx_fit(lx+13, yy, "•  " + b, lw - 26, size=7.5, min_size=6.0, col=muted)
        yy -= 10
    yy -= 8

    checks_list = list(onepager.checks)
    if yy >= card_bottom_l + 10:
        sec(lx+10, yy, "CHECKLIST COMITÉ", size=7.8)
        yy -= 13
        for i, (label, ok) in enumerate(checks_list):
            if yy < card_bottom_l:
                remaining = len(checks_list) - i
                tx(lx+13, yy + 10, f"(+{remaining} ítem{'s' if remaining != 1 else ''} más)", size=6.6, col=muted)
                break
            c_col = good if ok else bad
            tx_fit(lx+13, yy, ("✓  " if ok else "✗  ") + label, lw - 26, size=7.5, min_size=6.0, col=c_col)
            yy -= 10

    # — Estructura del valor —
    sec(rx+10, mid_y + mid_h - 15, "ESTRUCTURA DEL VALOR")
    hdiv(rx+10, mid_y + mid_h - 21, rx + rw - 10)
    tx(rx+10, mid_y + mid_h - 31, "VAN = PV(FCF) + PV(TV) − CAPEX inicial", size=7.4, col=muted)

    def _safe(x):
        return float(x) if x is not None and math.isfinite(x) else 0.0

    pv_fcf_v = _safe(onepager.pv_fcf)
    pv_tv_v  = _safe(onepager.pv_tv)
    capex0_v = _safe(onepager.capex0)
    total_v  = max(pv_fcf_v + pv_tv_v, 1e-9)

    bx, by2 = rx + 12, mid_y + mid_h - 56
    bw_vb, bh_vb = rw - 24, 14
    # Fondo de la barra
    cv.setFillColor(colors.Color(1, 1, 1, alpha=0.05))
    cv.roundRect(bx, by2, bw_vb, bh_vb, 4, stroke=0, fill=1)
    s_fcf = bw_vb * min(max(pv_fcf_v, 0.0) / total_v, 1.0)
    s_tv  = bw_vb * min(max(pv_tv_v,  0.0) / total_v, 1.0)
    # roundRect con ancho ~0 genera un artefacto (aspa/triángulo) — se omite el segmento.
    if s_fcf > 1.0:
        cv.setFillColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.80))
        cv.roundRect(bx, by2, s_fcf, bh_vb, 4, stroke=0, fill=1)
    if s_tv > 1.0:
        cv.setFillColor(colors.Color(accent.red, accent.green, accent.blue, alpha=0.38))
        cv.roundRect(bx + s_fcf, by2, s_tv, bh_vb, 4, stroke=0, fill=1)
    # Etiquetas dentro de la barra
    cv.setFont("Helvetica", 5.5)
    cv.setFillColor(bg)
    if s_fcf > 28:
        cv.drawString(bx + 4, by2 + 4, "PV FCF")
    if s_tv > 22:
        cv.drawRightString(bx + s_fcf + s_tv - 3, by2 + 4, "PV TV")

    vy = by2 - 14
    for lbl, val, is_total in [
        ("PV FCF (ciclo 1..N):",   fc(onepager.pv_fcf), False),
        ("PV TV (perpetuidad):",   fc(onepager.pv_tv),  False),
        ("− CAPEX inicial:",       fc(-capex0_v) if capex0_v else "—", False),
        ("VAN (neto):", fc(onepager.npv_base), True),
    ]:
        if is_total:
            hdiv(rx+10, vy + 13, rx + rw - 10)
            vy -= 3
        vc = (good if van_good else bad) if is_total else text
        kv_row(rx+12, rx + rw - 12, vy, lbl, val, size=7.5, bold=is_total, col=vc)
        vy -= 12

    # Lista de FCF anuales
    vy -= 8
    fcf_list = list(onepager.fcf_years)
    sec(rx+10, vy, "FCF POR AÑO", size=7.5)
    vy -= 13
    for i, f_v in enumerate(fcf_list, 1):
        if vy < mid_y + 10:
            remaining = len(fcf_list) - (i - 1)
            tx(rx+12, vy + 9, f"(+{remaining} año{'s' if remaining != 1 else ''} más)", size=6.6, col=muted)
            break
        fc_col = good if f_v >= 0 else bad
        kv_row(rx+12, rx + rw - 12, vy, f"Año {i}:", fc(f_v), size=7.2, col=fc_col)
        vy -= 9

    y = mid_y - GAP

    # ══ BLOQUE 4 — FCF BARS (izq 48%) + MONTE CARLO (der 52%) ═══════════════
    lw2 = cw * 0.46 - 4
    rw2 = cw - lw2 - 8
    rx2 = left + lw2 + 8

    bot_y = y - bot_h
    rr(lx, bot_y, lw2, bot_h, r=8, fill=card)
    rr(rx2, bot_y, rw2, bot_h, r=8, fill=card)

    # — FCF bars —
    sec(lx+10, bot_y + bot_h - 15, "FLUJOS DE CAJA PROYECTADOS (FCF)")
    hdiv(lx+10, bot_y + bot_h - 21, lx + lw2 - 10)
    tx_fit(lx+10, bot_y + bot_h - 31, f"Valor Terminal Año {onepager.n_years}: {fc(onepager.tv)}",
           lw2 - 20, size=7.3, min_size=6.0, col=muted)

    f_list  = list(onepager.fcf_years)
    nb      = len(f_list)
    bax     = lx + 14
    baw     = lw2 - 28
    label_y = bot_y + 9                    # etiquetas "Año N" — franja fija al pie
    plot_bottom = bot_y + 20                # piso del área de barras (encima de las etiquetas)
    plot_top    = bot_y + bot_h - 40        # techo del área de barras (debajo del título)
    bah_total   = max(plot_top - plot_bottom, 10.0)

    max_pos = max([v for v in f_list if v > 0], default=0.0)
    max_neg = max([-v for v in f_list if v < 0], default=0.0)   # magnitud del más negativo
    mag_tot = max_pos + max_neg
    # La línea base se reparte proporcionalmente para que ninguna barra
    # (positiva o negativa) se salga del recuadro.
    neg_h = bah_total * (max_neg / mag_tot) if mag_tot > 0 else 0.0
    pos_h = bah_total - neg_h
    bay   = plot_bottom + neg_h             # línea de base (cero)

    if nb:
        gapb  = 6
        bw_b  = (baw - gapb * (nb - 1)) / nb
        for i, val in enumerate(f_list):
            bxi = bax + i * (bw_b + gapb)
            if val >= 0:
                bh_b = (val / max_pos * pos_h) if max_pos > 0 else 0.0
                c_b  = good
                if bh_b > 0.5:
                    cv.setFillColor(colors.Color(c_b.red, c_b.green, c_b.blue, alpha=0.72))
                    cv.roundRect(bxi, bay, bw_b, bh_b, 3, stroke=0, fill=1)
            else:
                bh_b = (-val / max_neg * neg_h) if max_neg > 0 else 0.0
                c_b  = bad
                if bh_b > 0.5:
                    cv.setFillColor(colors.Color(c_b.red, c_b.green, c_b.blue, alpha=0.72))
                    cv.roundRect(bxi, bay - bh_b, bw_b, bh_b, 3, stroke=0, fill=1)
            # Año label — siempre en la franja fija, nunca se solapa con las barras
            cv.setFillColor(muted)
            cv.setFont("Helvetica", 6.5)
            cv.drawCentredString(bxi + bw_b/2, label_y, f"Año {i+1}")

    # — Monte Carlo —
    sec(rx2+10, bot_y + bot_h - 15, "RIESGO — MONTE CARLO")
    hdiv(rx2+10, bot_y + bot_h - 21, rx2 + rw2 - 10)

    # Filas etiqueta/valor con auto-ajuste — evita overflow con montos PYG largos
    mc_left, mc_right = rx2+10, rx2+rw2-10
    mly = bot_y + bot_h - 32
    prob_str = "—" if onepager.prob_neg is None else f"{onepager.prob_neg*100:.1f}%"
    for lbl, val, s_col in [
        ("Simulaciones:", f"{onepager.sims:,}".replace(",", "."), muted),
        ("P(VAN<0):", prob_str, good if prob_ok else bad),
        ("P5:",    fcs(onepager.p5),    muted),
        ("P50:",   fcs(onepager.p50),   good if p50_good else bad),
        ("P95:",   fcs(onepager.p95),   muted),
        ("CVaR5:", fcs(onepager.cvar5), bad),
        ("σ:",     fcs(onepager.std),   muted),
    ]:
        kv_row(mc_left, mc_right, mly, lbl, val, size=7.2, col=s_col)
        mly -= 10

    # Histograma
    hx = rx2 + 12
    hy = bot_y + 14
    hw = rw2 - 24
    hh = max(mly - hy - 6, 20)

    cv.setFillColor(colors.Color(1, 1, 1, alpha=0.04))
    cv.roundRect(hx, hy, hw, hh, 4, stroke=0, fill=1)

    if hist_counts is not None and hist_edges is not None and len(hist_counts) > 0:
        maxc = max(hist_counts) if max(hist_counts) > 0 else 1
        nbh  = len(hist_counts)
        bwh  = hw / nbh
        lo   = float(hist_edges[0])
        hi_e = float(hist_edges[-1])

        for i, cnt in enumerate(hist_counts):
            bh_h = (cnt / maxc) * hh
            bxi  = hx + i * bwh
            mid_v = (hist_edges[i] + hist_edges[i + 1]) / 2
            ch   = bad if mid_v < 0 else accent
            cv.setFillColor(colors.Color(ch.red, ch.green, ch.blue, alpha=0.65))
            cv.rect(bxi, hy, bwh * 0.90, bh_h, stroke=0, fill=1)

        def x_at(v):
            return hx + (float(v) - lo) / (hi_e - lo) * hw if hi_e > lo else hx

        if lo < 0 < hi_e:
            xx = x_at(0)
            cv.setStrokeColor(colors.Color(bad.red, bad.green, bad.blue, alpha=0.85))
            cv.setLineWidth(1.2)
            cv.setDash()
            cv.line(xx, hy, xx, hy + hh)

        for pv_val in [onepager.p5, onepager.p50, onepager.p95]:
            if pv_val is None or not math.isfinite(pv_val):
                continue
            xx = x_at(pv_val)
            cv.setStrokeColor(colors.Color(1, 1, 1, alpha=0.38))
            cv.setLineWidth(0.8)
            cv.setDash(3, 3)
            cv.line(xx, hy, xx, hy + hh)
            cv.setDash()

    # ══ FOOTER ══════════════════════════════════════════════════════════════
    hdiv(left, bot_y - 5, right)
    cv.setFillColor(muted)
    cv.setFont("Helvetica", 7)
    cv.drawString(left, mg + 4, "Uso académico (MBA). Resultados dependen de supuestos; no sustituyen due diligence.")
    cv.drawRightString(right, mg + 4, f"ValuationSuite USIL v2.0  ·  {C}  ·  {onepager.report_date}")

    cv.showPage()
    cv.save()
    return buf.getvalue()

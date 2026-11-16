# test_engine.py — pruebas de regresión (Fase 5) + verificaciones de cada corrección C1–C8 y de los criterios CFA.
# Ejecutar:  python -m unittest -v        (no requiere pytest)
import unittest
from dataclasses import replace

import numpy as np

import fixtures as fx
import glosario as gl
import report_usil as rep
import valuation_engine as ve


def rel(a, b):
    return abs(a - b) / abs(b)


def codes(ev):
    return {a.code for a in ev.alerts}


def proj_demo(**kw):
    base = dict(n_years=5, capex0=500, revenue_y1=1000, var_cost_y1=500, fixed_cost_y1=250, g_revenue=.03,
                g_fixed=.03, tax=.10, dep_years=10, maint_capex_pct=1.0)
    base.update(kw)
    return ve.Project(**base)


# ═════════════════════════════════════════════════════════════════════════════
class TestT1aT5(unittest.TestCase):
    def test_T1_sin_vt_van_es_suma_descontada(self):
        p = ve.Project(n_years=3, capex0=250, fcf_direct=[100, 120, 140])
        ev = ve.evaluate(p, ve.wacc_from_reported(0.10))
        self.assertAlmostEqual(ev.metrics.van_main, 100 / 1.1 + 120 / 1.1 ** 2 + 140 / 1.1 ** 3 - 250, places=6)

    def test_T1_motor_desagregado_sin_extras(self):
        # Sin impuestos, capital de trabajo ni reposición: FCF = EBITDA → VAN = Σ EBITDA descontado − CAPEX.
        p = proj_demo(tax=0.0, maint_capex_pct=0.0, g_revenue=0.0, g_fixed=0.0)
        ev = ve.evaluate(p, ve.wacc_from_reported(0.10))
        esperado = sum(250 / 1.1 ** t for t in range(1, 6)) - 500
        self.assertAlmostEqual(ev.metrics.van_main, esperado, places=6)

    def test_T2_ke_gs_mayor_que_ke_usd(self):
        w = ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.10, debt=0, equity=1, kd=.10, infl_flow=.035, infl_usd=.025)
        wb = ve.wacc_breakdown(w)
        self.assertGreater(wb.ke_flow, wb.ke_usd)
        self.assertAlmostEqual(wb.ke_flow, (1 + wb.ke_usd) * 1.035 / 1.025 - 1, places=12)

    def test_T3_alerta_pesimista_aunque_monte_carlo_sea_bajo(self):
        spec = ve.MCSpec(sims=10_000, seed=1, ranges=dict(price=(0.93, 1, 1.04), volume=(0.93, 1, 1.04),
                         unit_vc=(0.97, 1, 1.05), fixed=(0.97, 1, 1.05), capex=(1.0, 1, 1.05)), wacc_range=0.01)
        ev = ve.evaluate(proj_demo(), ve.wacc_from_reported(0.10), spec)
        self.assertLess(ev.mc.stats["prob_neg"], 0.20)      # premisa: la simulación "se ve bien"
        self.assertLess(ev.pess_van_main, 0)                # ... pero el pesimista pierde
        self.assertIn("V11", codes(ev))                     # → alerta obligatoria

    def test_T4_caso_manual(self):
        m = ve.evaluate(ve.Project(n_years=5, capex0=300, fcf_direct=[100] * 5), ve.wacc_from_reported(0.10)).metrics
        self.assertAlmostEqual(m.van_main, 79.08, places=2)
        self.assertAlmostEqual(m.irr_sin_vt * 100, 19.86, places=2)

    def test_T5_validaciones_disparan(self):
        wr = ve.wacc_from_reported(0.10)
        flat = lambda **k: ve.Project(n_years=5, capex0=300, fcf_direct=[100] * 5, **k)
        # V01 Ke < Kd
        wb = ve.wacc_breakdown(ve.WaccInputs(rf=.02, erp=.01, crp=0, beta_u=.5, tax=.1, debt=1, equity=1, kd=.20))
        self.assertIn("V01", codes(ve.evaluate(flat(), wb)))
        # V02 TIR > 50 % y V03 payback < 2 años
        ev = ve.evaluate(ve.Project(n_years=5, capex0=100, fcf_direct=[100] * 5), wr)
        self.assertTrue({"V02", "V03"} <= codes(ev))
        # V04 VT > 50 % del valor (perpetuidad justificada)
        ev = ve.evaluate(flat(terminal_mode="perpetuity", vt_justified=True, g_inf=0.03), wr)
        self.assertIn("V04", codes(ev))
        # V05 g explícito > 10 % por más de 3 años
        self.assertIn("V05", codes(ve.evaluate(flat(g_revenue=.15), wr)))
        # V06 EBIT y FCF incoherentes (caso Smart Recovery: FCF/EBIT = 0,027)
        f = fx.F2_SMART_RECOVERY
        ev = ve.evaluate(ve.Project(n_years=5, capex0=f["capex0"], fcf_direct=f["fcfs"], ebit_reported=f["ebit_y1"]), wr)
        self.assertIn("V06", codes(ev))
        # V07 moneda de la tasa distinta a la del flujo
        wb = ve.wacc_breakdown(ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.1, debt=0, equity=1, kd=.1,
                                             infl_flow=.035, infl_usd=.025, convert=False))
        self.assertIn("V07", codes(ve.evaluate(flat(), wb)))
        # V08 horizontes distintos entre escenarios comparados
        rows = [dict(name="A", n_years=5, wacc=.1, wacc_key=1), dict(name="B", n_years=8, wacc=.1, wacc_key=1)]
        self.assertIn("V08", {a.code for a in ve.compare_scenarios(rows)})
        # V09 perpetuidad sin justificar → se evalúa sin VT
        ev = ve.evaluate(flat(terminal_mode="perpetuity"), wr)
        self.assertIn("V09", codes(ev))
        self.assertEqual(ev.metrics.mode, "none")
        # V10 reposición < depreciación en la perpetuidad
        ev = ve.evaluate(proj_demo(terminal_mode="perpetuity", vt_justified=True, maint_capex_pct=0.5), wr)
        self.assertIn("V10", codes(ev))
        # V11 se prueba en test_T3
        # V12 g∞ acotado a WACC − 2 pp
        ev = ve.evaluate(flat(terminal_mode="perpetuity", vt_justified=True, g_inf=0.09), wr)
        self.assertIn("V12", codes(ev))
        # V13 FCF negativo
        ev = ve.evaluate(ve.Project(n_years=3, capex0=100, fcf_direct=[50, -20, 80]), wr)
        self.assertIn("V13", codes(ev))

    def test_T5_validacion_negativa_no_dispara_de_mas(self):
        # Un proyecto sano no debe levantar alertas de severidad alta.
        ev = ve.evaluate(proj_demo(), ve.wacc_from_reported(0.12))
        self.assertFalse([a for a in ev.alerts if a.severity == "alta"], ev.alerts)

    def test_T6_vive_en_TestCompatibilidad(self):
        self.assertTrue(True)


# ═════════════════════════════════════════════════════════════════════════════
class TestCorrecciones(unittest.TestCase):
    wr = ve.wacc_from_reported(0.10)

    # C1 — valor terminal opcional
    def test_C1_vt_desactivado_por_defecto(self):
        self.assertEqual(proj_demo().terminal_mode, "none")
        self.assertEqual(proj_demo().effective_mode(), "none")

    def test_C1_muestra_siempre_con_y_sin_vt_y_peso(self):
        m = ve.evaluate(proj_demo(), self.wr).metrics
        self.assertTrue(m.con_vt_is_reference)            # con VT referencial cuando está desactivado
        self.assertGreater(m.van_con_vt, m.van_sin_vt)
        self.assertTrue(0 < m.vt_weight < 1)
        self.assertEqual(m.van_main, m.van_sin_vt)

    def test_C1_desecho_neto_de_impuesto(self):
        p = proj_demo(terminal_mode="salvage", salvage_value=400.0, maint_capex_pct=0.0)
        fl = ve.project_flows(p)
        ganancia = max(400.0 - fl.book_end[0], 0)
        self.assertAlmostEqual(fl.salvage_net[0], 400.0 - 0.10 * ganancia, places=9)
        m = ve.evaluate(p, self.wr).metrics
        self.assertGreater(m.van_main, m.van_sin_vt)

    def test_C1_perpetuidad_normaliza_reinversion(self):
        p = proj_demo(terminal_mode="perpetuity", vt_justified=True, maint_capex_pct=0.2)
        fl = ve.project_flows(p)
        g = 0.02
        capex_n = max(fl.capex_repl[0, -1], fl.dep[0, -1]) * (1 + g)
        self.assertGreaterEqual(capex_n, fl.dep[0, -1] * (1 + g) - 1e-9)       # reinversión ≥ depreciación
        eb = fl.ebitda[0, -1] * (1 + g)
        esperado = eb - 0.10 * max(eb - capex_n, 0) - capex_n - fl.nwc_end[0] * g
        self.assertAlmostEqual(float(fl.norm_fcf(g)[0]), esperado, places=9)

    # C2 — TIR principal sin VT, TIRM
    def test_C2_tir_principal_sin_vt_y_tirm(self):
        m = ve.evaluate(proj_demo(terminal_mode="perpetuity", vt_justified=True), self.wr).metrics
        self.assertLess(m.irr_sin_vt, m.irr_con_vt)
        self.assertIsNotNone(m.mirr_sin_vt)
        self.assertLess(abs(m.mirr_sin_vt - m.wacc), abs(m.irr_sin_vt - m.wacc))   # TIRM más cerca del WACC

    # C3 — WACC en moneda del flujo
    def test_C3_desglose_completo_y_formula(self):
        w = ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.10, debt=40, equity=60, kd=.11,
                          size_premium=.01, infl_flow=.035, infl_usd=.025)
        b = ve.wacc_breakdown(w)
        bl = .9 * (1 + .9 * 40 / 60)
        ke_usd = .045 + bl * .055 + .02 + .01
        ke_f = (1 + ke_usd) * 1.035 / 1.025 - 1
        self.assertAlmostEqual(b.beta_l, bl, places=12)
        self.assertAlmostEqual(b.ke_usd, ke_usd, places=12)
        self.assertAlmostEqual(b.kd_post, .11 * .9, places=12)
        self.assertAlmostEqual(b.wE + b.wD, 1.0, places=12)
        self.assertAlmostEqual(b.wacc, .6 * ke_f + .4 * .11 * .9, places=12)
        self.assertEqual(b.rate_currency, "PYG")

    def test_C3_flujo_en_usd_no_convierte(self):
        w = ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.1, debt=0, equity=1, kd=.07, infl_flow=.5,
                          infl_usd=.025, flow_currency="USD")
        b = ve.wacc_breakdown(w)
        self.assertAlmostEqual(b.ke_flow, b.ke_usd, places=12)
        self.assertFalse(b.mismatch)

    def test_C3_modo_legacy_equivale_sin_conversion(self):
        a = ve.legacy_wacc(.045, .055, .02, .9, .10, 40, 60, .11)
        w = ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.10, debt=40, equity=60, kd=.11,
                          infl_flow=.035, infl_usd=.025, convert=False)
        self.assertAlmostEqual(ve.wacc_breakdown(w).wacc, a["wacc"], places=12)

    # C4 — Monte Carlo
    def test_C4_estadisticos_y_reproducibilidad(self):
        spec = ve.MCSpec(sims=8000, seed=11)
        a = ve.evaluate(proj_demo(), self.wr, spec).mc
        b = ve.evaluate(proj_demo(), self.wr, spec).mc
        np.testing.assert_array_equal(a.npv_main, b.npv_main)                   # misma semilla → mismo resultado
        s = a.stats
        self.assertLessEqual(s["p5"], s["p50"]); self.assertLessEqual(s["p50"], s["p95"])
        self.assertLessEqual(s["cvar5"], s["p5"])                               # CVaR5 ≤ P5
        self.assertTrue(0.0 <= s["base_percentile"] <= 1.0)
        self.assertEqual(s["valid_rate"], 1.0)

    def test_C4_los_drivers_mueven_el_resultado(self):
        # El MC de la v2.0 no tenía precio/volumen/costos: acá el ancho de la distribución depende de ellos.
        ang = ve.MCSpec(sims=6000, seed=3, ranges=dict(price=(0.99, 1, 1.01), volume=(0.99, 1, 1.01), unit_vc=(0.99, 1, 1.01),
                        fixed=(0.99, 1, 1.01), capex=(0.99, 1, 1.01)), wacc_range=0.001)
        anc = ve.MCSpec(sims=6000, seed=3, ranges=dict(price=(0.8, 1, 1.2), volume=(0.8, 1, 1.2), unit_vc=(0.8, 1, 1.2),
                        fixed=(0.8, 1, 1.2), capex=(0.8, 1, 1.2)), wacc_range=0.03)
        s1 = ve.evaluate(proj_demo(), self.wr, ang).mc.stats["std"]
        s2 = ve.evaluate(proj_demo(), self.wr, anc).mc.stats["std"]
        self.assertGreater(s2, 5 * s1)

    def test_C4_correlacion_y_distribucion_normal(self):
        spec = ve.MCSpec(sims=20_000, seed=5, dist="normal", corr={("price", "volume"): -0.8})
        d = ve._draw(spec)
        self.assertLess(np.corrcoef(d["price"], d["volume"])[0, 1], -0.6)
        lo, _, hi = spec.ranges["price"]
        self.assertTrue((d["price"] >= lo - 1e-12).all() and (d["price"] <= hi + 1e-12).all())   # truncada al rango

    def test_C4_matriz_de_correlacion_invalida(self):
        with self.assertRaises(ValueError):
            ve._draw(ve.MCSpec(sims=100, corr={("price", "volume"): 0.99, ("volume", "unit_vc"): 0.99, ("price", "unit_vc"): -0.99}))

    def test_C4_g_inf_acotado(self):
        p = proj_demo(terminal_mode="perpetuity", vt_justified=True, g_inf=0.30)
        ev = ve.evaluate(p, self.wr, ve.MCSpec(sims=2000, seed=1))
        self.assertTrue(np.isfinite(ev.mc.npv_main).all())
        self.assertLessEqual(ev.valuation.g_eff[0], 0.10 - ve.G_INF_MARGIN + 1e-12)

    def test_C4_pesimista_p10_es_menos_severo_que_extremos(self):
        a = ve.evaluate(proj_demo(), self.wr, ve.MCSpec(sims=1000, seed=1, pess_quantile=0.0)).pess_van_main
        b = ve.evaluate(proj_demo(), self.wr, ve.MCSpec(sims=1000, seed=1, pess_quantile=0.10)).pess_van_main
        self.assertLess(a, b)

    # C5 — motor de flujo desagregado
    def test_C5_ire_solo_si_ebit_positivo(self):
        p = proj_demo(var_cost_y1=800, fixed_cost_y1=400)         # EBITDA < 0
        fl = ve.project_flows(p)
        self.assertTrue((fl.ebit[0] < 0).all())
        self.assertTrue((fl.tax[0] == 0).all())

    def test_C5_identidad_del_fcf(self):
        fl = ve.project_flows(proj_demo(nwc_y1=80))
        fcf = fl.revenue - fl.var_cost - fl.fixed_cost - fl.tax - fl.d_nwc - fl.capex_repl
        np.testing.assert_allclose(fl.fcf_ops, fcf)
        np.testing.assert_allclose(fl.ebit + fl.dep, fl.ebitda)

    def test_C5_capital_de_trabajo_y_recupero(self):
        p = proj_demo(nwc_y1=100, g_revenue=0.0)
        fl = ve.project_flows(p)
        self.assertAlmostEqual(float(fl.d_nwc[0].sum()), float(fl.nwc_end[0]), places=9)
        con = ve.evaluate(p, self.wr).metrics.van_sin_vt
        sin = ve.evaluate(replace(p, recover_nwc=False), self.wr).metrics.van_sin_vt
        self.assertGreater(con, sin)

    def test_C5_rampa(self):
        fl = ve.project_flows(proj_demo(ramp_years=2, ramp_start=0.5, g_revenue=0.0))
        np.testing.assert_allclose(fl.revenue[0, :3] / 1000, [0.5, 0.75, 1.0])
        self.assertAlmostEqual(fl.revenue[0, 3] / 1000, 1.0)

    def test_C5_reposicion_y_depreciacion(self):
        fl = ve.project_flows(proj_demo(dep_years=5, maint_capex_pct=1.0, n_years=6))
        self.assertAlmostEqual(fl.dep[0, 0], 100.0)                                  # 500/5
        self.assertAlmostEqual(fl.dep[0, 1], 100.0 + 100.0 / 5)                      # + reposición año 1 / 5

    # C6/C7/C8
    def test_C7_wacc_constante_entre_horizontes(self):
        a = ve.evaluate(proj_demo(n_years=5), ve.wacc_breakdown(ve.WaccInputs(.045, .055, .02, .9, .1, 40, 60, .11))).metrics.wacc
        b = ve.evaluate(proj_demo(n_years=8), ve.wacc_breakdown(ve.WaccInputs(.045, .055, .02, .9, .1, 40, 60, .11))).metrics.wacc
        self.assertEqual(a, b)

    def test_C7_comparar_detecta_wacc_distinto_con_mismos_inputs(self):
        rows = [dict(name="A", n_years=5, wacc=.1, wacc_key=1), dict(name="B", n_years=5, wacc=.1011, wacc_key=1)]
        self.assertIn("C7", {a.code for a in ve.compare_scenarios(rows)})

    def test_C7_payback_se_redondea_no_trunca(self):
        self.assertEqual(ve.fmt_years(1.4186), "1.42")
        self.assertEqual(ve.fmt_years(1.485), "1.49")
        self.assertEqual(ve.fmt_years(1.4849), "1.48")
        self.assertEqual(ve.fmt_years(None), "N/D")

    def test_C7_tasas_con_la_precision_usada(self):
        self.assertEqual(ve.fmt_rate(0.14529866), "14.5299%")

    def test_C8_lectura_no_aprueba(self):
        ev = ve.evaluate(proj_demo(), ve.wacc_from_reported(0.10), ve.MCSpec(sims=2000, seed=2))
        self.assertIn("bajo los supuestos cargados", ev.reading.headline)
        self.assertNotIn("APROBADO", ev.reading.headline)

    def test_C8_variable_critica_y_valor_limite_anulan_el_van(self):
        p = proj_demo()
        ev = ve.evaluate(p, ve.wacc_from_reported(0.10))
        self.assertIsNotNone(ev.critical)
        for b in ev.breakevens:
            if b.limit_value is None or b.driver in ("wacc",):
                continue
            mult = 1 + b.rel_change
            kw = dict(price_m=1.0, vol_m=1.0, vc_m=1.0, fix_m=1.0, capex_m=1.0)
            kw[{"price": "price_m", "volume": "vol_m", "unit_vc": "vc_m", "fixed": "fix_m", "capex": "capex_m"}[b.driver]] = mult
            van = ve.valuate(ve.project_flows(p, **kw), 0.10, p).van_main[0]
            self.assertLess(abs(van), 1e-2 * p.capex0, (b.driver, van))
        be_w = [b for b in ev.breakevens if b.driver == "wacc"][0]
        self.assertAlmostEqual(be_w.limit_value, ve.evaluate(p, ve.wacc_from_reported(0.10)).metrics.irr_sin_vt, delta=2e-3)

    def test_C8_variable_critica_es_la_mas_fragil(self):
        ev = ve.evaluate(proj_demo(), ve.wacc_from_reported(0.10))
        m = min(abs(b.rel_change) for b in ev.breakevens if b.rel_change is not None)
        self.assertEqual(abs(ev.critical.rel_change), m)


# ═════════════════════════════════════════════════════════════════════════════
class TestCFA(unittest.TestCase):
    """Criterios de presupuesto de capital y valoración (lineamientos CFA)."""
    wr = ve.wacc_from_reported(0.10)

    def test_valor_anual_equivalente_permite_comparar_vidas_distintas(self):
        eaa = ve.equivalent_annual_annuity(100.0, 0.10, 5)
        self.assertAlmostEqual(eaa, 100 * 0.10 / (1 - 1.1 ** -5), places=9)
        # A (3 años) y B (10 años): B gana por VAN, pero A gana por valor anual equivalente.
        a = ve.evaluate(ve.Project(n_years=3, capex0=200, fcf_direct=[105] * 3), self.wr).metrics
        b = ve.evaluate(ve.Project(n_years=10, capex0=200, fcf_direct=[50] * 10), self.wr).metrics
        self.assertGreater(b.van_main, a.van_main)
        self.assertGreater(a.eaa, b.eaa)

    def test_flujos_no_convencionales_alertan_tir_no_unica(self):
        ev = ve.evaluate(ve.Project(n_years=4, capex0=50, fcf_direct=[100, -300, 100, 400]), self.wr)
        self.assertGreater(ev.metrics.sign_changes, 1)
        self.assertIn("V14", codes(ev))

    def test_coherencia_nominal_real(self):
        wb = ve.wacc_breakdown(ve.WaccInputs(.045, .055, .02, .9, .1, 0, 1, .1, infl_flow=.035, infl_usd=.025))
        ev = ve.evaluate(proj_demo(g_revenue=0.0, g_fixed=0.0), wb)
        self.assertIn("V15", codes(ev))
        ev = ve.evaluate(proj_demo(g_revenue=0.04, g_fixed=0.04), wb)
        self.assertNotIn("V15", codes(ev))

    def test_g_inf_no_debe_superar_crecimiento_nominal(self):
        wb = ve.wacc_breakdown(ve.WaccInputs(.045, .055, .02, .9, .1, 0, 1, .1, infl_flow=.035, infl_usd=.025))
        ev = ve.evaluate(proj_demo(terminal_mode="perpetuity", vt_justified=True, g_inf=0.07), wb)
        self.assertIn("V16", codes(ev))

    def test_kd_no_puede_estar_bajo_la_tasa_libre_de_riesgo(self):
        wb = ve.wacc_breakdown(ve.WaccInputs(.045, .055, .02, .9, .1, 50, 50, .03, infl_flow=.035, infl_usd=.025))
        ev = ve.evaluate(proj_demo(), wb)
        self.assertIn("V17", codes(ev))

    def test_van_prevalece_sobre_la_tir_en_la_lectura(self):
        ev = ve.evaluate(ve.Project(n_years=5, capex0=300, fcf_direct=[50] * 5), self.wr)
        self.assertLess(ev.metrics.van_main, 0)
        self.assertEqual(ev.reading.status, "desfavorable")

    def test_indice_de_rentabilidad(self):
        m = ve.evaluate(ve.Project(n_years=5, capex0=300, fcf_direct=[100] * 5), self.wr).metrics
        self.assertAlmostEqual(m.ir_sin_vt, 1 + m.van_sin_vt / 300, places=12)


# ═════════════════════════════════════════════════════════════════════════════
class TestCompatibilidad(unittest.TestCase):
    """T6: el modo compatibilidad reproduce los fixtures de la Fase 1 dentro de ±0,5 %."""

    def test_F1(self):
        f = fx.F1_FRIOLOG
        r = ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"])
        self.assertLess(rel(r["van"], f["reported"]["van"]), 0.005)
        self.assertLess(rel(r["irr"], f["reported"]["irr"]), 0.005)
        self.assertEqual(ve.fmt_years(r["payback"], 1), "1.1")
        self.assertEqual(ve.fmt_years(r["payback_disc"], 1), "1.3")

    def test_F2_ambas_corridas(self):
        f = fx.F2_SMART_RECOVERY
        r = ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], fcfs=f["fcfs"])
        for k, kk in (("van", "van"), ("pv_fcf", "pv_fcf"), ("pv_tv", "pv_tv"), ("tv", "tv")):
            self.assertLess(rel(r[k], f["reported"][kk]), 0.005, k)
        self.assertLess(rel(r["irr"], f["reported"]["irr"]), 0.005)
        r2 = ve.legacy_dcf(f["capex0"], f["n_years"], f["reported_run2"]["wacc"], f["g_inf"], fcfs=f["fcfs"])
        self.assertLess(rel(r2["van"], f["reported_run2"]["van"]), 0.005)
        self.assertLess(rel(r2["irr"], f["reported_run2"]["irr"]), 0.005)

    def test_F3_usd_a_7000(self):
        f = fx.F3_PANTALLA_RH
        r = ve.legacy_dcf(f["capex0"], f["n_years"], f["wacc"], f["g_inf"], f["fcf1"], f["g"])
        rp = f["reported"]
        self.assertLess(rel(r["van"] / 7000, rp["van_usd"]), 0.005)
        self.assertLess(rel(r["van_sin_vt"] / 7000, rp["van_sin_vt_usd"]), 0.005)
        self.assertLess(rel(r["irr"], rp["irr"]), 0.005)
        self.assertLess(rel(r["vt_pct"], rp["vt_pct"]), 0.005)
        self.assertEqual(ve.fmt_years(r["payback"], 1), "6.1")        # redondeado; truncado daría 6.0

    def test_F4_con_fcf_armado(self):
        f = fx.F4_OVOS_TERRA
        fcf = (f["ventas"] - f["balanceado"] - f["fijos"]) * 0.9 - f["reposicion_costo_anual_equiv"]
        ke = f["rf"] + f["beta"] * f["erp"] + f["crp"]
        r = ve.legacy_dcf(f["capex_stage1"], f["n_years"], ke, f["g_inf"], fcf, 0.0)
        self.assertLess(rel(r["van"], f["reported"]["van"]), 0.005)
        self.assertLess(rel(r["irr"], f["reported"]["irr"]), 0.005)
        self.assertEqual(ve.fmt_years(r["payback"], 2), "3.41")
        self.assertEqual(ve.fmt_years(r["payback_disc"], 2), "4.54")

    def test_legacy_tir_mayor_a_200_se_descarta_como_en_v20(self):
        self.assertIsNone(ve.legacy_safe_irr([-100, 400, 400]))

    def test_legacy_nopat_negativo_da_credito_fiscal_ficticio(self):
        r = ve.legacy_fcf1(sales=100, cvar=60, cfix=40, dep=20, capex_y1=0, delta_wc=0, tax=0.10)
        self.assertLess(r["ebit"], 0)
        self.assertAlmostEqual(r["nopat"], r["ebit"] * 0.9)             # defecto documentado (D5)
        self.assertEqual(float(ve.project_flows(proj_demo(var_cost_y1=800, fixed_cost_y1=400)).tax.sum()), 0.0)  # el motor corregido no lo repite


# ═════════════════════════════════════════════════════════════════════════════
class TestReporte(unittest.TestCase):
    def _op(self, **kw):
        ev = ve.evaluate(proj_demo(**kw), ve.wacc_from_reported(0.10), ve.MCSpec(sims=3000, seed=4))
        return rep.OnePager(ev=ev, currency="PYG", institution="USIL", program="MBA", course="Valuation", project="X",
                            responsible="Y", programa="MBA USIL", integrantes="Ana, Luis", report_date="2026-10-12"), ev

    def test_txt_contiene_los_elementos_exigidos(self):
        op, ev = self._op()
        t = rep.build_onepager_text(op)
        for frag in ("VAN sin VT", "VAN con VT", "Peso del VT", "TIR sin VT", "TIR con VT", "TIR modificada", "TASA DE DESCUENTO EN",
                     "WACC:", "Variable crítica", "ESCENARIO PESIMISTA", "ALERTAS ACTIVAS", "SUPUESTOS Y LIMITACIONES",
                     "bajo los supuestos cargados"):
            self.assertIn(frag, t)
        self.assertNotIn("APROBADO", t)

    @unittest.skipUnless(rep.REPORTLAB_OK, "reportlab no instalado")
    def test_pdf_se_genera_en_una_pagina(self):
        op, ev = self._op()
        c, e = np.histogram(ev.mc.npv_main, bins=36)
        pdf = rep.generate_onepager_pdf(op, c, e)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertEqual(pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page "), 1)

    @unittest.skipUnless(rep.REPORTLAB_OK, "reportlab no instalado")
    def test_pdf_textos_largos_no_rompen(self):
        op, ev = self._op()
        op.project = "P" * 400; op.responsible = "R" * 400; op.integrantes = ", ".join(["Nombre Apellido"] * 40)
        c, e = np.histogram(ev.mc.npv_main, bins=36)
        self.assertTrue(rep.generate_onepager_pdf(op, c, e).startswith(b"%PDF"))

    def test_describe_break(self):
        op, ev = self._op()
        self.assertIn("VAN = 0", rep.describe_break(ev.critical, "PYG"))
        self.assertIn("No se encontró", rep.describe_break(None, "PYG"))


class TestGlosario(unittest.TestCase):
    """Propósito principal de la calculadora: enseñar. Todo concepto lleva su explicación académica."""

    def test_cada_concepto_tiene_las_cuatro_partes(self):
        for k, g in gl.G.items():
            for campo in ("nombre", "que", "formula", "lectura", "base"):
                self.assertTrue(g.get(campo, "").strip(), f"{k}.{campo} vacío")
            self.assertGreaterEqual(len(g["que"]), 40, k)
            self.assertGreaterEqual(len(g["lectura"]), 40, k)

    def test_cubre_cada_componente_de_la_tasa_y_cada_driver(self):
        for k in ("rf", "beta_u", "beta_l", "erp", "crp", "size", "ke_usd", "pi", "ke_flow", "kd", "weights", "wacc", "ire"):
            self.assertIn(k, gl.G)
        for d in ve.DRIVERS:
            self.assertIn(gl.BE_KEYS[d], gl.G)

    def test_formulas_clave_son_las_que_calcula_el_motor(self):
        self.assertIn("(1 + Ke_USD) · (1 + π_flujo) / (1 + π_USD) − 1", gl.G["ke_flow"]["formula"])
        self.assertIn("(1 − T)", gl.G["kd"]["formula"])
        self.assertIn("E/V · Ke + D/V · Kd · (1 − T)", gl.G["wacc"]["formula"])
        self.assertIn("1 + (1 − T) · D/E", gl.G["beta_l"]["formula"])
        self.assertIn("WACC − g∞", gl.G["van_con_vt"]["formula"])

    def test_txt_incluye_el_glosario(self):
        ev = ve.evaluate(proj_demo(), ve.wacc_from_reported(0.10), ve.MCSpec(sims=1000, seed=1))
        op = rep.OnePager(ev=ev, currency="PYG", institution="U", program="P", course="C", project="x", responsible="y",
                          programa="z", integrantes="", report_date="d")
        t = rep.build_onepager_text(op)
        self.assertIn("GLOSARIO", t)
        for k in ("wacc", "ke_flow", "van", "tir"):
            self.assertIn(gl.G[k]["nombre"], t)
            self.assertIn(gl.G[k]["formula"], t)

    def test_celda_html_escapa_y_ayuda_tiene_formato(self):
        self.assertIn("&lt;", gl.celda_html("p_neg"))
        self.assertIn("**Fórmula:**", gl.ayuda("wacc"))

# ═════════════════════════════════════════════════════════════════════════════
# v3.1 — regresiones del testeo adversarial (A1–A10)
class TestAdversarial(unittest.TestCase):
    W = ve.WaccInputs(rf=.045, erp=.055, crp=.02, beta_u=.9, tax=.10, debt=400, equity=600, kd=.11,
                      infl_flow=.035, infl_usd=.025, flow_currency="PYG")

    def _spec(self, **ranges):
        r = dict(ve.MCSpec().ranges)
        r.update(ranges)
        return ve.MCSpec(sims=2000, seed=1, ranges=r)

    def test_A1_rangos_mc_invalidos_se_rechazan(self):
        for bad in ((1.08, 1.0, 0.92),      # mín > máx: antes anulaba la variación en silencio
                    (1.05, 1.0, 1.08),      # mín y máx positivos: antes sorteaba por debajo del mínimo
                    (0.92, 1.0, 0.95),      # mín y máx negativos
                    (-0.5, 1.0, 1.08)):     # multiplicador negativo
            with self.assertRaises(ValueError, msg=bad):
                ve.evaluate(proj_demo(), self.W, self._spec(price=bad))
        with self.assertRaises(ValueError):
            ve.evaluate(proj_demo(), self.W, ve.MCSpec(sims=2000, wacc_range=-0.05))

    def test_A1_sorteos_respetan_el_rango_declarado(self):
        for dist in ("triangular", "normal"):
            d = ve._draw(replace(self._spec(price=(0.80, 1.0, 1.30)), dist=dist))["price"]
            self.assertTrue(np.isfinite(d).all())
            self.assertGreaterEqual(d.min(), 0.80 - 1e-12)
            self.assertLessEqual(d.max(), 1.30 + 1e-12)
            self.assertGreater(d.std(), 0.01)

    def test_A1_driver_fijo_sigue_permitido(self):
        ev = ve.evaluate(proj_demo(), self.W, self._spec(price=(1.0, 1.0, 1.0)))
        self.assertEqual(ev.mc.stats["n"], 2000)

    def test_A2_wacc_no_positivo_se_rechaza(self):
        for w in (replace(self.W, rf=-2.0), replace(self.W, beta_u=-3.0), replace(self.W, kd=-0.5, debt=900, equity=100, rf=-0.1)):
            with self.assertRaises(ValueError, msg=w):
                ve.evaluate(proj_demo(), w)

    def test_A2_entradas_de_tasa_imposibles(self):
        for w in (replace(self.W, infl_usd=-1.0), replace(self.W, tax=1.5), replace(self.W, tax=-0.1),
                  replace(self.W, debt=-1.0), replace(self.W, debt=0.0, equity=0.0)):
            with self.assertRaises(ValueError, msg=w):
                ve.wacc_breakdown(w)

    def test_A3_favorable_con_alerta_alta_pasa_a_reservas(self):
        ev = ve.evaluate(proj_demo(), replace(self.W, convert=False))          # V07 (alta)
        self.assertGreater(ev.metrics.van_main, 0)
        self.assertIn("V07", codes(ev))
        self.assertEqual(ev.reading.status, "reservas")
        self.assertIn("con reservas", ev.reading.headline)
        limpio = ve.evaluate(ve.Project(n_years=5, capex0=500, fcf_direct=[180] * 5), ve.wacc_from_reported(0.10))
        self.assertFalse(any(a.severity == "alta" for a in limpio.alerts))
        self.assertEqual(limpio.reading.status, "favorable")

    def test_A4_comparador_alerta_monedas_distintas(self):
        rows = [dict(name="a", n_years=5, wacc=.13, wacc_key=1, currency="PYG"),
                dict(name="b", n_years=5, wacc=.11, wacc_key=2, currency="USD")]
        self.assertIn("V19", {a.code for a in ve.compare_scenarios(rows)})
        rows[1]["currency"] = "PYG"
        self.assertNotIn("V19", {a.code for a in ve.compare_scenarios(rows)})

    def test_A5_reposicion_no_depende_de_la_vida_contable(self):
        caja = [ve.project_flows(proj_demo(dep_years=L, maint_capex_of_capex=0.10, tax=0.0)).capex_repl[0].sum()
                for L in (3, 8, 20)]
        self.assertAlmostEqual(caja[0], caja[1], places=9)
        self.assertAlmostEqual(caja[1], caja[2], places=9)
        self.assertAlmostEqual(caja[0], 0.10 * 500 * 5, places=9)
        # con IRE = 0 la vida contable no puede mover el VAN (antes lo movía a través de la reposición)
        vans = [ve.evaluate(proj_demo(dep_years=L, maint_capex_of_capex=0.10, tax=0.0), replace(self.W, tax=0.0)).metrics.van_main
                for L in (3, 8, 20)]
        self.assertAlmostEqual(vans[0], vans[2], places=6)

    def test_A5_sin_reposicion_el_ultimo_anio_si_el_proyecto_termina(self):
        p = proj_demo(maint_capex_of_capex=0.10, repl_final_year=False)
        fl = ve.project_flows(p)
        self.assertEqual(fl.capex_repl[0, -1], 0.0)
        self.assertGreater(fl.capex_repl[0, -2], 0.0)
        perp = ve.project_flows(replace(p, terminal_mode="perpetuity", vt_justified=True))
        self.assertGreater(perp.capex_repl[0, -1], 0.0)                         # el negocio continúa: se repone
        self.assertAlmostEqual(fl.repl_steady[0], perp.capex_repl[0, -1], places=9)
        self.assertTrue(ve.project_flows(proj_demo()).capex_repl[0, -1] > 0)    # comportamiento previo por defecto

    def test_A6_desecho_con_perdida_genera_escudo_fiscal(self):
        p = proj_demo(terminal_mode="salvage", salvage_value=100.0, maint_capex_pct=0.0)
        fl = ve.project_flows(p)
        libro = fl.book_end[0]
        self.assertGreater(libro, 100.0)
        self.assertAlmostEqual(fl.salvage_net[0], 100.0 + 0.10 * (libro - 100.0), places=9)

    def test_A7_arrastre_de_perdidas(self):
        base = dict(n_years=5, capex0=500, revenue_y1=1000, var_cost_y1=500, fixed_cost_y1=250, g_revenue=0.0, g_fixed=0.0,
                    tax=.10, dep_years=10, maint_capex_pct=0.0, ramp_years=2, ramp_start=0.2)
        sin = ve.project_flows(ve.Project(**base))
        con = ve.project_flows(ve.Project(**base, loss_carryforward=True, loss_cf_cap=1.0))
        tope = ve.project_flows(ve.Project(**base, loss_carryforward=True, loss_cf_cap=0.20))
        self.assertLess(sin.ebit[0, 0], 0)
        perdida = -np.minimum(sin.ebit[0], 0).sum()
        self.assertAlmostEqual(con.loss_used[0].sum(), perdida, places=9)       # se usa toda, nunca más que la generada
        self.assertAlmostEqual(sin.tax[0].sum() - con.tax[0].sum(), 0.10 * perdida, places=9)
        for t in range(5):                                                      # tope del 20 % de la renta neta
            self.assertLessEqual(tope.loss_used[0, t], 0.20 * max(tope.ebit[0, t], 0.0) + 1e-9)
        self.assertTrue((con.tax[0] >= -1e-12).all())
        self.assertLess(tope.tax[0].sum(), sin.tax[0].sum())

    def test_A7_las_perdidas_vencen(self):
        p = ve.Project(n_years=5, capex0=500, revenue_y1=1000, var_cost_y1=500, fixed_cost_y1=250, g_revenue=0.0, g_fixed=0.0,
                       tax=.10, dep_years=10, maint_capex_pct=0.0, ramp_years=4, ramp_start=0.1,
                       loss_carryforward=True, loss_cf_cap=1.0, loss_cf_years=1)
        fl = ve.project_flows(p)
        primer_positivo = int(np.argmax(fl.ebit[0] > 0))
        self.assertGreater(primer_positivo, 1)
        self.assertLessEqual(fl.loss_used[0, primer_positivo], -min(fl.ebit[0, primer_positivo - 1], 0.0) + 1e-9)

    def test_A8_payback_ultimo_cruce(self):
        self.assertIsNone(ve.payback_period(100, [150, -200, 10, 10]))        # el acumulado termina negativo
        self.assertAlmostEqual(ve.payback_period(100, [150, -100, 100]), 2.5, places=9)       # el primer cruce no cuenta
        self.assertIsNone(ve.payback_period(100, [10, 10, 10]))
        for flows in ([40, 40, 40, 40], [100, 0, 0], [30, 80]):                               # convencional: igual que antes
            self.assertAlmostEqual(ve.payback_period(100, flows), ve.legacy_payback(100, flows), places=12)
            self.assertAlmostEqual(ve.payback_period(100, flows, 0.1) or -1, ve.legacy_payback(100, flows, 0.1) or -1, places=12)

    def test_A9_apalancamiento_extremo(self):
        ev = ve.evaluate(proj_demo(), replace(self.W, debt=950, equity=50))
        self.assertIn("V18", codes(ev))
        self.assertNotIn("V18", codes(ve.evaluate(proj_demo(), self.W)))

    def test_A10_ventas_cero_con_costos_variables(self):
        with self.assertRaises(ValueError):
            ve.project_flows(proj_demo(revenue_y1=0.0))
        ve.project_flows(proj_demo(revenue_y1=0.0, var_cost_y1=0.0))             # sin costos proporcionales: válido

    def test_A_entradas_de_proyecto_incoherentes(self):
        w = ve.wacc_from_reported(0.10)
        with self.assertRaises(ValueError):
            ve.evaluate(ve.Project(n_years=5, capex0=100, fcf_direct=[50, 50, 50]), w)
        with self.assertRaises(ValueError):
            ve.evaluate(ve.Project(n_years=3, capex0=0.0, fcf_direct=[50, 50, 50]), w)

# ═════════════════════════════════════════════════════════════════════════════
# v3.1 — proyectos aleatorios contra un modelo independiente (Python puro, sin numpy ni código del motor)
def _rand_case(i, rnd):
    cur = rnd.choice(["PYG", "PYG", "USD"])
    capex = round(rnd.uniform(0.5e9, 20e9)) if cur == "PYG" else round(rnd.uniform(1e5, 3e6), 2)
    r2 = (lambda x: round(x)) if cur == "PYG" else (lambda x: round(x, 2))
    sales = r2(capex * rnd.uniform(0.5, 2.2))
    cvar = r2(sales * rnd.uniform(0.30, 0.65))
    cfix = r2(sales * rnd.uniform(0.10, 0.28))
    dv = rnd.choice([0.0, rnd.uniform(0.1, 0.7)])
    mode = rnd.choice(["none", "none", "salvage", "perpetuity"])
    ramp_years = rnd.choice([0, 0, 1, 2, 3])
    return dict(
        id=i, cur=cur, capex=capex, sales=sales, cvar=cvar, cfix=cfix,
        ar=r2(sales * rnd.uniform(0.02, 0.12)), inv=r2(sales * rnd.uniform(0.0, 0.08)), ap=r2(sales * rnd.uniform(0.0, 0.08)),
        n=rnd.randint(3, 10), g=round(rnd.uniform(0.0, 9.0), 2), gfix=round(rnd.uniform(2.0, 6.0), 2),
        dep_years=rnd.randint(3, 15), repl=round(rnd.uniform(0.0, 15.0), 1),
        ramp_years=ramp_years, ramp_start=rnd.choice([30, 40, 50, 60, 70, 80]) if ramp_years else 100,
        mode=mode, salvage=r2(capex * rnd.uniform(0.0, 0.5)) if mode == "salvage" else 0.0, ginf=round(rnd.uniform(1.0, 4.0), 1),
        rf=round(rnd.uniform(3.5, 5.0), 2), erp=round(rnd.uniform(4.0, 6.5), 2), crp=round(rnd.uniform(1.5, 3.5), 2),
        size=rnd.choice([0.0, 0.0, round(rnd.uniform(1.0, 3.0), 1)]), beta=round(rnd.uniform(0.6, 1.5), 2), tax=10.0,
        debt=r2(capex * dv), equity=r2(capex * (1 - dv)),
        kd=round(rnd.uniform(8.0, 14.0), 2) if cur == "PYG" else round(rnd.uniform(5.0, 9.0), 2),
        pi_usd=round(rnd.uniform(2.0, 3.0), 1), pi_flow=round(rnd.uniform(3.0, 4.5), 1))


def _rand_to_engine(c):
    pi_flow = c["pi_flow"] / 100 if c["cur"] == "PYG" else c["pi_usd"] / 100
    w = ve.WaccInputs(rf=c["rf"] / 100, erp=c["erp"] / 100, crp=c["crp"] / 100, beta_u=c["beta"], tax=c["tax"] / 100,
                      debt=float(c["debt"]), equity=float(c["equity"]), kd=c["kd"] / 100, size_premium=c["size"] / 100,
                      infl_flow=pi_flow, infl_usd=c["pi_usd"] / 100, flow_currency=c["cur"], convert=True)
    p = ve.Project(n_years=c["n"], capex0=float(c["capex"]), revenue_y1=float(c["sales"]), var_cost_y1=float(c["cvar"]),
                   fixed_cost_y1=float(c["cfix"]), g_revenue=c["g"] / 100, g_fixed=c["gfix"] / 100, tax=c["tax"] / 100,
                   dep_years=c["dep_years"], maint_capex_of_capex=c["repl"] / 100, repl_final_year=False, loss_carryforward=True,
                   infl_capex=pi_flow, nwc_y1=float(c["ar"] + c["inv"] - c["ap"]), recover_nwc=True,
                   salvage_value=float(c["salvage"]), ramp_years=c["ramp_years"], ramp_start=c["ramp_start"] / 100,
                   terminal_mode=c["mode"], g_inf=c["ginf"] / 100, vt_justified=c["mode"] == "perpetuity", name=f"R{c['id']}")
    return p, w


def _rand_indep(c, m=None):
    """m = multiplicadores opcionales {price, volume, unit_vc, fixed, capex, dw}."""
    m = dict(dict(price=1.0, volume=1.0, unit_vc=1.0, fixed=1.0, capex=1.0, dw=0.0), **(m or {}))
    T = c["tax"] / 100
    pi_u = c["pi_usd"] / 100
    pi_f = c["pi_flow"] / 100 if c["cur"] == "PYG" else pi_u
    D, E = float(c["debt"]), float(c["equity"])
    bl = c["beta"] * (1 + (1 - T) * D / E)
    ke_usd = c["rf"] / 100 + bl * c["erp"] / 100 + c["crp"] / 100 + c["size"] / 100
    ke = (1 + ke_usd) * (1 + pi_f) / (1 + pi_u) - 1
    wacc0 = E / (D + E) * ke + D / (D + E) * c["kd"] / 100 * (1 - T)
    w = wacc0 + m["dw"]
    N, L = c["n"], c["dep_years"]
    capex = c["capex"] * m["capex"]
    g, gf = c["g"] / 100, c["gfix"] / 100
    k, s0 = c["ramp_years"], c["ramp_start"] / 100
    nwc_y1 = c["ar"] + c["inv"] - c["ap"]
    rev, ebitda, repl, repl_plan, nwc = [], [], [], [], []
    for t in range(1, N + 1):
        ramp = 1.0 if k == 0 else min(1.0, s0 + (1 - s0) * (t - 1) / k)
        base_rev = c["sales"] * (1 + g) ** (t - 1) * ramp
        r = base_rev * m["price"] * m["volume"]
        vc = c["cvar"] / c["sales"] * base_rev * m["volume"] * m["unit_vc"]
        fx = c["cfix"] * (1 + gf) ** (t - 1) * m["fixed"]
        rev.append(r)
        ebitda.append(r - vc - fx)
        rp = c["repl"] / 100 * capex * (1 + pi_f) ** (t - 1)
        repl_plan.append(rp)
        repl.append(0.0 if (t == N and c["mode"] != "perpetuity") else rp)
        nwc.append(nwc_y1 / c["sales"] * r)
    dep = []
    for t in range(1, N + 1):
        d = capex / L if t <= L else 0.0
        for s in range(1, t):                       # reposicion del anio s se deprecia en s+1 .. s+L
            if t <= s + L:
                d += repl[s - 1] / L
        dep.append(d)
    ebit = [a - b for a, b in zip(ebitda, dep)]
    losses = [max(-e, 0.0) for e in ebit]
    tax, used_all = [], []
    for t in range(N):
        room = 0.20 * max(ebit[t], 0.0)
        used = 0.0
        for o in range(max(0, t - 5), t):
            u = min(losses[o], room)
            losses[o] -= u
            room -= u
            used += u
        used_all.append(used)
        tax.append(T * max(ebit[t] - used, 0.0))
    fcf = []
    for t in range(N):
        dn = nwc[t] - (nwc[t - 1] if t else 0.0)
        fcf.append(ebitda[t] - tax[t] - dn - repl[t])
    book = capex + sum(repl) - sum(dep)
    pv = lambda x, t: x / (1 + w) ** t
    pv_ops = sum(pv(f, t + 1) for t, f in enumerate(fcf))
    van_sin = pv_ops + pv(nwc[-1], N) - capex
    cfs_sin = [-capex] + fcf[:]
    cfs_sin[-1] += nwc[-1]
    if c["mode"] == "salvage":
        salv = c["salvage"] - T * (c["salvage"] - book)
        van = van_sin + pv(salv, N)
    elif c["mode"] == "perpetuity":
        ge = min(c["ginf"] / 100, w - 0.02)
        eb = ebitda[-1] * (1 + ge)
        cn = max(repl_plan[-1], dep[-1]) * (1 + ge)
        nf = eb - T * max(eb - cn, 0.0) - cn - nwc[-1] * ge
        van = pv_ops + pv(nf / (w - ge), N) - capex
    else:
        van = van_sin

    def npv_at(r, cfs):
        return sum(x / (1 + r) ** i for i, x in enumerate(cfs))

    irr = None
    if any(x > 0 for x in cfs_sin) and any(x < 0 for x in cfs_sin):
        lo, hi = -0.99, 50.0
        if npv_at(lo, cfs_sin) * npv_at(hi, cfs_sin) < 0:
            for _ in range(300):
                mid = (lo + hi) / 2
                if npv_at(lo, cfs_sin) * npv_at(mid, cfs_sin) <= 0:
                    hi = mid
                else:
                    lo = mid
            irr = (lo + hi) / 2
    cum, pb, prev = -capex, None, -capex
    for i, f in enumerate(cfs_sin[1:], 1):
        prev, cum = cum, cum + f
        if prev < 0 <= cum:
            pb = i - 1 + (-prev) / f
        elif cum < 0:
            pb = None
    eaa = van * w / (1 - (1 + w) ** -N)
    return dict(wacc=wacc0, ke=ke, beta_l=bl, van=van, van_sin=van_sin, irr=irr, payback=pb, eaa=eaa, fcf=fcf, ebit=ebit,
                tax=tax, dep=dep, used=used_all, book=book, ebitda=ebitda, rev=rev, ir=1 + van_sin / capex)


class TestAleatorios(unittest.TestCase):
    """El motor debe coincidir con una segunda implementación escrita aparte, año por año y fórmula por fórmula."""

    def setUp(self):
        import random
        rnd = random.Random(2026)
        self.cases = [_rand_case(i + 1, rnd) for i in range(10)]

    def test_motor_coincide_con_modelo_independiente(self):
        for c in self.cases:
            p, w = _rand_to_engine(c)
            ev = ve.evaluate(p, w)
            m, I = ev.metrics, _rand_indep(c)
            for nombre, a, b in (("wacc", m.wacc, I["wacc"]), ("van", m.van_main, I["van"]), ("van_sin_vt", m.van_sin_vt, I["van_sin"]),
                                 ("eaa", m.eaa, I["eaa"]), ("ir", m.ir_sin_vt, I["ir"])):
                self.assertLess(abs(a - b), 1e-9 * max(abs(b), 1.0), (c["id"], nombre))
            for a, b in zip(ev.flows.fcf_ops[0], I["fcf"]):
                self.assertLess(abs(a - b), 1e-9 * max(abs(b), 1.0), (c["id"], "fcf"))
            self.assertEqual(m.irr_sin_vt is None, I["irr"] is None, c["id"])
            if I["irr"] is not None:
                self.assertAlmostEqual(m.irr_sin_vt, I["irr"], places=9, msg=c["id"])
            self.assertEqual(m.payback is None, I["payback"] is None, c["id"])
            if I["payback"] is not None:
                self.assertAlmostEqual(m.payback, I["payback"], places=9, msg=c["id"])

    def test_punto_de_equilibrio_anula_el_van_del_modelo_independiente(self):
        for c in self.cases:
            p, w = _rand_to_engine(c)
            ev = ve.evaluate(p, w)
            for b in ev.breakevens:
                if b.rel_change is None:
                    continue
                mult = dict(dw=b.limit_value - ev.metrics.wacc) if b.driver == "wacc" else {b.driver: 1 + b.rel_change}
                self.assertLess(abs(_rand_indep(c, mult)["van"]) / c["capex"], 1e-4, (c["id"], b.driver))

    def test_pesimista_cuartil_queda_dentro_de_la_simulacion(self):
        """El escenario pesimista de la app (cuartil adverso) debe ser un caso plausible: entre el 2 % y el 15 % peor."""
        for c in self.cases:
            p, w = _rand_to_engine(c)
            ev = ve.evaluate(p, w, ve.MCSpec(sims=8000, seed=3, pess_quantile=0.25))
            pct = float((ev.mc.npv_main < ev.pess_van_main).mean())
            self.assertTrue(0.02 < pct < 0.15, (c["id"], pct))
            extremo = ve.evaluate(p, w, ve.MCSpec(sims=8000, seed=3, pess_quantile=0.0))
            self.assertLessEqual(extremo.pess_van_main, ev.mc.npv_main.min())      # los extremos caen fuera de la simulación


class TestCalibracion(unittest.TestCase):
    def test_peso_del_vt_acotado(self):
        p = proj_demo(fixed_cost_y1=480.0)                     # flujos del horizonte negativos, VT de referencia positivo o nulo
        ev = ve.evaluate(p, ve.wacc_from_reported(0.10))
        w = ev.metrics.vt_weight
        self.assertTrue(w != w or 0.0 <= w <= 1.0, w)
        for kw in (dict(), dict(terminal_mode="perpetuity", vt_justified=True), dict(terminal_mode="salvage", salvage_value=300.0)):
            w = ve.evaluate(proj_demo(**kw), ve.wacc_from_reported(0.10)).metrics.vt_weight
            self.assertTrue(0.0 <= w <= 1.0, (kw, w))

    def test_V20_horizonte_mayor_que_la_vida_de_los_activos(self):
        w = ve.wacc_from_reported(0.10)
        corto = proj_demo(n_years=9, dep_years=5, maint_capex_of_capex=0.05)        # repone 5 % y desgasta 20 % por año
        self.assertIn("V20", codes(ve.evaluate(corto, w)))
        self.assertNotIn("V20", codes(ve.evaluate(replace(corto, maint_capex_of_capex=0.20), w)))
        self.assertNotIn("V20", codes(ve.evaluate(replace(corto, n_years=5), w)))
        self.assertNotIn("V20", codes(ve.evaluate(replace(corto, terminal_mode="perpetuity", vt_justified=True), w)))

    def test_V11_explica_el_escenario_segun_como_se_armo(self):
        spec = ve.MCSpec(sims=2000, seed=1, pess_quantile=0.25)
        ev = ve.evaluate(proj_demo(fixed_cost_y1=330.0), ve.wacc_from_reported(0.10), spec)
        self.assertLess(ev.pess_van_main, 0)
        v11 = [a for a in ev.alerts if a.code == "V11"][0]
        self.assertIn("25 % más adverso", v11.detail)
        self.assertIn("25 % más adverso", rep.pess_label(ev))


if __name__ == "__main__":
    unittest.main()

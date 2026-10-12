# fixtures.py — Cinco casos reales procesados por ValuationSuite USIL v2.0 + benchmark TechCare PY.
#
# REGLA: estos datos son la "verdad de la versión actual". NO se modifican.
# Todo lo que NO figura aquí (inflaciones, capital de trabajo, rangos de Monte Carlo, etc.) se declara
# como SUPUESTO en backtest.py y se rotula como tal en el informe.
#
# Convenciones: tasas en decimal (12,80 % → 0.1280); montos en la moneda indicada; paybacks como
# (simple, descontado) tal como los mostró la v2.0 (redondeados a 1 decimal).

F1_FRIOLOG = dict(
    id="F1", name="FrioLog Paraguay (transporte refrigerado)", currency="PYG",
    capex0=921_528_909, fcf1=825_753_784, g=0.05, g_inf=0.02, n_years=5,
    wacc=0.1280, ke=0.1253, kd=0.1450, financing="préstamo + capital propio",
    reported=dict(van=7_454_269_220, irr=1.1635, payback=(1.1, 1.3),
                  mc=dict(sims=10_000, prob_neg=0.0, p5=5_249_000_000)),
)

F2_SMART_RECOVERY = dict(
    id="F2", name="Smart Recovery (suplemento)", currency="PYG",
    capex0=13_434_000,
    fcfs=[9_068_680, 10_428_982, 11_993_329, 13_792_329, 15_861_178], g=0.15, g_inf=0.03, n_years=5,
    wacc=0.1398, ke=0.1303, kd=0.1800, ebit_y1=334_313_200,
    reported=dict(pv_fcf=40_496_748, tv=148_743_916, pv_tv=77_309_486, van=104_372_234, irr=1.0600,
                  payback=(1.4, 1.7),
                  mc=dict(sims=10_000, prob_neg=0.0, p5=42_920_804, p50=95_912_507, p95=429_776_275,
                          cvar5=37_881_736, std=208_705_937)),
    # "Otra corrida del mismo proyecto reportó WACC 11,81 %, VAN 135.541.600 y TIR 110,95 %."
    reported_run2=dict(wacc=0.1181, van=135_541_600, irr=1.1095),
)

F3_PANTALLA_RH = dict(
    id="F3", name="Pantalla icónica RH (pantalla LED publicitaria)", currency="PYG",
    presented_currency="USD", fx_pyg_per_usd=7_000,
    capex0=3_550_000_000, fcf1=476_100_000, g=0.08, g_inf=0.03, n_years=9,
    wacc=0.14529866, ke=0.1453, kd=0.16, ebit_y1=579_000_000,
    reported=dict(  # outputs en USD
        van_usd=252_033.88, irr=0.2217, payback_simple=6.1, vt_pct=0.4369, van_sin_vt_usd=-79_657.64,
        mc=dict(sims=15_000, prob_neg=0.015, p5_usd=29_424.03, p50_usd=145_163.29, p95_usd=287_368.72,
                cvar5_usd=6_061.37)),
)

F4_OVOS_TERRA = dict(
    id="F4", name="Ovos Terra (huevos, 800 ponedoras)", currency="PYG", equity_only=True,
    capex_stage1=50_820_000, capex_stage2_reposicion_plantel=35_390_000,
    ventas=153_600_000, balanceado=82_800_000, fijos=31_200_000, reposicion_costo_anual_equiv=20_728_000,
    rf=0.0493, beta=0.81, erp=0.0423, crp=0.0285, ke=0.1121, wacc=0.1121,
    g_inf=0.02, n_years=5,
    reported=dict(van=101_149_710, irr=0.4729, payback=(3.41, 4.54),
                  mc=dict(sims=15_000, prob_neg=0.0, p5=73_669_241, p95=130_121_212,
                          note="solo crecimiento −3 % a +1,5 %")),
    pessimistic=dict(postura=0.70, balanceado_gs_kg=3_000, fcf_anual=-15_760_000),
    note="NO se reproduce exactamente con la hipótesis de la Fase 1; investigar.",
)

F5_HUMANITAS = dict(
    id="F5", name="Humanitas (venta en consignación)", currency="PYG", capex0=4_536_000,
    scenarios=dict(
        A=dict(compra=0.10, crecimiento=0.20, n_years=5, van=55_611_099, irr=1.2691, wacc=0.1113, payback=(1.2, 1.4)),
        B=dict(compra=0.10, crecimiento=0.10, n_years=5, van=40_228_380, irr=1.1459, wacc=0.1113, payback=(1.3, 1.4)),
        C=dict(compra=0.05, crecimiento=0.20, n_years=8, van=10_089_056, irr=0.3486, wacc=0.1098, payback=(5.1, 6.8)),
        D=dict(compra=0.05, crecimiento=0.10, n_years=8, van=4_552_689, irr=0.2549, wacc=0.1098, payback=(6.0, None)),
    ),
    note="Investigar por qué el WACC cambia con el horizonte.",
)

BENCHMARK_TECHCARE = dict(
    id="BM", name="TechCare PY (modelo manual, no usó la calculadora)",
    ke_usd=0.1134, prima=0.03, ke_total_usd=0.1434, wacc_gs=0.1546, infl_gs=0.035, infl_usd=0.025,
    van=221_000_000, irr=0.423, ir=2.68, van_conservador=-293_000_000,
    estructura="60 períodos mensuales, IVA depurado, IRE solo sobre resultado positivo, capital de trabajo por "
               "déficit máximo + 20 % con recupero, valor de desecho cero, sin perpetuidad.",
)

ALL = [F1_FRIOLOG, F2_SMART_RECOVERY, F3_PANTALLA_RH, F4_OVOS_TERRA, F5_HUMANITAS]

# glosario.py — explicaciones ACADÉMICAS de cada concepto que muestra la calculadora.
# Fuente única para tablas, tooltips y el TXT del one-pager. Propósito: enseñar.
#
# Cada entrada: nombre · qué es · fórmula · cómo leerlo · base teórica.
# Las referencias son a la teoría general de finanzas corporativas; no sustituyen al texto del curso.

from __future__ import annotations

from html import escape
from typing import Dict

G: Dict[str, Dict[str, str]] = {
    # ── Costo del capital: componentes del WACC ─────────────────────────────────────────────────
    "rf": dict(
        nombre="Tasa libre de riesgo (Rf)",
        que="Rendimiento de un activo sin riesgo de incumplimiento, en la misma moneda en que se estima el CAPM "
            "(aquí USD: bono del Tesoro de EE. UU. a largo plazo).",
        formula="Dato de mercado (no se calcula).",
        lectura="Es el piso del costo del capital: un proyecto riesgoso no puede exigir menos. "
                "Si cambia la moneda de referencia, cambia la Rf.",
        base="Modelo CAPM (Sharpe, 1964; Lintner, 1965).",
    ),
    "beta_u": dict(
        nombre="β desapalancada (βU)",
        que="Sensibilidad del negocio a los movimientos del mercado SIN el efecto de la deuda: mide solo el riesgo operativo del sector.",
        formula="βU = βL / [1 + (1 − T) · D/E]",
        lectura="β = 1: riesgo igual al del mercado; β > 1: más riesgoso (cíclico); β < 1: más defensivo. "
                "Se toma de empresas comparables del sector, desapalancadas.",
        base="Hamada (1972); betas sectoriales publicados (p. ej. Damodaran).",
    ),
    "beta_l": dict(
        nombre="β apalancada (βL)",
        que="Beta del capital propio una vez incorporada la estructura de deuda objetivo: a más deuda, más riesgo para el accionista.",
        formula="βL = βU · [1 + (1 − T) · D/E]   (supone beta de la deuda = 0)",
        lectura="βL ≥ βU siempre que haya deuda: a más deuda, mayor riesgo financiero para el accionista. Es la beta que entra al CAPM para calcular el Ke.",
        base="Hamada (1972); Modigliani y Miller (1958, 1963).",
    ),
    "erp": dict(
        nombre="Prima de riesgo de mercado (ERP)",
        que="Rendimiento adicional que exigen los inversores por mantener el mercado accionario en lugar del activo libre de riesgo.",
        formula="ERP = E(Rm) − Rf",
        lectura="Es el precio del riesgo sistemático: se multiplica por β. Usá una estimación prospectiva y citá la fuente; "
                "las estimaciones históricas y las prospectivas difieren.",
        base="CAPM; estimaciones anuales de Damodaran.",
    ),
    "crp": dict(
        nombre="Prima de riesgo país (CRP)",
        que="Compensación adicional por invertir en un país emergente (riesgo soberano, cambiario e institucional) "
            "que un CAPM de mercado maduro no captura.",
        formula="Una metodología habitual: CRP ≈ spread soberano × (volatilidad de acciones / volatilidad de bonos).",
        lectura="Se suma al Ke. No la dupliques ajustando además los flujos por el mismo riesgo.",
        base="Damodaran (riesgo país).",
    ),
    "size": dict(
        nombre="Prima por tamaño",
        que="Rendimiento extra que históricamente exigieron las empresas pequeñas frente a las grandes.",
        formula="Ke = Rf + βL · ERP + CRP + prima por tamaño",
        lectura="Es opcional y discutida en la literatura: aplicala solo si podés justificar que el proyecto es pequeño "
                "y menos líquido que las comparables.",
        base="Banz (1981).",
    ),
    "ke_usd": dict(
        nombre="Costo del capital propio en USD (Ke USD)",
        que="Rendimiento mínimo que exige el accionista por el riesgo del proyecto, expresado en dólares.",
        formula="Ke = Rf + βL · ERP + CRP + prima por tamaño",
        lectura="Es la tasa para descontar flujos del accionista en USD. El capital propio es más riesgoso que la deuda: "
                "se espera Ke > Kd.",
        base="CAPM (Sharpe, 1964).",
    ),
    "pi": dict(
        nombre="Inflación esperada (π Gs / π USD)",
        que="Variación esperada de precios de largo plazo en cada moneda; permite trasladar una tasa de una moneda a otra.",
        formula="Se usa en: Ke_flujo = (1 + Ke_USD) · (1 + π_flujo) / (1 + π_USD) − 1",
        lectura="Si π Gs > π USD, la tasa en guaraníes resulta mayor que en dólares: compensa la pérdida esperada de poder "
                "adquisitivo de la moneda local.",
        base="Efecto Fisher internacional y paridad relativa de poder adquisitivo.",
    ),
    "ke_flow": dict(
        nombre="Ke en la moneda del flujo",
        que="Costo del capital propio expresado en la MISMA moneda de los flujos, para que el numerador y el denominador "
            "del VAN estén en la misma unidad.",
        formula="Ke_flujo = (1 + Ke_USD) · (1 + π_flujo) / (1 + π_USD) − 1",
        lectura="Evita descontar flujos en guaraníes con una tasa en dólares, que subestima el costo de capital y "
                "sobrevalúa el VAN.",
        base="Efecto Fisher internacional; paridad relativa de poder adquisitivo.",
    ),
    "kd": dict(
        nombre="Costo de la deuda (Kd) antes y después de IRE",
        que="Tasa que paga el proyecto por su deuda. Los intereses son deducibles de impuestos, lo que genera un ahorro fiscal "
            "(escudo fiscal).",
        formula="Kd después de IRE = Kd · (1 − T)",
        lectura="Usá el rendimiento de mercado actual de deuda comparable (no la tasa cupón histórica), en la moneda del flujo.",
        base="Modigliani y Miller (1963): valor del escudo fiscal de la deuda.",
    ),
    "weights": dict(
        nombre="Pesos E/V y D/V",
        que="Proporción de capital propio (E) y de deuda (D) en la estructura de capital OBJETIVO, a valores de mercado.",
        formula="E/V = E / (D + E)   ;   D/V = D / (D + E)",
        lectura="Ponderan el Ke y el Kd. Corresponden a la estructura de largo plazo, no a la financiación puntual de este proyecto.",
        base="Teoría de la estructura de capital.",
    ),
    "wacc": dict(
        nombre="WACC (costo promedio ponderado del capital)",
        que="Tasa de descuento de los flujos libres del proyecto: el rendimiento mínimo que debe generar para remunerar a "
            "accionistas y acreedores.",
        formula="WACC = E/V · Ke + D/V · Kd · (1 − T)",
        lectura="Si TIR > WACC, el proyecto crea valor. Debe estar en la moneda del flujo y reflejar el riesgo del PROYECTO, "
                "no el de la empresa que lo ejecuta.",
        base="Modigliani y Miller; textos de finanzas corporativas (p. ej. Brealey, Myers y Allen).",
    ),
    "ire": dict(
        nombre="IRE (impuesto a la renta empresarial)",
        que="Impuesto sobre la utilidad operativa. En Paraguay la tasa general es 10 %.",
        formula="IRE = T · máx(EBIT, 0)",
        lectura="Solo se paga cuando el EBIT es positivo. Este modelo no arrastra pérdidas fiscales de un año a otro.",
        base="Legislación tributaria vigente; verificá la tasa aplicable a tu caso.",
    ),
    # ── Indicadores de decisión ─────────────────────────────────────────────────────────────────
    "van": dict(
        nombre="VAN (valor actual neto)",
        que="Valor, en moneda de hoy, de la riqueza que el proyecto crea o destruye: flujos futuros descontados al WACC "
            "menos la inversión inicial.",
        formula="VAN = Σ FCF_t / (1 + WACC)^t  +  valor de cierre / (1 + WACC)^N  −  CAPEX₀",
        lectura="VAN > 0: crea valor. VAN < 0: lo destruye. VAN = 0: rinde exactamente el costo de capital. "
                "Es el criterio principal porque es aditivo y mide valor absoluto.",
        base="Regla del VAN (presupuesto de capital).",
    ),
    "van_sin_vt": dict(
        nombre="VAN sin valor terminal",
        que="VAN considerando solo los flujos del horizonte explícito (y el recupero del capital de trabajo).",
        formula="VAN = Σ FCF_t / (1 + WACC)^t  +  CT_N / (1 + WACC)^N  −  CAPEX₀",
        lectura="No depende de supuestos más allá del horizonte: es la medida más conservadora y la adecuada para activos de vida finita.",
        base="Presupuesto de capital con vida finita.",
    ),
    "van_con_vt": dict(
        nombre="VAN con valor terminal (VT)",
        que="Agrega el valor de todo lo que ocurriría después del último año proyectado, como una perpetuidad creciente.",
        formula="VT = FCF_(N+1) / (WACC − g∞)   (Gordon–Shapiro), con FCF_(N+1) normalizado: reinversión ≥ depreciación",
        lectura="Solo corresponde si el negocio continúa indefinidamente. Es muy sensible a g∞ y al WACC.",
        base="Modelo de crecimiento constante de Gordon–Shapiro.",
    ),
    "vt_weight": dict(
        nombre="Peso del valor terminal",
        que="Porción del valor presente que proviene del valor terminal y no de los flujos del horizonte.",
        formula="Peso = PV(VT) / [ PV(FCF 1..N) + PV(VT) ]",
        lectura="Más de 50 % significa que el resultado depende de lo que ocurra después del horizonte: conviene mostrar siempre el VAN sin VT.",
        base="Buenas prácticas de valoración.",
    ),
    "tir": dict(
        nombre="TIR (tasa interna de retorno) sin VT",
        que="Tasa de descuento que hace el VAN igual a cero: rendimiento anual implícito de los flujos del horizonte.",
        formula="0 = −CAPEX₀ + Σ FCF_t / (1 + TIR)^t",
        lectura="Si TIR > WACC conviene; si TIR < WACC no. Límites: puede haber varias TIR si los flujos cambian de signo, "
                "supone reinversión a la propia TIR y no mide escala. Ante conflicto con el VAN, prevalece el VAN.",
        base="Presupuesto de capital: comparación VAN vs. TIR.",
    ),
    "tir_vt": dict(
        nombre="TIR con VT (secundaria)",
        que="TIR que incluye el valor terminal como si fuera caja del último año; mezcla el rendimiento del horizonte con el de la perpetuidad.",
        formula="0 = −CAPEX₀ + Σ FCF_t / (1 + TIR)^t, con VT sumado al flujo del año N",
        lectura="Tiende a inflarse porque el VT puede pesar más de la mitad del valor: usala solo como referencia.",
        base="Presupuesto de capital.",
    ),
    "tirm": dict(
        nombre="TIR modificada (TIRM)",
        que="TIR que supone reinvertir los flujos y financiar los egresos a una tasa realista (el WACC), no a la propia TIR.",
        formula="TIRM = ( VF de flujos positivos al WACC / VP de flujos negativos al WACC )^(1/N) − 1",
        lectura="Es única y menos optimista que la TIR; se compara con el WACC igual que la TIR.",
        base="Presupuesto de capital: corrección de los supuestos de reinversión.",
    ),
    "ir": dict(
        nombre="Índice de rentabilidad (IR)",
        que="Valor presente de los flujos futuros por cada unidad de moneda invertida: cuánto valor se obtiene por cada guaraní o dólar de inversión.",
        formula="IR = VP(flujos futuros) / CAPEX₀ = 1 + VAN / CAPEX₀",
        lectura="IR > 1 equivale a VAN > 0. Sirve para ordenar proyectos cuando el capital es limitado (racionamiento de capital).",
        base="Presupuesto de capital.",
    ),
    "payback": dict(
        nombre="Payback simple",
        que="Tiempo que tarda el flujo acumulado, sin descontar, en igualar la inversión inicial (con interpolación dentro del año).",
        formula="Payback = año anterior + (inversión pendiente / flujo del año de recupero)",
        lectura="Mide rapidez de recupero (liquidez y riesgo), no rentabilidad: ignora el valor del dinero en el tiempo y los flujos posteriores. Es secundario.",
        base="Presupuesto de capital: limitaciones del payback.",
    ),
    "payback_disc": dict(
        nombre="Payback descontado",
        que="Igual que el payback simple, pero descontando cada flujo al WACC antes de acumularlo.",
        formula="Año en que Σ FCF_t / (1 + WACC)^t ≥ CAPEX₀",
        lectura="Corrige el valor del dinero en el tiempo, pero sigue ignorando lo que ocurre después de recuperar la inversión.",
        base="Presupuesto de capital.",
    ),
    "eaa": dict(
        nombre="Valor anual equivalente (EAA)",
        que="VAN convertido en una anualidad equivalente durante la vida del proyecto: cuánto valor crea el proyecto por año.",
        formula="EAA = VAN · WACC / [ 1 − (1 + WACC)^(−N) ]",
        lectura="Permite comparar proyectos mutuamente excluyentes con vidas distintas: el de mayor EAA crea más valor por año.",
        base="Método de la anualidad equivalente (proyectos con vidas desiguales).",
    ),
    # ── Riesgo: Monte Carlo ─────────────────────────────────────────────────────────────────────
    "p_neg": dict(
        nombre="P(VAN < 0)",
        que="Proporción de las simulaciones en que el proyecto destruye valor, es decir, en que el VAN resulta negativo.",
        formula="P(VAN<0) = (simulaciones con VAN < 0) / (total de simulaciones)",
        lectura="Es una estimación condicionada a las distribuciones elegidas, no una probabilidad real. No reemplaza al escenario pesimista.",
        base="Simulación de Monte Carlo aplicada a presupuesto de capital.",
    ),
    "p50": dict(
        nombre="Mediana del VAN (P50)",
        que="Valor del VAN que deja la mitad de los escenarios por encima y la mitad por debajo.",
        formula="Percentil 50 de la distribución simulada",
        lectura="Si el caso base está lejos de la mediana, los rangos de los drivers son asimétricos.",
        base="Estadística descriptiva.",
    ),
    "p5": dict(
        nombre="Percentiles P5 y P95",
        que="Valores del VAN por debajo de los cuales cae el 5 % (P5, adverso plausible) y el 95 % (P95, favorable) de los escenarios.",
        formula="Percentiles 5 y 95 de la distribución simulada",
        lectura="El tramo P5–P95 muestra el rango razonable de resultados, no el peor ni el mejor caso posible.",
        base="Estadística descriptiva.",
    ),
    "cvar5": dict(
        nombre="CVaR al 5 % (déficit esperado)",
        que="VAN promedio en el 5 % de los peores escenarios simulados (también llamado déficit esperado): mide la severidad de la cola de pérdidas.",
        formula="CVaR5 = promedio de los VAN ≤ P5",
        lectura="Complementa al P5: el P5 dice dónde empieza el tramo malo y el CVaR5 qué tan malo es en promedio. Comparalo con el CAPEX para dimensionar la pérdida posible.",
        base="Medidas de riesgo de cola (expected shortfall).",
    ),
    "van_pess": dict(
        nombre="VAN del escenario pesimista",
        que="VAN con todos los drivers (precio, volumen, costos, CAPEX, WACC) en su lado adverso a la vez.",
        formula="Mismo cálculo del VAN con los valores adversos de cada driver",
        lectura="Si es negativo, el proyecto no resiste una combinación adversa aunque la simulación muestre baja probabilidad de pérdida.",
        base="Análisis de escenarios.",
    ),
    "base_pct": dict(
        nombre="Posición del caso base en la distribución",
        que="Porcentaje de las simulaciones cuyo VAN es menor que el del caso base: indica en qué punto de la distribución cae el caso base.",
        formula="Percentil del VAN base dentro de la distribución simulada",
        lectura="Cerca de 50 %: caso base centrado. Muy alto: el caso base es optimista frente a los rangos.",
        base="Estadística descriptiva.",
    ),
    # ── Puente EBITDA → FCF ─────────────────────────────────────────────────────────────────────
    "ingresos": dict(
        nombre="Ingresos",
        que="Ventas del año: precio por volumen vendido. Es el punto de partida del flujo y el principal impulsor del valor del proyecto.",
        formula="Ingresos_t = Ingresos_1 · (1 + g)^(t−1) · factor de rampa_t",
        lectura="g es nominal: debe ser coherente con la inflación de la moneda del flujo, porque la tasa de descuento también lo es.",
        base="Proyección de flujos incrementales.",
    ),
    "costos_var": dict(
        nombre="Costos variables",
        que="Costos que cambian con el volumen: materia prima, comisiones, transporte.",
        formula="Costos variables_t = % de los ingresos a precios base × volumen",
        lectura="Ingresos − costos variables es el margen de contribución: lo que cada venta aporta a cubrir los fijos.",
        base="Contabilidad de costos.",
    ),
    "costos_fijos": dict(
        nombre="Costos fijos",
        que="Costos que no cambian con el volumen de ventas dentro del rango relevante: alquileres, sueldos administrativos, seguros.",
        formula="Costos fijos_t = Costos fijos_1 · (1 + g costos fijos)^(t−1)",
        lectura="Generan apalancamiento operativo: una caída de las ventas reduce el EBITDA más que proporcionalmente.",
        base="Apalancamiento operativo.",
    ),
    "ebitda": dict(
        nombre="EBITDA",
        que="Utilidad operativa antes de depreciación, intereses e impuestos (en inglés: earnings before interest, taxes, depreciation and amortization).",
        formula="EBITDA = Ingresos − Costos variables − Costos fijos",
        lectura="Aproxima la caja que genera la operación antes de impuestos e inversiones; sirve para comparar la rentabilidad operativa entre proyectos de distinta intensidad de capital.",
        base="Estado de resultados.",
    ),
    "dep": dict(
        nombre="Depreciación",
        que="Distribución contable del costo de los activos a lo largo de su vida útil (línea recta). No es una salida de caja.",
        formula="Depreciación = CAPEX / vida contable",
        lectura="Reduce la utilidad y por lo tanto el IRE (escudo fiscal), pero se suma de vuelta al calcular el flujo de caja.",
        base="Contabilidad; escudo fiscal de la depreciación.",
    ),
    "ebit": dict(
        nombre="EBIT (utilidad operativa)",
        que="Resultado operativo después de depreciación; es la base sobre la que se calcula el impuesto.",
        formula="EBIT = EBITDA − Depreciación",
        lectura="Si es negativo no hay IRE a pagar ese año (este modelo no genera crédito fiscal por pérdidas).",
        base="Estado de resultados.",
    ),
    "ire_row": dict(
        nombre="IRE del año",
        que="Impuesto a la renta empresarial que paga el proyecto sobre su utilidad operativa.",
        formula="IRE = T · máx(EBIT, 0)",
        lectura="Se calcula sobre el EBIT, sin intereses: el beneficio fiscal de la deuda ya está en el Kd después de impuestos del WACC.",
        base="FCFF: flujos al proyecto antes de costos financieros.",
    ),
    "dep_back": dict(
        nombre="+ Depreciación",
        que="Se suma de vuelta porque redujo la utilidad (y el impuesto) pero no fue una salida de caja: solo queda el ahorro fiscal.",
        formula="FCF = EBIT · (1 − T) + Depreciación − …",
        lectura="Si no se sumara, se subestimaría el flujo de caja: la depreciación reduce la utilidad contable y el impuesto, pero no es una salida de dinero.",
        base="Construcción del flujo de caja libre.",
    ),
    "dnwc": dict(
        nombre="Δ capital de trabajo",
        que="Dinero inmovilizado en la operación: cuentas por cobrar + inventarios − cuentas por pagar. Su aumento resta caja.",
        formula="CT = AR + INV − AP ;   ΔCT_t = CT_t − CT_(t−1)",
        lectura="Crece con las ventas; se recupera al cierre si el proyecto termina (no si continúa en perpetuidad).",
        base="Gestión del capital de trabajo en presupuesto de capital.",
    ),
    "capex_repl": dict(
        nombre="CAPEX de reposición",
        que="Inversión anual necesaria para reponer los activos que se desgastan y mantener la capacidad productiva del negocio.",
        formula="Reposición = % × depreciación de la base inicial, indexada por la inflación",
        lectura="En perpetuidad debe ser al menos igual a la depreciación: ningún negocio dura para siempre sin reponer sus activos.",
        base="Valor terminal con reinversión (FCF normalizado).",
    ),
    "fcf": dict(
        nombre="Flujo de caja libre (FCF / FCFF)",
        que="Caja disponible para accionistas y acreedores después de impuestos, inversiones y capital de trabajo, y antes de intereses.",
        formula="FCF = EBIT · (1 − T) + Depreciación − CAPEX − ΔCT = EBITDA − IRE − ΔCT − CAPEX",
        lectura="Como excluye los costos financieros, se descuenta al WACC. No incluye costos hundidos y sí los costos de oportunidad.",
        base="Flujos incrementales (FCFF).",
    ),
    # ── Punto de equilibrio ─────────────────────────────────────────────────────────────────────
    "be_price": dict(
        nombre="Precio (ingresos Año 1)",
        que="Ingresos mínimos del Año 1, por menor precio, con los que el VAN llega a cero manteniendo lo demás constante.",
        formula="Se busca el factor de precio m tal que VAN(m) = 0",
        lectura="La distancia entre el valor actual y el límite es el margen de seguridad en precio.",
        base="Análisis de sensibilidad y punto de equilibrio financiero (VAN = 0).",
    ),
    "be_volume": dict(
        nombre="Volumen / ocupación",
        que="Nivel de volumen (como % del caso base) con el que el VAN llega a cero. Afecta ingresos y costos variables.",
        formula="Se busca el factor de volumen m tal que VAN(m) = 0",
        lectura="Cuanto más cerca de 100 %, más frágil es el proyecto frente a una demanda menor.",
        base="Análisis de sensibilidad.",
    ),
    "be_unit_vc": dict(
        nombre="Costo variable (Año 1)",
        que="Costo variable máximo tolerable antes de que el proyecto deje de crear valor.",
        formula="Se busca el factor de costo m tal que VAN(m) = 0",
        lectura="Mide cuánto puede subir el costo unitario (insumos, comisiones) sin destruir valor.",
        base="Análisis de sensibilidad.",
    ),
    "be_fixed": dict(
        nombre="Costos fijos (Año 1)",
        que="Nivel máximo de costos fijos del Año 1 que el proyecto tolera antes de que el VAN llegue a cero, manteniendo lo demás constante.",
        formula="Se busca el factor de costos fijos m tal que VAN(m) = 0",
        lectura="Un límite muy cercano al valor actual indica alto apalancamiento operativo: pequeños aumentos de costos fijos destruyen el valor.",
        base="Análisis de sensibilidad.",
    ),
    "be_capex": dict(
        nombre="CAPEX inicial",
        que="Inversión inicial máxima que soporta el proyecto con VAN = 0 (sobrecosto máximo tolerable).",
        formula="Se busca el factor m tal que VAN(m) = 0. En el modelo, al cambiar el CAPEX también cambian la depreciación y la reposición.",
        lectura="Dato clave para controlar el presupuesto de obra: indica cuánto sobrecosto de inversión soporta el proyecto antes de dejar de crear valor.",
        base="Análisis de sensibilidad.",
    ),
    "be_wacc": dict(
        nombre="WACC",
        que="WACC máximo con el que el proyecto todavía no destruye valor: el costo de capital de equilibrio.",
        formula="WACC* tal que VAN(WACC*) = 0  ⇒  WACC* = TIR de los flujos que componen el VAN de decisión",
        lectura="Coincide con la TIR de los flujos considerados: por definición, la TIR es la tasa que anula el VAN.",
        base="Definición de TIR.",
    ),
}

BE_KEYS = {"price": "be_price", "volume": "be_volume", "unit_vc": "be_unit_vc", "fixed": "be_fixed",
           "capex": "be_capex", "wacc": "be_wacc"}


def get(key: str) -> Dict[str, str]:
    return G[key]


def ayuda(key: str) -> str:
    """Texto para tooltips (Markdown): qué es, fórmula, cómo leerlo y base teórica."""
    g = G[key]
    return (f"**{g['nombre']}**\n\n**Qué es:** {g['que']}\n\n**Fórmula:** `{g['formula']}`\n\n"
            f"**Cómo leerlo:** {g['lectura']}\n\n*Base teórica: {g['base']}*")


def celda_html(key: str) -> str:
    """Explicación para celdas de tabla HTML (texto escapado)."""
    g = G[key]
    return (f"<b>Qué es:</b> {escape(g['que'])}<br><b>Fórmula:</b> <code>{escape(g['formula'])}</code><br>"
            f"<b>Cómo leerlo:</b> {escape(g['lectura'])}<br><i>Base teórica: {escape(g['base'])}</i>")


def texto_plano(key: str) -> str:
    g = G[key]
    return f"{g['nombre']}: {g['que']} Fórmula: {g['formula']}. Cómo leerlo: {g['lectura']} (Base: {g['base']})"

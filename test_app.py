# test_app.py — pruebas de humo de la interfaz (Streamlit AppTest, sin navegador).
# Ejecutar: python -m unittest test_app -v
import os
import unittest

from streamlit.testing.v1 import AppTest

HERE = os.path.dirname(os.path.abspath(__file__))


def new_app() -> AppTest:
    return AppTest.from_file(os.path.join(HERE, "app.py"), default_timeout=90).run()


def find(elements, label_start: str):
    for e in elements:
        if str(e.label).startswith(label_start):
            return e
    raise KeyError(label_start)


def texts(at) -> str:
    out = []
    for coll in (at.markdown, at.error, at.warning, at.info, at.success, at.caption):
        out += [str(x.value) for x in coll]
    for m in at.metric:
        out.append(f"{m.label} {m.value}")
    return "\n".join(out)


class TestApp(unittest.TestCase):
    def test_corrida_por_defecto_sin_excepciones(self):
        at = new_app()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        t = texts(at)
        self.assertIn("Indicadores", t)                   # lectura nueva (no 'DICTAMEN: APROBADO')
        self.assertNotIn("APROBADO", t)
        self.assertIn("Variable crítica", t)
        labels = [m.label for m in at.metric]
        self.assertTrue(any(l.startswith("VAN sin VT") for l in labels))
        self.assertTrue(any(l.startswith("TIR sin VT") for l in labels))
        self.assertTrue(any("TIR modificada" in l for l in labels))

    def test_usd(self):
        at = new_app()
        find(at.sidebar.selectbox, "💱").set_value("USD 🇺🇸  Dólar Estadounidense").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])

    def test_modo_compatibilidad(self):
        at = new_app()
        find(at.sidebar.toggle, "Modo compatibilidad").set_value(True).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("MODO COMPATIBILIDAD", texts(at))

    def test_perpetuidad_sin_justificar_no_se_usa(self):
        at = new_app()
        find(at.sidebar.selectbox, "Tratamiento").set_value("Perpetuidad (requiere justificación)").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("V09", texts(at))                   # alerta de perpetuidad no habilitada
        vt = [m for m in at.metric if m.label.startswith("VAN —")][0]
        self.assertIn("sin valor terminal", vt.label)

    def test_perpetuidad_justificada(self):
        at = new_app()
        find(at.sidebar.selectbox, "Tratamiento").set_value("Perpetuidad (requiere justificación)").run()
        find(at.sidebar.checkbox, "Justifico").set_value(True).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertTrue(any("con perpetuidad" in m.label for m in at.metric))

    def test_desecho_rampa_normal_y_correlaciones(self):
        at = new_app()
        find(at.sidebar.selectbox, "Tratamiento").set_value("Valor de desecho").run()
        find(at.sidebar.number_input, "Años de rampa").set_value(2).run()
        find(at.sidebar.selectbox, "Distribución").set_value("Normal truncada").run()
        find(at.sidebar.slider, "Correlación precio").set_value(-0.5).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])

    def test_ke_sin_convertir_dispara_v07(self):
        at = new_app()
        find(at.sidebar.checkbox, "Convertir Ke").set_value(False).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertIn("V07", texts(at))


class TestAyudas(unittest.TestCase):
    """Todo campo y todo indicador debe tener su explicación (tooltip de ayuda)."""

    KINDS = ("number_input", "text_input", "text_area", "selectbox", "slider", "checkbox", "toggle", "button")

    def _faltan(self, at):
        faltan = []
        for kind in self.KINDS:
            for coll in (getattr(at.sidebar, kind, []), getattr(at.main, kind, [])):
                faltan += [f"{kind}: {e.label}" for e in coll if not getattr(e, "help", None)]
        faltan += [f"metric: {m.label}" for m in at.metric if not getattr(m, "help", None)]
        return faltan

    def test_todos_los_campos_tienen_ayuda_en_todos_los_modos(self):
        casos = {
            "base": lambda at: at,
            "compat": lambda at: find(at.sidebar.toggle, "Modo compatibilidad").set_value(True).run(),
            "perpetuidad": lambda at: find(at.sidebar.selectbox, "Tratamiento").set_value("Perpetuidad (requiere justificación)").run(),
            "desecho": lambda at: find(at.sidebar.selectbox, "Tratamiento").set_value("Valor de desecho").run(),
            "usd": lambda at: find(at.sidebar.selectbox, "💱").set_value("USD 🇺🇸  Dólar Estadounidense").run(),
        }
        for nombre, prep in casos.items():
            at = new_app()
            prep(at)
            self.assertEqual(self._faltan(at), [], nombre)

    def test_inflaciones_explican_la_formula_de_conversion(self):
        at = new_app()
        for lab in ("π USD", "π Gs"):
            h = find(at.sidebar.number_input, lab).help
            self.assertIn("inflación", h.lower(), lab)
            self.assertIn("Ke", h, lab)


class TestExplicacionAcademica(unittest.TestCase):
    """Cada tabla de resultados debe mostrar, por fila, qué es / fórmula / cómo leerlo / base teórica."""

    def _html(self, at):
        return "\n".join(str(x.value) for x in at.markdown)

    def test_tabla_de_la_tasa_explica_cada_componente(self):
        import glosario as gl
        from html import escape
        h = self._html(new_app())
        for k in ("rf", "beta_u", "beta_l", "erp", "crp", "size", "ke_usd", "pi", "ke_flow", "kd", "weights", "wacc"):
            self.assertIn(escape(gl.G[k]["formula"]), h, k)
            self.assertIn(escape(gl.G[k]["base"]), h, k)
        self.assertIn("Qué es, cómo se calcula y cómo leerlo", h)

    def test_tabla_de_equilibrio_y_puente_explican_cada_fila(self):
        import glosario as gl
        from html import escape
        h = self._html(new_app())
        for k in ("be_price", "be_volume", "be_unit_vc", "be_fixed", "be_capex", "be_wacc", "ebitda", "ebit", "ire_row", "dnwc", "fcf"):
            self.assertIn(escape(gl.G[k]["formula"]), h, k)

    def test_glosario_completo_dentro_de_la_app(self):
        import glosario as gl
        from html import escape
        h = self._html(new_app())
        for k, g in gl.G.items():
            self.assertIn(escape(g["nombre"]), h, k)

    def test_los_indicadores_traen_la_teoria_en_el_tooltip(self):
        at = new_app()
        van = [m for m in at.metric if m.label.startswith("VAN —")][0]
        for frag in ("Qué es", "Fórmula", "Base teórica"):
            self.assertIn(frag, van.help)
        for m in at.metric:
            self.assertIn("Fórmula", m.help, m.label)

    def test_los_campos_conceptuales_traen_la_teoria(self):
        at = new_app()
        for lab in ("Rf (%)", "ERP (%)", "CRP (%)", "βU", "π USD", "π Gs", "Kd (%)", "IRE (%)"):
            h = find(at.sidebar.number_input, lab).help
            self.assertIn("Base teórica", h, lab)
            self.assertIn("Fórmula", h, lab)


if __name__ == "__main__":
    unittest.main()

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


if __name__ == "__main__":
    unittest.main()

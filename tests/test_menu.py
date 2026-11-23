from trafico.menu import Menu


def _menu(respuestas, ejecutar=False):
    it = iter(respuestas)
    salida = []
    m = Menu(entrada=lambda _p: next(it), salida=salida.append, ejecutar=ejecutar)
    m.run()
    return m, "\n".join(salida)


def test_corrida_con_valores_por_defecto():
    # 1 corrida; modo 1 (flujo); Enter en todo; no hacer otra cosa
    m, out = _menu(["1", "1", "", "", "", "", "", "", "results/x", "n"])
    assert m.ultimo[:3] == ["corrida", "--modo", "flujo"]
    assert "--flujo" in m.ultimo and "--vel-sonda" in m.ultimo
    assert "trafico corrida" in out


def test_animacion_carretera_llena():
    m, _ = _menu(["2", "2", "50", "10", "1", "130", "3", "7", "n", "n"])
    assert m.ultimo[0] == "animar"
    i = m.ultimo.index("--vehiculos")
    assert m.ultimo[i + 1] == "50"
    assert m.ultimo[m.ultimo.index("--longitud") + 1] == "10000"
    assert m.ultimo[m.ultimo.index("--semilla") + 1] == "7"


def test_campana_con_dos_barridos_y_valor_invalido():
    m, out = _menu([
        "3", "1", "abc", "200", "20", "1",  # tráfico (con un valor inválido que se repite), recta
        "2", "100,300",  # barrer flujo
        "3", "5000, 10000",  # barrer longitud
        "0", "120 130", "4", "3", "2", "results/c", "n", "n",
    ])
    assert "Valor no válido" in out
    assert m.ultimo.count("--barrer") == 2
    assert "flujo=100,300" in m.ultimo and "longitud=5000,10000" in m.ultimo
    assert m.ultimo[m.ultimo.index("--velocidades") + 1:m.ultimo.index("--velocidades") + 3] == ["120", "130"]


def test_menu_ejecuta_la_corrida(tmp_path):
    m, out = _menu(["1", "1", "150", "3", "1", "130", "1", "2", str(tmp_path / "r"), "n"], ejecutar=True)
    assert (tmp_path / "r" / "viajes.csv").exists()
    assert (tmp_path / "r" / "resumen.json").exists()


def test_salir():
    m, _ = _menu(["0"])
    assert m.ultimo is None


def test_corrida_con_muchas_curvas_y_trazado_fijo():
    m, _ = _menu(["1", "1", "200", "10", "3", "5", "130", "2", "1", "results/x", "n"])
    assert m.ultimo[m.ultimo.index("--trazado") + 1] == "muchas"
    assert m.ultimo[m.ultimo.index("--semilla-trazado") + 1] == "5"


def test_campana_barre_trazado():
    m, _ = _menu(["3", "1", "200", "20", "1", "1", "recta,muchas", "0", "120 130", "4", "2", "1",
                  "results/c", "n", "n"])
    assert "trazado=recta,muchas" in m.ultimo

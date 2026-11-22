from trafico.plots import plot_delay_vs_flow, plot_gain_vs_flow, plot_time_vs_speed


def test_las_graficas_se_generan(tmp_path):
    flows = [100, 200, 300]
    plot_delay_vs_flow(flows, {120: ([5, 20, 40], [1, 2, 3]), 130: ([8, 30, 60], [1, 2, 3])}, str(tmp_path / "a.png"))
    plot_gain_vs_flow(flows, [40, 30, 20], [2, 2, 2], 46.2, str(tmp_path / "b.png"), 120, 130)
    plot_time_vs_speed([100, 120, 140], [700, 600, 520], [5, 5, 5], [720, 600, 514], str(tmp_path / "c.png"), 200)
    for n in "abc":
        assert (tmp_path / f"{n}.png").stat().st_size > 5_000

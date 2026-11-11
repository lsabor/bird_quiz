import datetime as dt

from scraper.barchart import parse_barchart, week_index, week_window

SAMPLE = (
    "Frequency of observations in the selected location(s).:\n"
    "Number of taxa: 2\n\n"
    "\tJan\t\t\t\n"
    "Sample Size:\t" + "\t".join(["10.0"] * 48) + "\n"
    'Black-winged Stilt (<em class="sci">Himantopus himantopus</em>)\t' + "\t".join(["0.5"] * 48) + "\t\n"
    "Common Bulbul (Pycnonotus barbatus)\t" + "\t".join(["0.0"] * 47 + ["1.0"]) + "\n"
)


def test_week_index():
    assert week_index(dt.date(2026, 1, 1)) == 0
    assert week_index(dt.date(2026, 11, 20)) == 42  # Nov week 3
    assert week_index(dt.date(2026, 12, 31)) == 47
    assert week_window(dt.date(2026, 12, 31), 1) == [46, 47, 0]


def test_parse():
    bc = parse_barchart(SAMPLE)
    assert len(bc.rows) == 2
    assert bc.rows[0].scientific_name == "Himantopus himantopus"
    assert bc.rows[0].common_name == "Black-winged Stilt"
    n, freqs = bc.window_stats([46, 47])
    assert n == 20
    assert freqs["Pycnonotus barbatus"] == 0.5

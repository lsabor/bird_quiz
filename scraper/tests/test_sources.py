from scraper.sources import _group_name, _same_species, _xc_license, _xc_seconds


def test_group_name():
    assert _group_name("Western Cattle-Egret") == _group_name("Western Cattle Egret") == "egret"
    assert _group_name("Reed Bunting") == _group_name("Common Reed Bunting")
    assert _group_name("Chimpanzee") != _group_name("Eurasian Wren")


def test_helpers():
    assert _same_species("Himantopus himantopus himantopus", "Himantopus himantopus")
    assert not _same_species("Himantopus mexicanus", "Himantopus himantopus")
    assert _xc_seconds("1:05") == 65 and _xc_seconds("0:30") == 30
    assert _xc_license("//creativecommons.org/licenses/by-nc-sa/4.0/") == "cc-by-nc-sa"

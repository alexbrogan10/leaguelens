from leaguelens.ids import IdLinker, normalize_name, pfr_to_gsis

NFLVERSE = [
    {"gsis_id": "G1", "display_name": "Kenneth Walker III", "position": "RB", "espn_id": "1"},
    {
        "gsis_id": "G2",
        "display_name": "D.J. Moore",
        "position": "WR",
        "espn_id": "",
        "pfr_id": "P2",
    },
    {"gsis_id": "G3", "display_name": "Mike Williams", "position": "WR", "espn_id": ""},
    {"gsis_id": "G4", "display_name": "Mike Williams", "position": "WR", "espn_id": ""},
    {"gsis_id": "G5", "display_name": "Old Guy", "position": "QB", "status": "RET"},
]


def test_normalize_name():
    assert normalize_name("Kenneth Walker III") == "kennethwalker"
    assert normalize_name("D.J. Moore") == normalize_name("DJ Moore")
    assert normalize_name("Marvin Harrison Jr.") == "marvinharrison"


def test_linker_fallback_order():
    linker = IdLinker(NFLVERSE)
    assert linker.gsis_for({"gsis_id": " X9 ", "full_name": "whoever"}) == "X9"
    assert linker.gsis_for({"espn_id": 1, "full_name": "Wrong Name"}) == "G1"
    assert linker.gsis_for({"full_name": "DJ Moore", "position": "WR"}) == "G2"
    assert linker.gsis_for({"full_name": "DJ Moore", "position": "RB"}) is None


def test_linker_skips_ambiguous_and_retired_names():
    linker = IdLinker(NFLVERSE)
    assert linker.gsis_for({"full_name": "Mike Williams", "position": "WR"}) is None
    assert linker.gsis_for({"full_name": "Old Guy", "position": "QB"}) is None


def test_pfr_map():
    assert pfr_to_gsis(NFLVERSE) == {"P2": "G2"}

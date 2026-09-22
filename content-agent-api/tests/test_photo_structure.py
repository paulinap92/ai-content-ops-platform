from src.domain.photo_structure import parse_photo_folder


def test_product_structure_is_parsed() -> None:
    meta = parse_photo_folder(
        "Tenerife/Explore/natural-pools/Guimar/Puertito de Guimar"
    )
    assert meta.island == "Tenerife"
    assert meta.site_area == "explore"
    assert meta.site_section == "natural-pools"
    assert meta.municipality == "Guimar"
    assert meta.place == "Puertito De Guimar"


def test_guide_structure_does_not_require_location() -> None:
    meta = parse_photo_folder("Gran Canaria/Guide/nature")
    assert meta.island == "Gran Canaria"
    assert meta.site_area == "guide"
    assert meta.site_section == "nature"
    assert meta.municipality == ""
    assert meta.place == ""


def test_old_island_municipality_structure_still_works() -> None:
    meta = parse_photo_folder("Tenerife/Guimar")
    assert meta.island == "Tenerife"
    assert meta.site_area == ""
    assert meta.site_section == ""
    assert meta.municipality == "Guimar"

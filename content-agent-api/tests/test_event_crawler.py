from src.events.crawler import GenericEventCrawler
from src.events.source_catalog import EVENT_SOURCE_BY_ID


def test_lalaguna_keeps_event_details_and_rejects_news() -> None:
    source = EVENT_SOURCE_BY_ID["la-laguna-agenda"]
    crawler = GenericEventCrawler(delay_seconds=0)

    assert crawler._is_candidate(  # noqa: SLF001
        source,
        "https://www.lalaguna.es/actualidad/eventos/Recital-Poetico",
    )
    assert not crawler._is_candidate(  # noqa: SLF001
        source,
        "https://www.lalaguna.es/actualidad/noticias/Laura-Morales-presenta-Ser-Pastora",
    )
    assert not crawler._is_candidate(source, source.url)  # noqa: SLF001
    assert not crawler._is_candidate(  # noqa: SLF001
        source,
        "https://www.lalaguna.es/actualidad/eventos/?page=2",
    )


def test_lalaguna_navigation_stays_in_event_area() -> None:
    source = EVENT_SOURCE_BY_ID["la-laguna-agenda"]
    crawler = GenericEventCrawler(delay_seconds=0)

    assert crawler._can_navigate(  # noqa: SLF001
        source,
        "https://www.lalaguna.es/actualidad/eventos/?page=2",
    )
    assert not crawler._can_navigate(  # noqa: SLF001
        source,
        "https://www.lalaguna.es/actualidad/noticias/foo",
    )


def test_lalaguna_starts_from_future_only_official_filter() -> None:
    source = EVENT_SOURCE_BY_ID["la-laguna-agenda"]
    assert "buscadorfield-4=true" in source.url


def test_la_gomera_accepts_event_detail_and_rejects_news() -> None:
    source = EVENT_SOURCE_BY_ID["cabildo-la-gomera-cultura"]
    crawler = GenericEventCrawler(delay_seconds=0)

    assert crawler._is_candidate(  # noqa: SLF001
        source,
        "https://www.lagomera.es/evento/segunda-edicion-de-la-pasarela-la-gomera-moda-y-magia",
    )
    assert not crawler._is_candidate(  # noqa: SLF001
        source,
        "https://www.lagomera.es/noticia/el-cabildo-abre-la-inscripcion-para-cursar-formacion",
    )

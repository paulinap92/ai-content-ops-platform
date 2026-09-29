from src.events.source_catalog import EVENT_SOURCE_BY_ID, EVENT_SOURCES


def test_event_source_ids_are_unique() -> None:
    assert len(EVENT_SOURCE_BY_ID) == len(EVENT_SOURCES)


def test_event_sources_use_https_urls() -> None:
    assert EVENT_SOURCES
    assert all(source.url.startswith("https://") for source in EVENT_SOURCES)


def test_core_tenerife_sources_are_seeded() -> None:
    ids = set(EVENT_SOURCE_BY_ID)
    assert {
        "webtenerife-agenda",
        "auditorio-tenerife",
        "tea-tenerife",
        "la-laguna-agenda",
    }.issubset(ids)


def test_la_gomera_uses_canonical_event_pages_not_news_feed() -> None:
    source = EVENT_SOURCE_BY_ID["cabildo-la-gomera-cultura"]
    assert source.crawl_strategy == "tavily"
    assert source.candidate_path_prefixes == ("/evento/",)
    assert "/noticia/" in source.exclude_path_prefixes
    assert "/noticias/" in source.exclude_path_prefixes

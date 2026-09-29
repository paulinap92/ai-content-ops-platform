from src.events.cleaner import clean_event_html


def test_cleaner_keeps_json_ld_event() -> None:
    html = '''
    <html><head>
      <script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Event","name":"Concierto de prueba","startDate":"2026-10-03T20:00:00+01:00","location":{"@type":"Place","name":"Teatro Leal"}}
      </script>
    </head><body><nav>MENU</nav><main><h1>Concierto de prueba</h1><p>Una actuación cultural en La Laguna.</p></main><footer>newsletter</footer></body></html>
    '''
    result = clean_event_html(html, "https://example.com/evento")
    assert result["json_ld_event"]["name"] == "Concierto de prueba"
    assert "Concierto de prueba" in result["text"]


def test_cleaner_keeps_explicit_fields_and_trims_lalaguna_footer_noise() -> None:
    html = '''
    <html><body>
      <nav>LA LAGUNA, PATRIMONIO DE LA HUMANIDAD</nav>
      <h1>PIELES - TARASCA</h1>
      <div>Información del evento</div>
      <div>Lugar:</div><div>Teatro Leal</div>
      <div>Inicio:</div><div>23 de mayo de 2019 | 10:05</div>
      <p>Descripción real del evento.</p>
      <h2>Suscripción / baja al boletín de noticias</h2>
      <p>Suscríbete a nuestro boletín.</p>
      <h2>Últimas noticias</h2><p>Noticia que no pertenece al evento.</p>
    </body></html>
    '''
    result = clean_event_html(html, "https://www.lalaguna.es/actualidad/eventos/PIELES-TARASCA")
    assert result["html_fields"]["start_at"] == "2019-05-23T10:05:00"
    assert result["html_fields"]["venue"] == "Teatro Leal"
    assert result["text"].startswith("PIELES - TARASCA")
    assert "Últimas noticias" not in result["text"]
    assert "Noticia que no pertenece" not in result["text"]

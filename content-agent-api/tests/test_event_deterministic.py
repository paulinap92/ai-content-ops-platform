from datetime import date

from src.events.deterministic import extract_html_event_fields, is_past_event, parse_event_datetime


def test_spanish_labelled_fields_are_extracted_before_llm() -> None:
    html = """
    <html><body>
      <h1>La Ruta</h1>
      <section>
        <h2>Información del evento</h2>
        <div>Lugar:</div><div>San Cristobal de La Laguna</div>
        <div>Inicio:</div><div>28 de noviembre de 2019</div>
        <div>Finalización:</div><div>22 de diciembre de 2019</div>
        <div>Precio de la tapa:</div><div>3,50 €</div>
      </section>
    </body></html>
    """
    fields = extract_html_event_fields(html)
    assert fields["title"] == "La Ruta"
    assert fields["venue"] == "San Cristobal de La Laguna"
    assert fields["start_at"] == "2019-11-28"
    assert fields["end_at"] == "2019-12-22"
    assert fields["price"] == "3,50 €"


def test_spanish_datetime_with_time_is_normalized() -> None:
    assert parse_event_datetime("23 de mayo de 2019 | 10:05") == "2019-05-23T10:05:00"


def test_explicit_finished_event_is_filtered() -> None:
    fields = {"start_at": "2019-05-23T10:05:00"}
    assert is_past_event(fields, today=date(2026, 9, 29))
    assert not is_past_event({"start_at": "2026-10-03"}, today=date(2026, 9, 29))



def test_import_extracts_explicit_tenerife_event_without_ai_key(monkeypatch):
    from src.events import nodes
    from src.core.config import settings
    from src.events.source_catalog import EVENT_SOURCES
    source=next(s for s in EVENT_SOURCES if s.island.lower()=='tenerife')
    monkeypatch.setattr(nodes,'settings',settings.model_copy(update={'openai_api_key':None,'anthropic_api_key':None}))
    monkeypatch.setattr(nodes,'create_model',lambda *a,**k: (_ for _ in ()).throw(AssertionError('No model should be created')))
    from dataclasses import asdict
    result=nodes.extract({'source_id':source.source_id,'source_config':asdict(source),'cleaned_pages':[{'url':'https://official.example/event','text':'Fiesta publicada por la fuente','html_fields':{'title':'Fiesta de Tenerife','start_at':'2099-11-07T18:00:00','venue':'Santa Cruz'}},{'url':'https://official.example/no-date','text':'Sin fecha','html_fields':{'title':'No date'}}]})
    assert len(result['events'])==1
    assert result['events'][0]['title']=='Fiesta de Tenerife' and result['events'][0]['extraction_method']=='html'
    assert result['stats']['llm']==0 and result['stats']['deterministic']==1

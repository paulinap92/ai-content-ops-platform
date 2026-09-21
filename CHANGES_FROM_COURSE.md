# Zmiany względem projektu z kursu

## Część tekstowa

LangGraph nadal zachowuje prawie ten sam przepływ:

```text
research → curate → human_review → write → publish
```

Tylko node'y pracują dla Canarias Cerca i kończą finalnym JSON-em ES/EN/PL.

## v0.2

Doszedł webowy **Text Editor** i ekran **Graph**.

## v0.3 — Photo Manager

Nie zmieniamy grafu tekstowego. Do tego samego FastAPI dokładamy osobny moduł:

```text
src/services/photo_source.py
src/services/photo_service.py
src/api/v1/photos.py
PhotoDocument w src/domain/documents.py
Photo schemas w src/domain/schemas.py
```

UI ma teraz:

```text
[ Text Editor ] [ Photos ] [ Graph ]
```

Photo workflow w v0.3:

```text
scan_source
↓
infer metadata from folders
↓
human review
↓
approve / skip
↓
rename
```

To jeszcze nie jest LangGraph, bo na tym etapie nie ma powodu robić z prostego skanu plików agenta. Gdy dodamy Gemini Vision i ewentualne poprawki/ponowne analizy, możemy świadomie zdecydować, czy photo workflow też warto przenieść do osobnego grafu.

Najważniejsza zasada: **LLM nie robi rzeczy deterministycznych**, takich jak skan folderu czy rename. AI dostanie tylko analizę treści zdjęcia.

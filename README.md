# Canarias Cerca Content Studio — v0.3

Jeden projekt dla dwóch rzeczy:

1. **Text Editor** — LangGraph + Human-in-the-loop do przygotowywania treści Canarias Cerca.
2. **Photo Manager** — skan folderów/Google Drive, kolejka zdjęć, metadata, approve/skip i automatyczny rename.

## Co doszło w v0.3

- nowa zakładka **Photos** w tym samym UI,
- nowa kolekcja MongoDB `photos`,
- endpointy `/api/v1/photos/...`,
- dwa źródła zdjęć:
  - `PHOTO_SOURCE=local` — zwykły folder lokalny, idealny do pierwszych testów,
  - `PHOTO_SOURCE=drive` — prawdziwy Google Drive przez Drive API,
- skan rekurencyjny folderów,
- wyspa i gmina są wyciągane z hierarchii folderów,
- podgląd zdjęcia,
- ręczna korekta: miejsce, kategoria, alt, tagi i nazwa,
- `Approve + rename` naprawdę zmienia nazwę pliku w źródle,
- `Skip` odkłada zdjęcie bez ruszania pliku,
- w zakładce **Graph** doszedł osobny schemat Photo workflow.

> W tej wersji **Gemini Vision jeszcze nie analizuje zdjęcia**. To będzie kolejny krok. Najpierw mamy działający scanner + review + rename.

---

## Przykładowa struktura folderów

```text
photo_inbox/
├── Tenerife/
│   ├── Guimar/
│   │   ├── IMG_3847.jpg
│   │   └── IMG_3848.jpg
│   └── La Laguna/
└── Gran Canaria/
    └── Agaete/
```

Dla:

```text
Tenerife/Guimar/IMG_3847.jpg
```

program wie od razu:

```text
island = Tenerife
municipality = Guimar
```

i proponuje unikalną nazwę w stylu:

```text
tenerife-guimar-a41c9f.jpg
```

Po dodaniu Gemini nazwa będzie bardziej semantyczna, np.:

```text
puertito-de-guimar-paseo-maritimo-a41c9f.jpg
```

---

# Najprostsze uruchomienie lokalne — uv

## 1. Wejdź do projektu

```powershell
cd canarias-cerca-editor-project-v0.3
```

## 2. Uruchom MongoDB

```powershell
docker compose up -d mongodb
```

## 3. Wejdź do backendu

```powershell
cd content-agent-api
```

## 4. Python 3.13 przez uv

```powershell
uv python install 3.13
```

## 5. Utwórz `.env`

PowerShell:

```powershell
Copy-Item .env.example .env
```

W `.env` ustaw co najmniej:

```env
MODEL_PROVIDER=openai
OPENAI_API_KEY=twoj_klucz
OPENAI_MODEL_NAME=gpt-5.6

MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB_NAME=canarias_cerca_editor

PHOTO_SOURCE=local
PHOTO_LOCAL_ROOT=./photo_inbox
```

## 6. Zainstaluj dependencies

```powershell
uv sync
```

## 7. Wrzuć kilka zdjęć

Przykład:

```text
content-agent-api/
└── photo_inbox/
    └── Tenerife/
        └── Guimar/
            ├── IMG_001.jpg
            └── IMG_002.jpg
```

## 8. Start

```powershell
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

## 9. Otwórz

- UI: `http://127.0.0.1:8000/`
- Swagger: `http://127.0.0.1:8000/docs`

W UI:

```text
Photos
→ Scan folders
→ wybierz zdjęcie
→ popraw metadata jeśli chcesz
→ Approve + rename
```

---

# Jak przełączyć się później na prawdziwy Google Drive

W Google Cloud potrzebujemy Drive API oraz service account.
Folder `Canarias Cerca` na Drive udostępniasz temu service accountowi jak zwykłemu użytkownikowi.

`.env`:

```env
PHOTO_SOURCE=drive
GOOGLE_DRIVE_ROOT_FOLDER_ID=ID_FOLDERU_CANARIAS_CERCA
GOOGLE_SERVICE_ACCOUNT_FILE=C:/sekrety/canarias-drive-service-account.json
```

Potem ten sam przycisk:

```text
Scan folders
```

nie skanuje dysku, tylko Google Drive.

**Nie zmienia się UI ani PhotoService.** Zmienia się tylko provider danych.

Na Cloud Run zamiast pliku z kluczem będziemy mogli użyć service account środowiska i udostępnić mu folder Drive.

---

# API Photos

```text
POST   /api/v1/photos/scan
GET    /api/v1/photos
GET    /api/v1/photos/{photo_id}
PATCH  /api/v1/photos/{photo_id}
GET    /api/v1/photos/{photo_id}/preview
POST   /api/v1/photos/{photo_id}/decision
DELETE /api/v1/photos/{photo_id}
```

Decision:

```json
{"action": "approve"}
```

lub:

```json
{"action": "skip"}
```

---

# Co jest następne

Następny krok jest już AI:

```text
scan_source
↓
infer_folders
↓
Gemini Vision
  - co jest na zdjęciu
  - place
  - category
  - alt_es
  - tags
  - semantyczna nazwa
↓
human_review
↓
approve + rename
↓
R2 / publikacja później
```

Nie dokładamy jeszcze R2. Najpierw chcemy, żeby Drive → review → rename działało dobrze.

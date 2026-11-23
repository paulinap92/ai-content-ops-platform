# Studio CanariasCerca

Wejdź na **https://canarias-content-editor.onrender.com/** i zaloguj się dotychczasowym kluczem. Zakładka **Studio CanariasCerca** otwiera tę samą aplikację `/site/`. Wydarzenia, AI, artykuły, zdjęcia i social pozostają dostępne. Niczego nie uruchamiasz lokalnie.

## Miejsca i zdjęcia

1. Kliknij **Lugares · miejsca i mapa**. Katalog pokazuje 372 opisy na stronie i 8 wstrzymanych. Wyszukaj nazwę lub UUID. Możesz też wybrać wyspę w mapie witryny i kliknąć kartę albo pinezkę w podglądzie Lugares.
2. Obok podglądu otworzy się formularz. Zmień krótki opis, szczegóły, źródła, kategorię, linki lub współrzędne. Mapa pod formularzem pomaga sprawdzić punkt.
3. **Wgraj zdjęcie z komputera** lub wybierz je z dotychczasowej biblioteki. Uzupełnij ALT, autora, licencję i źródło. Proporcje i środek kadru można ustawić przed wysłaniem; **Kadruj wybrane zdjęcie** tworzy kopię, zachowując oryginał. Galeria mieści 20 zdjęć; edytujesz opisy, kolejność i przypisania.
4. **Pokaż szkic Lugares** wyświetla treść i zdjęcia w bieżącym podglądzie. Miejsce musi być załadowane w Lugares; otwórz jego kartę. **Odśwież stronę** przywraca wersję opublikowaną. Pozostałe rodziny treści mają dotychczasowy przycisk **Podgląd i zmiany**.
5. **Zapisz treść roboczą** zachowuje szkic; dotychczasowy opis pozostaje na stronie. Sprawdź tekst, źródła i położenie, zaznacz potwierdzenie i wybierz **Opublikuj treść**. Podgląd się odświeży. Odwiedzający zobaczą zmianę przy odświeżeniu strony.
6. **Historia wersji treści** → przywróć wersję jako szkic → sprawdź → opublikuj. Konflikt wersji wymaga wczytania aktualnych danych i porównania.

Osiem wstrzymanych pozycji zachowuje powody blokad. Możesz poprawiać szkice; zwykły edytor ani klient API nie mogą ich opublikować. Odblokowanie wymaga osobnej decyzji redakcyjnej i kontrolowanej zmiany rejestru.

## Jedna aplikacja

Wybierz wyspę i katalog w drzewie, potem **+ Dodaj**, aby utworzyć miejsce, artykuł lub wydarzenie. Nowe miejsce wymaga rzeczywistych współrzędnych; importer kontroluje duplikaty i lokalizację. Wydarzenia zachowują dotychczasowe źródła, odkrywanie, selekcję i import do szkicu. Artykuły zachowują poprawianie z AI. Zdjęcia w formularzu i zakładce korzystają z tej samej biblioteki.

Mapa witryny jest generowana przy buildzie z `js/core/routes.js`: **497 rzeczywistych widoków na 8 wyspach**, także sekcje w rozwoju. Manifest podaje komponent, API, źródło i zakres edycji. Pogoda, kalima, sejsmika i statystyki są oznaczone jako automat: edytujesz prezentację i widoczność, a pomiary pozostają automatyczne.

To pierwszy pionowy zakres issue #4: podgląd całej strony, wybór treści, Lugares, zdjęcia, galerie i realna publikacja. Nowe niestandardowe bloki, dowolny HTML i pełna edycja konfiguracji wszystkich automatycznych źródeł wymagają kolejnych adapterów. Istniejące formularze i inspektor pozostają we wspólnej nawigacji.

## Dane i wdrożenie

Lugares pozostaje w `design.entity_source_properties`, `provider=canarias-cerca-editorial`. Szkice i historia używają istniejących `cc_studio_documents` i `cc_studio_revisions`, zdjęcia dotychczasowego magazynu Neon/R2. Publikacja opisów i zdjęć synchronizuje trzy katalogi tej samej tożsamości. Dane dostawców i geometria kanoniczna są zachowane.

**Nie uruchamiaj historycznej migracji B1**: adapter jej nie potrzebuje, nie zmienia FK `content_items` ani flag natywnego importu. Wdrażanie: backup → backend `sql/20261123_universal_studio_guard.sql` (idempotentnie) → backend → frontend → editor. Trzy istniejące usługi Render, ręcznie z `production`; bez nowych usług i zmian autoDeploy.

Backup: `backup-before-universal-studio-20261123` (`br-muddy-grass-ba7fhwf2`). Próba migracji: `studio-migration-check-20261123` (`br-sweet-snow-ba6i2ilt`). Nie usuwać automatycznie. Dwa wykonania migracji zachowały 403 nakładki / 372 UUID i hash treści; bezpośredni zapis dla wstrzymanego UUID został odrzucony przez trigger.

Rollback treści: historia → przywróć szkic → publikuj. Rollback kodu: ponownie wdrożyć poprzednie commity. Tabela blokad i trigger mogą pozostać; poprzedni kod jest z nimi zgodny. Rollback kodu nie cofa treści ani plików; do odtworzenia danych służy zachowany backup.

## Sprawdzenie

`pytest -q` z odizolowanym PostgreSQL/PostGIS i `EDITOR_STORAGE=postgres`. `test_visual_studio.py`: szkic, trzy katalogi, media, konflikty, przywrócenie, blokady i wydarzenie → szkic → edycja → publikacja. Browser: `site_editor.browser.mjs`, `lugares.browser.mjs`, `visual_studio.browser.mjs` (opcjonalnie `CC_TEST_CHROMIUM`). Nowy test używa rzeczywistych zasobów UI i izolowanych odpowiedzi API. Frontend: `npm test`, `npm run build`; `tests/studio.test.mjs` sprawdza manifest, origin, tekst i media.

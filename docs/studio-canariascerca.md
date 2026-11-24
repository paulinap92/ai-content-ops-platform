# Studio CanariasCerca

Otwórz **https://canarias-content-editor.onrender.com/** i zaloguj się dotychczasowym kluczem. Główny edytor otwiera się bezpośrednio pod `/site/`, na pełnej stronie. Wspólne menu prowadzi do treści, wydarzeń, zdjęć, bazy, AI i publikacji społecznościowych. Nie trzeba nic uruchamiać lokalnie.

## Dodawanie i edycja

1. **Miejsca i mapa** → wybierz wyspę i katalog w lewym menu: Lugares, Playas, Piscinas naturales, Buceo, Rutas itd. **+ Dodaj punkt** tworzy wpis w wybranym katalogu. W całym archipelagu można wybrać wyspę obok przycisku. W Guía przycisk dodaje artykuł, w kalendarzu wydarzenie, w Noticias aktualność.
2. **Przegląd strony** otwiera mały podgląd. Wybierz wyspę/widok w automatycznej mapie witryny i kliknij kartę, tekst lub pinezkę. Edytor otworzy właściwy wpis. **Zwiń podgląd** zostawia pełną szerokość dla pracy; formularz przewijasz razem ze stroną.
3. Formularz ma zakładki **Treść**, **Zdjęcia i galeria**, **Położenie / pinezka**, **Linki i źródła**, **Dodatkowe dane**. **Przeglądaj wpisy w tej sekcji** rozwija listę; wyszukiwarka filtruje aktualny katalog.
4. W **Położenie / pinezka** wpisz szerokość i długość geograficzną. **Odśwież położenie na mapie** sprawdza wpisane współrzędne. Nowy punkt bez współrzędnych nie pokazuje fikcyjnej pinezki. Rutas wymagają rzeczywistej geometrii linii w polu GeoJSON; samo wskazanie punktu nie tworzy przebiegu szlaku.
5. **Zapisz treść roboczą** → **Podgląd i zmiany** → **Opublikuj treść**. Zapis szkicu nie zmienia witryny. Lugares wymagają sprawdzenia tekstu, źródeł, kategorii i położenia oraz zaznaczenia potwierdzenia. Odwiedzający zobaczą publikację po odświeżeniu strony.

## Widoczność i linki

- **Treść → Widoczne na stronie (po publikacji)**: zaznaczone pokazuje wpis; odznaczone ukrywa. Zapisz i opublikuj, aby zmienić witrynę. Ukryty wpis pozostaje dostępny w Studio.
- **Linki i źródła → Pokazuj linki na stronie** steruje linkami tego wpisu. Uzupełnij stronę internetową/adres/źródła, zapisz i opublikuj. Strona wyświetla klikalne, bezpieczne linki ze Studia; wyłączenie przełącznika je ukrywa. Źródło zdjęcia i prywatne notatki nie są przyciskami nawigacyjnymi.
- Widoczność całej sekcji ustawiasz przełącznikiem przy jej nagłówku. Przyciski **Zapisz teksty i widoczność** i **Opublikuj zmiany strony** dotyczą ustawień witryny, a nie pojedynczego wpisu. Ukryta sekcja nadrzędna ukrywa również swoje podsekcje.

## Jak dodać zdjęcie

1. Otwórz wpis → **Zdjęcia i galeria** → **Wgraj zdjęcie z komputera**. JPEG, PNG i WebP do 20 MB są zmniejszane przed wysłaniem. Albo kliknij **Wybierz zdjęcie z biblioteki** — ta sama biblioteka obsługuje dotychczasowe zdjęcia z Drive i pliki strony.
2. Uzupełnij ALT, autora i licencję. **Kadrowanie (opcjonalne)** pozwala wybrać proporcje i środek kadru; kadrowanie tworzy kopię i zachowuje oryginał.
3. Do galerii użyj **Wgraj zdjęcia do galerii** (można wybrać kilka plików) lub **+ Dodaj zdjęcie z biblioteki**. Limit: 20 zdjęć. Rozwiń podpis konkretnego zdjęcia, aby zmienić ALT, autora, licencję i źródło. Strzałka zmienia kolejność.
4. Zapisz i opublikuj wpis. Sam upload zapisuje plik w bibliotece i przypisanie do szkicu. **Usuń zdjęcie z wpisu** usuwa przypisanie; plik pozostaje w bibliotece.

## Noticias — wiadomości i własne artykuły

Otwórz **Noticias · wiadomości** w menu Studia (bezpośrednio: https://canarias-content-editor.onrender.com/?view=noticias).

1. Wybierz wyspę albo całe Kanary. Kliknij **Napisz wiadomość**, wklej własny tekst i wybierz kategorię. Możesz dodać link źródłowy.
2. Możesz też wybrać źródło → **Pobierz propozycje ze źródła**, albo wpisać temat → **Szukaj w internecie**. Wyszukiwanie korzysta z istniejącego Tavily i jest dostępne po jego konfiguracji. HTML, RSS i Atom z podanego linku działają bez AI.
3. Kliknij **Przygotuj wiadomość na podstawie materiału**. **Pobierz materiał z linku** pobiera tekst do osobnego pola roboczego. Materiał źródłowy nie jest automatycznie kopiowany do artykułu ani publikowany.
4. Napisz własną treść albo użyj opcjonalnego **Przygotuj szkic z AI**. AI przygotowuje i zapisuje gotowy tekst do tego samego szkicu Noticias, po czym otwiera edytor do sprawdzenia. Nie wymaga osobnego zatwierdzania konspektu. Zachowuje wyspę, kategorię i źródło; nie trafia do Guía.
5. **Zapisz szkic i otwórz edytor** → dodaj zdjęcie/galerię → **Podgląd i zmiany** → **Opublikuj treść**. Strona wyświetla krótki opis oraz rozwijaną pełną treść własnego artykułu, źródła i galerię. **Enlace a este artículo** daje stały link; otworzy artykuł także poza listą 50 najnowszych wiadomości.
6. Kolejka pokazuje szkice, opublikowane i ukryte wiadomości. **Przeglądaj wiadomości na stronie** otwiera istniejące wpisy, także z automatycznego importu. Ukrywanie i przywracanie wersji używają tego samego edytora i historii. Wyłączone źródło pozostaje w katalogu i można je włączyć ponownie.

Źródła zainicjowano z istniejącej konfiguracji importu wiadomości dla ośmiu wysp i Gobierno de Canarias. Nie włączamy nowych harmonogramów. Zapis źródła lub pobranie propozycji nie zapisuje wiadomości na stronie. Powtórny import tego samego linku otwiera istniejący szkic, zachowując poprawki. Własne artykuły mają osobną tożsamość, więc nie nadpisują wpisów RSS. Guía zachowuje osobny edytor przewodnika.

## Baza danych i narzędzia

**Baza danych** to rzeczywiste tabele PostgreSQL ze schematu `design`: wybór tabeli, kolumn, wyszukiwanie, sortowanie, paginacja i szczegóły rekordu. Nie otwiera podglądu witryny. To przeglądarka tylko do odczytu; treści zmienia się zwykłymi formularzami.

Mapa witryny powstaje z `js/core/routes.js`: **497 rzeczywistych widoków na 8 wyspach**. Dla pogody, kalimy, sejsmiki i statystyk można zmieniać prezentację i widoczność. Pomiary aktualizują zadania automatyczne; nie wpisujemy ich ręcznie. Obsługiwane punkty Live dodaje przycisk **Dodaj punkt** w danych danej warstwy. Konfiguracje pozostałych automatycznych źródeł wymagają kolejnych adapterów.

Wyszukiwanie wydarzeń, źródła, selekcja i import do szkicu oraz poprawianie artykułów z AI pozostają w tej samej aplikacji. **Historia wersji treści** przywraca wersję jako szkic do sprawdzenia i publikacji. Konflikt wersji wymaga wczytania aktualnych danych i porównania.

Osiem wstrzymanych opisów ma zachowane powody blokad. Lista **Opisy: 372 opublikowane / 8 wstrzymanych** otwiera rejestr publikacji. Szkice można poprawiać; blokada uniemożliwia publikację także przez API. Odblokowanie wymaga osobnej decyzji redakcyjnej.

## Dane i wdrożenie

Lugares pozostaje w `design.entity_source_properties`, `provider=canarias-cerca-editorial`. Szkice i historia używają istniejących `cc_studio_documents` i `cc_studio_revisions`, zdjęcia dotychczasowego magazynu Neon/R2. Publikacja opisów i zdjęć synchronizuje trzy katalogi tej samej tożsamości. Dane dostawców i geometria kanoniczna są zachowane.

**Nie uruchamiaj historycznej migracji B1**: adapter jej nie potrzebuje, nie zmienia FK `content_items` ani flag natywnego importu. Wdrażanie: backup → backend `sql/20261123_universal_studio_guard.sql` (idempotentnie) → backend → frontend → editor. Trzy istniejące usługi Render, ręcznie z `production`; bez nowych usług i zmian autoDeploy.

Backup: `backup-before-universal-studio-20261123` (`br-muddy-grass-ba7fhwf2`). Próba migracji: `studio-migration-check-20261123` (`br-sweet-snow-ba6i2ilt`). Nie usuwać automatycznie. Dwa wykonania migracji zachowały 403 nakładki / 372 UUID i hash treści; bezpośredni zapis dla wstrzymanego UUID został odrzucony przez trigger.

Rollback treści: historia → przywróć szkic → publikuj. Rollback kodu: ponownie wdrożyć poprzednie commity. Tabela blokad i trigger mogą pozostać; poprzedni kod jest z nimi zgodny. Rollback kodu nie cofa treści ani plików; do odtworzenia danych służy zachowany backup.

## Sprawdzenie

`pytest -q` z odizolowanym PostgreSQL/PostGIS i `EDITOR_STORAGE=postgres`. `test_visual_studio.py`: szkic, trzy katalogi, media, konflikty, przywrócenie, blokady i wydarzenie → szkic → edycja → publikacja. Browser: `site_editor.browser.mjs`, `lugares.browser.mjs`, `visual_studio.browser.mjs` (opcjonalnie `CC_TEST_CHROMIUM`). Nowy test używa rzeczywistych zasobów UI i izolowanych odpowiedzi API. Frontend: `npm test`, `npm run build`; `tests/studio.test.mjs` sprawdza manifest, origin, tekst i media.

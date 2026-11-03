# Stan zawartości strony — 3 listopada 2026

Odczyt publicznego API zasilanego PostgreSQL. Nie wykonano importu, publikacji ani synchronizacji danych. Liczby są migawką; joby mogą je zmieniać.

## Wyniki

- Sprawdzono 17 katalogów Explore × 8 wysp: 136 odpowiedzi HTTP 200, 103 zakresy z wpisami i 33 puste.
- Sprawdzono 15 rozdziałów treści × 8 wysp: 120 odpowiedzi HTTP 200, 659 zwróconych wpisów, bez pustych rozdziałów.
- Destacados jest treścią Guide o sekcji `explore`; brakowało odnośnika w edytorze. Nie należy szukać go w filtrze mapowych miejsc.
- Bodegas y queserías: 9 wpisów, wyłącznie Fuerteventura (6) i Gran Canaria (3). Buceo: 1 wpis na El Hierro. To rzeczywisty stan katalogów, nie awaria wczytywania.
- Liczby nie dowodzą kompletności względem rzeczywistej oferty wysp. Nie dodawano niezweryfikowanych miejsc, aby zapełnić puste kategorie.

## Explore

| Katalog | Wpisy w całym katalogu | Wyspy bez wpisów |
|---|---:|---|
| Playas | 456 | Brak — wpisy na wszystkich 8 wyspach |
| Buceo | 1 | tenerife, gran-canaria, lanzarote, fuerteventura, la-palma, la-gomera, la-graciosa |
| Fauna | 592 | Brak — wpisy na wszystkich 8 wyspach |
| Flora | 446 | Brak — wpisy na wszystkich 8 wyspach |
| Bodegas y queserías | 9 | tenerife, lanzarote, la-palma, la-gomera, el-hierro, la-graciosa |
| Ocio | 24 | la-gomera, el-hierro, la-graciosa |
| Puertos deportivos | 33 | Brak — wpisy na wszystkich 8 wyspach |
| Mercados | 27 | la-gomera, la-graciosa |
| Museos y visitas | 122 | la-graciosa |
| Piscinas naturales | 18 | fuerteventura, la-graciosa |
| Espacios naturales | 11 | tenerife, lanzarote, la-gomera, el-hierro, la-graciosa |
| Lugares | 375 | Brak — wpisy na wszystkich 8 wyspach |
| Rutas | 554 | Brak — wpisy na wszystkich 8 wyspach |
| Mirar las estrellas | 30 | la-graciosa |
| Cumbres | 284 | Brak — wpisy na wszystkich 8 wyspach |
| Surf | 3 | lanzarote, fuerteventura, la-palma, la-gomera, el-hierro, la-graciosa |
| Volcanes | 140 | Brak — wpisy na wszystkich 8 wyspach |

Badanie obecności używa `limit=1`: nie jest liczbą wszystkich wpisów na danej wyspie. Suma globalna pochodzi z `/api/explore-canonical/catalogs`. Rozkłady Bodegas/Buceo potwierdzono małymi audytami pojedynczych katalogów.

## Treści i Destacados

| Wyspa | Wszystkie 15 rozdziałów | W tym Destacados |
|---|---:|---:|
| tenerife | 81 | 6 |
| gran-canaria | 92 | 14 |
| lanzarote | 81 | 6 |
| fuerteventura | 81 | 6 |
| la-palma | 81 | 6 |
| la-gomera | 81 | 6 |
| el-hierro | 81 | 6 |
| la-graciosa | 81 | 6 |

## Kalendarz

| Wyspa | Dostępne miesiące i liczby wydarzeń |
|---|---|
| tenerife | 2026-11: 51, 2026-10: 63, 2026-09: 19 |
| gran-canaria | 2026-11: 32, 2026-10: 28 |
| lanzarote | 2026-10: 29 |
| fuerteventura | 2026-11: 11, 2026-10: 13 |
| la-palma | 2026-11: 15, 2026-10: 10 |
| la-gomera | 2026-11: 12, 2026-10: 10 |
| el-hierro | 2026-11: 12, 2026-10: 11 |
| la-graciosa | Brak wydarzeń |

Wydarzenie wielodniowe może należeć do kilku miesięcy. Sum miesięcznych nie należy traktować jako liczby unikatowych wydarzeń.

## Live i Datos

Sprawdzono 88 odczytów publicznego API (11 zasobów × 8 wysp). Wszystkie zwróciły HTTP 200, co samo w sobie nie oznacza dostępności danych.

| Źródło | Wynik |
|---|---|
| Live: pogoda, jakość powietrza, morze, pływy, plaże, webcams | Dostępne dla wszystkich 8 wysp; liczby punktów różnią się między wyspami. |
| Alerty | Odczyt działa dla 8 wysp. Pusta lista może oznaczać brak alertów, nie brak zasilania. |
| Sismos | Odczyt działa dla 8 wysp. Ten audyt nie dowodzi ciągłości historycznego zbioru. |
| Volcanes | Globalny odczyt zwraca stan `ok`, dostępny. |
| Clima: weather i air-quality | Historia z ostatniego dnia zawiera pomiary dla każdej z 8 wysp. Audyt nie potwierdza braku luk w starszej historii. |
| Pasajeros — ruch lotniczy | Dostępne dane dla Tenerife, Gran Canaria, Lanzarote, Fuerteventura i La Palma. La Gomera, El Hierro i La Graciosa zwracają `not_initialized`; La Graciosa nie ma lotniska, więc brak osobnego zestawu lotniczego nie jest sam w sobie błędem. |
| Tourism Pulse | Wszystkie 8 odpowiedzi wyspowych zwracają `available=false`, `stale=true`. Dostępność pozostałych danych turystycznych należy rozpatrywać osobno. |
| Población, Economía, Vivienda, Medio ambiente | W publicznym frontendzie pozostają zapowiedziami bez `connected: true`. Nie są gotowymi działami statystycznymi. Powiązane surowe tabele, np. population_entities i population_nuclei, można przeglądać niezależnie w przeglądarce SQL. |
| Katalogi transportu | Publiczne API zwraca 8 lotnisk, 14 portów i 9 połączeń promowych. Źródłem tych trzech katalogów jest kod aplikacji. |

Dane Live i pomiary w edytorze są tylko do przeglądania; aktualizują je dotychczasowe joby. Ta aktualizacja nie dodaje źródeł dla niegotowych działów ani nie naprawia Tourism Pulse.

## Weryfikacja zmiany

GitHub Actions: PostgreSQL/PostGIS i MongoDB (58 testów), kontener Docker bez uprawnień root, test przeglądarkowy edytora i parser Windows — wszystkie zakończone powodzeniem. Testy korzystały z izolowanych danych; nie publikowano treści testowych do bazy produkcyjnej.

## Zmiany w edytorze

- Przywrócono Destacados i wybór wyspy według rzeczywistej dostępności.
- Dodano tabelaryczny podgląd źródeł Live i Datos, czasów zapisów oraz zestawów pomiarowych.
- Dodano zwykłą przeglądarkę schematu `design`: tabela, kolumny, szukanie, sortowanie, paginacja i szczegóły JSON. Odczyty wymuszają transakcję READ ONLY i limity czasu; nie ma konsoli dowolnego SQL.
- Kalendarz ma widok miesiąca, wybór dnia/wydarzenia i podpowiedzi miesięcy z danymi.
- Podgląd opublikowanej strony ma tryb komputera i telefonu. Szkice artykułów mają osobny podgląd w formularzu.
- Usunięto LangGraph z głównej nawigacji. Silnik AI pozostaje wewnątrz aplikacji.
- Lotniska, porty i połączenia promowe są nadal katalogami w kodzie publicznego API. Edytor odczytuje to samo źródło i nie udaje, że pusta tabela SQL oznacza brak tych miejsc.
- Przeglądanie bazy wymaga dotychczasowego prywatnego logowania. Dostęp do produkcyjnego interfejsu bez sesji pozostaje zablokowany.

## Źródła odczytu

`GET /api/explore-canonical/catalogs`, `GET /api/explore-canonical/{catalog}?island={island}&limit=1`, małe audyty `explore_food_producers` i `explore_diving_spots`, `GET /api/regions/canarias/content?island={island}&section={section}&limit=200`, `GET /api/regions/canarias/explore?island={island}`, `GET /api/regions/canarias/events/archive?island={island}`.

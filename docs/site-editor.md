# Site editing in the standalone Content Editor

The `/site/` workspace is served by the Content Editor itself. It is not an iframe
or proxy to the public website service: the embedded view, its API, authentication
and canonical SQL sessions all run in the editor's separate container.

A single signed, HttpOnly cookie protects the full editor, including AI routes,
photos, private assets, API documentation and SQL editing. The public login screen
and minimal liveness endpoint reveal no drafts or database credentials.
Local Docker binds only to loopback and still requires login.

## Workflows

- Start with the actual welcome text; use the left-hand site tree to choose an
  island, section or subsection using the same names as the public website.
- The selected part shows its text controls and one visibility switch together.
  Island-specific overrides have an explicit reset to the global setting.
- Guide/Explore entries open automatically when a category is selected. The
  published article is shown below the editing form for comparison.
- Save section text/visibility and article drafts explicitly. Publish remains a
  separate, version-checked action; browsing does not publish or overwrite data.
- For Live/Datos, edit explanatory copy and visibility. Measurements remain
  managed by the website's source jobs.
- Select an existing Guide article and choose **Popraw artykuł z AI**. Its content
  opens in the existing LangGraph workflow. Review the outline, approve generation
  and send the result to a private article draft. Publication remains separate.

Site visibility is a UI control, not a privacy boundary for previously public
information. Private drafts and editorial notes never enter the public API.

## Storage

`SITE_DATABASE_URL` is available only to the editor process. There is no website
worker or scheduler in this application. SQL pools are bounded and have statement
and lock timeouts. Editor-state tables/checkpoints live in `cc_editor_private`;
publication uses the existing canonical model and versioned draft/history tables.
The canonical model was extracted from backend commit
`17e6050c98a25edcef4691b0215a869d9bc47b07`; see `canarias_site/PROVENANCE.json`.

## Photos

File uploads accept JPEG, PNG and WebP up to 5 MB. They require
`R2_ACCOUNT_ID`, `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and
`R2_PUBLIC_BASE_URL` in the editor environment. Public image URLs can be edited
without R2. No photo or export depends on Render's ephemeral filesystem.

## Reading source data and inspecting the database

- **Baza danych** shows ordinary paginated PostgreSQL tables in `design`, with
  column metadata, search, ordering and expandable JSON cells. Every query uses
  a read-only transaction, statement/lock timeouts and a validated table/column
  list. It does not accept arbitrary SQL and excludes job control/credential tables.
- **Live** and **Datos** show canonical snapshots, observations and statistics,
  including source timestamps and honest empty states. No job or refresh is run.
- **Kompletność danych** shows all catalogs/islands, editorial chapters, calendar
  months, snapshot availability and history ranges. Counts include hidden records
  and are not a claim that external source coverage is complete.
- **Explore → Destacados** edits the same `guide/explore` articles used by the
  public Explore endpoint. It is distinct from the `featured` flag on map places.
- Calendar uses a month grid, dated entries and available-month navigation.
- **Podgląd strony** embeds the published website in desktop or phone width.
  Draft article preview and the publication diff remain separate from the live site.
- The LangGraph engine remains part of AI generation; it is not a navigation tab.


## Pełny przepływ edycji (2026-11-03)

- Historia otwiera okno również dla starej treści bez zapisanych wersji i wyjaśnia zakres historii. Wczytanie aktualnej wersji działa bez uprzedniego zapisu i zachowuje formularz. Poprawa z AI otwiera formularz pracy AI także przy wejściu bezpośrednio na `/site/`.
- Transport ma osobną pozycję Transporte: lotniska, porty, promy, przystanki i linie TITSA oraz TILP.
- Calendario filtruje miesięczne wpisy po miejscowości, kategorii, publikacji, datach i tekście. Ręczne `Dodaj` oraz `Wydarzenia → Do wersji roboczej strony` zapisują szkic. Dopiero `Opublikuj wydarzenie` udostępnia treść na stronie; importowany szkic otwiera się po swoim kluczu, a nie jako przypadkowy pierwszy wpis.
- Clima udostępnia wykresy: punkt / miejscowość, pogoda lub jakość powietrza, wielkość, zakres dat i przedział. Dodatkowo dostępne są tabela wykresu i CSV. Geología pokazuje zdarzenia sejsmiczne. Turismo udostępnia miesięczny wykres pasażerów i podział lotów według zapisanych serii; dane dotyczą wyspy, a nie miasta. Braki w szeregu nie są interpolowane. Domyślnie agregacja oznacza średnią zapisanych wartości w dniu UTC, nie nowy oficjalny wskaźnik meteorologiczny.
- Jedyna zakładka Zdjęcia otwiera katalog folderów: indeks Google Drive / źródła oraz trwałe pliki przesłane do biblioteki strony. Oryginały Drive pozostają na Drive. Użycie zdjęcia Drive we wpisie kopiuje wybrany plik do publicznej biblioteki po wyraźnym kliknięciu, nie przenosi oryginału. Katalog metadanych nie oznacza, że źródło jest połączone; stan połączenia jest wyświetlany. JPEG/PNG/WebP do 20 MB są w przeglądarce zmniejszane do maks. 1920 px i JPEG, a wynik ma limit 5 MB. Podpis autora i alt można wpisać przed wgraniem. Wybór zdjęcia przypisuje je do otwartego formularza, wymagającego osobnego zapisu i publikacji.
- Gdy R2 nie jest skonfigurowane, biblioteka korzysta z addytywnej tabeli `design.cc_studio_assets` w istniejącej bazie. Limit tej biblioteki to 100 MB, pliki są deduplikowane według SHA256. Publiczny backend udostępnia wyłącznie konkretne obrazy pod `/api/media/{sha256}`; administracja wymaga dotychczasowej sesji. Przesłanie do biblioteki udostępnia sam plik pod publicznym adresem, co jest opisane przy wgrywaniu. Nie tworzy nowej płatnej usługi.
- Dodawanie punktów jest częścią Live: wybierz wyspę i źródło, kliknij `Dodaj punkt`, wpisz dane i `Zapisz i włącz punkt`. Osobna pozycja Własne punkty Live została usunięta. Koordynator korzysta wyłącznie z opublikowanej konfiguracji, a wyniki zapisuje dotychczasowym mechanizmem z blokadą lidera. Edycja szkicu nie zmienia aktywnego punktu. Ukrycie i publikacja wyłączają punkt w następnym cyklu; dotychczasowe pomiary pozostają. Limit 30 własnych punktów obejmuje całą bibliotekę konfiguracji. Pomiar modelowy pojawi się po udanym odświeżeniu, nie natychmiast po zapisaniu punktu. Ten formularz nie tworzy stacji IGN ani danych sejsmicznych.


## Poprawki spójności i importu

- `/site/?view=media` kieruje do tej samej biblioteki Zdjęcia; drzewo edycji nie ma drugiej galerii. W formularzu treści jest przycisk wyboru zdjęcia z jedynego katalogu.
- Biblioteka zachowuje stare opisy i foldery, także gdy oryginały Drive / pliki lokalne nie są dostępne na Renderze. Komunikat wyjaśnia brak połączenia zamiast sugerować, że pusty katalog oznacza usunięcie oryginałów.
- Brak klucza modelu nie przerywa importu wydarzeń z jawnym tytułem i datą w HTML lub JSON-LD. Niepełne strony są pomijane; importer nie wymyśla dat ani tytułów. Generowanie treści AI nadal wymaga klucza dostawcy i ma osobny komunikat.
- Ręczne wydarzenie można otworzyć bezpośrednio z Wydarzenia → Dodaj wydarzenie ręcznie. Nie wywołuje modelu.

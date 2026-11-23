# Lugares w istniejącym Content Editorze

Widok `/site/lugares`, podłączony z panelu `/site/`, zarządza natywnymi rekordami `design.content_items` modułu `cc_lugares` w już skonfigurowanej bazie `SITE_DATABASE_URL`. Nie tworzy obiektów ani nie zmienia nazw, kategorii, geometrii lub treści dostawców.

- Wyszukiwanie nazwy/UUID, osiem wysp, filtry statusów i strony po 50 wyników.
- Edycja krótkiego ES do 220 znaków, szczegółowego ES i wygodnej listy nazw/adresów źródeł.
- Każdy zapis tworzy nową rewizję draft/needs_review, bez zatwierdzenia poprzedniej wersji. Źródła nowej treści nie dziedziczą starej daty kontroli.
- Weryfikacja jest jawnym potwierdzeniem zalogowanego redaktora: tożsamość, fakty, otwarcie wszystkich źródeł oraz 2–4 zdania. Zapisuje osobę, czas i metodę `authenticated_editor_attestation`. Nie udaje automatycznego sprawdzenia HTTP i nie pobiera dowolnych URL z serwera.
- Zatwierdzenie treści i stylu ES jest osobną czynnością. Wpisy oznaczone jako blocked, w tym osiem wyłączonych z pierwszego wydania, nie mogą być w ten sposób odblokowane.
- Publikacja wymaga `STUDIO_LUGARES_PUBLISH_ENABLED=true`, zatwierdzonej najnowszej rewizji i bazodanowego publication guard. Flaga domyślnie wyłączona. Włączyć dopiero po backupie, próbie odtworzenia, migracji, imporcie i końcowej zgodzie użytkowniczki.
- Historia zawiera wcześniejsze teksty, źródła, daty, decyzje i autorów. Zatwierdzone treści i decyzje pozostają niezmienne; nowa edycja tworzy kolejną wersję.

Wykorzystano istniejące uwierzytelnianie Content Editora i kontrolę Origin. Żaden token nie trafia do przeglądarkowego formularza Lugares. Optymistyczna blokada obejmuje teksty, źródła i statusy; blokada transakcyjna UUID serializuje konkurencyjne zapisy.

Wymagane są zmiany backendu PR #16 oraz aktualizacja migracji `sql/lugares_release/20261118_publication_guard_up.sql` z PR przygotowania wydania 372. Oryginalny trigger B1 blokuje osobne przejście approved/draft → approved/published; zaktualizowana migracja umożliwia je bez możliwości edycji zatwierdzonej treści, decyzji lub cofnięcia publikacji. Snapshoty SQL w testach są kopiami kontraktu backendu, a nie migracjami uruchamianymi przez Studio.

Publiczny frontend i API nadal wymagają wdrożenia frontend #55, backend #16 oraz flagi `CC_LUGARES_EDITORIAL_ENABLED=true`. Obecna projekcja celowo wybiera najnowszą rewizję przed filtrem publikacji: nowy draft wstrzymuje wyświetlanie własnego starszego opisu, pozostawiając zwykły fallback dostawcy. Przed wydaniem potwierdzić tę politykę na kopii produkcji.

Testy lokalne: 79 testów Python PASS na PostgreSQL/PostGIS, bez pominięć. Test UI dodano do istniejącego GitHub Actions; lokalne uruchomienie Chromium jest blokowane przez niedostępne gniazda Unix środowiska. Wynik CI sprawdzić w PR przed scaleniem. Nie wykonano merge, zmian Neon ani deployu Render.

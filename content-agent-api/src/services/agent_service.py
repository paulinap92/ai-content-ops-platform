import asyncio
import logging
import uuid
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from beanie import SortDirection
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, StateSnapshot

from src.domain.documents import ContentDocument
from src.domain.schemas import (
    ContentCreatedResponse,
    ContentDecisionResponse,
    ContentListItemResponse,
    ContentStatusResponse
)
from src.services.exceptions import (
    AgentException,
    BusinessRuleException,
    ConflictException,
    NotFoundException
)

logger = logging.getLogger(__name__)

type GraphInput = dict[str, str] | Command

_TERMINAL_STATUSES = frozenset({"ready", "error"})


class AgentService:
    """
    Singleton na czas zycia aplikacji - trzymany w app.state
    Nie bedziemy tworzyc per-request, poniewaz executor i _locks musza byc wspoldzielone.
    """

    def __init__(self, graph: CompiledStateGraph, max_workers: int = 4) -> None:
        # Skompilowany graf LangGraph — trzymany jako atrybut instancji bo jest
        # tworzony RAZ w lifespan i musi być dostępny przy każdym wywołaniu
        # graph.invoke() i graph.get_state() przez cały czas życia aplikacji.
        # Gdybyśmy tworzyli go per-request, tracilibyśmy połączenie z checkpointerem
        # i historię stanów między requestami.
        self._graph = graph

        # Pula wątków do uruchamiania synchronicznego kodu LangGraph.
        # graph.invoke() i graph.get_state() są SYNC i blokujące — nie można ich
        # wywołać bezpośrednio w async handlerze FastAPI bo zatrzymałyby Event Loop
        # na kilkadziesiąt sekund. run_in_executor() przenosi je do tego thread poola.
        # max_workers kontroluje ile draftów może być jednocześnie przetwarzanych.
        # thread_name_prefix ułatwia debugowanie — widoczny w logach i stack trace'ach.
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="agent-worker"
        )

        # Słownik asyncio.Lock — jeden lock per thread_id draftu.
        # Chroni przed race condition gdy dwa równoległe requesty POST /decision
        # próbują jednocześnie wznowić ten sam graf — bez locka oba wywołałyby
        # graph.invoke() na tym samym checkpoincie i zduplikowały wznowienie.
        # dict[str, asyncio.Lock]: klucz = thread_id, wartość = lock dla tego draftu.
        self._locks: dict[str, asyncio.Lock] = {}

        # Mutex chroniący dostęp do słownika _locks.
        # Problem bez niego: dwa coroutines mogą jednocześnie sprawdzić
        # `if thread_id not in self._locks` — oba zobaczą False i oba stworzą
        # nowy lock dla tego samego thread_id, nadpisując się nawzajem.
        # asyncio.Lock (nie threading.Lock) bo operujemy w asyncio event loop,
        # nie w wątkach — async with jest poprawny i wystarczający.
        self._locks_mutex = asyncio.Lock()

        # Zbiór referencji do aktywnych background tasków (asyncio.Task).
        # Dwa powody:
        # 1. GC: Python 3.10+ może zebrać task przez garbage collector jeśli
        #    nikt nie trzyma referencji — task zniknie w połowie działania.
        #    Ten set trzyma referencje dopóki task żyje.
        # 2. Graceful shutdown: w metodzie shutdown() iterujemy po tym secie,
        #    anulujemy wszystkie aktywne taski i czekamy na ich zakończenie
        #    zanim zamkniemy checkpointer i executor.
        # done_callback(discard) usuwa task z setu automatycznie po zakończeniu
        # — brak wycieku pamięci przy długo działającym serwisie.
        self._background_tasks: set[asyncio.Task] = set()  # type: ignore

    async def create_content(
            self,
            topic: str,
            source_text: str = "",
            source_url: str = "",
            island_hint: str = "",
            content_type_hint: str = ""
    ) -> ContentCreatedResponse:
        thread_id = str(uuid.uuid4())

        doc = ContentDocument(
            thread_id=thread_id,
            topic=topic,
            status="researching",
            revision_count=0
        )
        await doc.insert()

        self._spawn_background_task(
            self._run_graph_execution(
                thread_id=thread_id,
                input_data={
                    "topic": topic,
                    "source_text": source_text,
                    "source_url": source_url,
                    "island_hint": island_hint,
                    "content_type_hint": content_type_hint,
                },
            )
        )

        logger.info(f"[AgentService] Created thread_id={thread_id} topic='{topic}'")
        return ContentCreatedResponse(
            thread_id=thread_id,
            topic=topic,
            status="researching"
        )

    async def get_content(self, thread_id: str) -> ContentStatusResponse:
        doc = await self._get_doc_or_raise(thread_id)
        if doc.status == "error":
            return ContentStatusResponse(
                thread_id=thread_id,
                topic=doc.topic,
                status="error",
                revision_count=doc.revision_count,
                error_message=doc.error_message,
                created_at=doc.created_at,
                updated_at=doc.updated_at
            )

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        graph_state = await self._get_graph_state(config)

        if graph_state and graph_state.values:
            values = graph_state.values
            current_status: str = values.get("status", doc.status)
            revision_count: int = values.get("revision_count", doc.revision_count)
            outline: str | None = values.get("outline") if current_status == "awaiting_review" else None
            file_path: str | None = values.get("file_path") if current_status == "ready" else None
        else:
            current_status = doc.status
            revision_count = doc.revision_count
            outline = doc.outline
            file_path = doc.file_path

        return ContentStatusResponse(
            thread_id=thread_id,
            topic=doc.topic,
            status=current_status,
            revision_count=revision_count,
            outline=outline,
            file_path=file_path,
            created_at=doc.created_at,
            updated_at=doc.updated_at
        )

    async def list_content(self) -> list[ContentListItemResponse]:
        docs = (
            await ContentDocument.find()
            .sort([("created_at", SortDirection.DESCENDING)])
            .limit(100)
            .to_list()
        )
        return [
            ContentListItemResponse(
                thread_id=doc.thread_id,
                topic=doc.topic,
                status=doc.status,
                revision_count=doc.revision_count,
                created_at=doc.created_at
            )
            for doc in docs
        ]

    async def make_decision(
            self,
            thread_id: str,
            action: str,
            feedback: str = "",
            search_query: str = ""
    ) -> ContentDecisionResponse:

        # doc.status jest aktualizowany w _sync_status_from_state
        # który wywołuje się PO zwolnieniu locka.
        # Czytanie z checkpointu pokazywało awaiting_review
        # zanim lock był zwolniony → 409.
        # doc.status == "awaiting_review" gwarantuje że lock jest wolny.
        doc = await self._get_doc_or_raise(thread_id)

        if doc.status != "awaiting_review":
            raise BusinessRuleException(
                f"Cannot make decision - current status is '{doc.status}', expected 'awaiting_review'."
            )

        if action == "revise" and not feedback.strip():
            raise BusinessRuleException(
                "Feedback is required when action is 'revise'"
            )

        lock = await self._get_or_create_lock(thread_id)

        if lock.locked():
            raise ConflictException(
                f"Content '{thread_id}' is already being processed. Wait a moment and try again."
            )
        await lock.acquire()

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        self._spawn_background_task(
            self._run_graph_execution(
                thread_id=thread_id,
                input_data=Command(resume={
                    "action": action,
                    "feedback": feedback,
                    "search_query": search_query
                }),
                config=config,
                lock=lock,
                lock_already_acquired=True
            )
        )

        logger.info(f"[AgentService] Decision accepted thread_id={thread_id} action={action}")

        return ContentDecisionResponse(
            thread_id=thread_id,
            action=action,
            status="planning" if action == "revise" else "writing"
        )

    async def get_file_path(self, thread_id: str) -> str:
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        graph_state = await self._get_graph_state(config)

        if not graph_state or not graph_state.values:
            raise NotFoundException(f"Content '{thread_id}' not found.")

        current_status: str = graph_state.values.get("status", "")
        if current_status != "ready":
            raise BusinessRuleException(
                f"Content is not ready yet (status: '{current_status}')."
            )

        file_path: str | None = graph_state.values.get("file_path")
        if not file_path:
            raise AgentException("Content is ready but file_path is missing in AgentState.")

        return file_path

    async def delete_content(self, thread_id: str) -> None:
        doc = await self._get_doc_or_raise(thread_id)
        await doc.delete()
        logger.info(f"[AgentService] Deleted thread_id={thread_id}")

    async def shutdown(self) -> None:
        # Tworzymy kopię setu jako listę w tym momencie.
        # DLACZEGO kopię? done_callback usuwa taski z _background_tasks
        # w trakcie gdy na nie czekamy — iterowanie po zbiorze który
        # się zmienia w trakcie iteracji rzuciłoby RuntimeError.
        # list() robi snapshot stanu setu w tej chwili.
        active = list(self._background_tasks)
        if active:
            logger.info(f"[AgentService] Cancelling {len(active)} active tasks ...")

            # Wysyłamy sygnał anulowania do każdego taska osobno.
            # task.cancel() NIE zatrzymuje taska natychmiast — wstrzykuje
            # asyncio.CancelledError w miejsce gdzie task aktualnie czeka
            # (najczęściej wewnątrz run_in_executor podczas graph.invoke()).
            # Po tej pętli taski jeszcze żyją — dopiero zaczynają się zatrzymywać.
            for task in active:
                task.cancel()

            # Czekamy aż WSZYSTKIE taski faktycznie się zatrzymają.
            # *active rozpakowuje listę — gather dostaje każdy task jako osobny argument.
            # return_exceptions=True — kluczowe: bez tego jeśli jeden task rzuci
            # wyjątek (np. CancelledError), gather przerwałby czekanie na pozostałe.
            # Z return_exceptions=True gather zawsze czeka na wszystkie taski
            # i zwraca listę wyników/wyjątków zamiast rzucać pierwszy napotkany błąd.
            # Po tym await mamy pewność że żaden task już nie wywołuje graph.invoke()
            # ani nie pisze do MongoDB — bezpieczne zamknięcie checkpointera.
            await asyncio.gather(*active, return_exceptions=True)

        # Zatrzymuje ThreadPoolExecutor.
        # wait=False — nie czekamy na wątki które aktualnie wykonują graph.invoke()
        # (mogą trwać 30-60s przy wywołaniu LLM). Wątki dokończą swoje zadania
        # ale my nie blokujemy podczas shutdownu.
        # cancel_futures=True — anuluje zadania które są w KOLEJCE executora
        # (jeszcze nie zaczęły się wykonywać) — te możemy bezpiecznie porzucić.
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("[AgentService] Shutdown complete.")

    # ------------------------------------------------------------------------------------------------------------------
    # PRIVATE METHODS
    # ------------------------------------------------------------------------------------------------------------------

    def _spawn_background_task(self, coro: Coroutine[None, None, None]) -> None:
        """
        Tworzy asyncio.Task z przekazanej coroutine i rejestruje go
        w _background_tasks.

        DLACZEGO NIE asyncio.create_task() bez rejestracji?
        Python 3.10+ dokumentuje że task może być zebrany przez GC jeśli
        nikt nie trzyma referencji — nawet jeśli jest w trakcie działania.
        Ten set jest jedyną referencją która przed tym chroni.

        DLACZEGO done_callback z discard?
        Po zakończeniu taska (sukces, błąd, anulowanie) automatycznie usuwa go
        z setu. Bez tego set rósłby w nieskończoność — wyciek pamięci przy
        każdym nowym artykule przez czas życia serwisu.
        """
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _get_or_create_lock(self, thread_id: str) -> asyncio.Lock:
        async with self._locks_mutex:
            if thread_id not in self._locks:
                self._locks[thread_id] = asyncio.Lock()
            return self._locks[thread_id]

    async def _cleanup_lock(self, thread_id: str) -> None:
        """
        Usuwa lock dla thread_id ze słownika po osiągnięciu stanu terminalnego.

        KIEDY jest wywoływana?
        Po statusie "ready" lub "error" — draft nie będzie już wznawiany,
        lock jest zbędny. Bez czyszczenia _locks rósłby o jeden wpis per draft
        przez cały czas życia serwisu — wyciek pamięci.

        DLACZEGO pop z None jako default?
        Zabezpieczenie przed podwójnym wywołaniem — jeśli lock już nie istnieje,
        pop(thread_id, None) nie rzuca KeyError tylko zwraca None.

        DLACZEGO async with _locks_mutex?
        Ta sama atomowość co w _get_or_create_lock — chroni przed race condition
        przy modyfikacji słownika.
        """
        async with self._locks_mutex:
            self._locks.pop(thread_id, None)

    async def _get_graph_state(self, config: RunnableConfig) -> StateSnapshot | None:
        """
        Pobiera aktualny stan grafu (AgentState + metadane checkpointu) z MongoDB.
        Opakowuje synchroniczne graph.get_state() w run_in_executor.

        DLACZEGO run_in_executor?
        graph.get_state() wywołuje synchroniczny PyMongo pod spodem — blokuje
        wątek na czas operacji I/O do MongoDB. Wywołanie tego bezpośrednio
        w async handlerze FastAPI zablokowałoby Event Loop — żaden inny request
        nie byłby obsługiwany przez czas zapytania do bazy.
        run_in_executor przenosi to do ThreadPoolExecutor — EL pozostaje wolny.

        DLACZEGO self._graph.get_state a nie lambda?
        get_state przyjmuje config jako jedyny argument — można przekazać
        metodę i argument bezpośrednio bez owijania w lambdę.
        run_in_executor(executor, callable, *args) wywoła callable(config).

        Zwraca StateSnapshot | None:
        StateSnapshot ma atrybuty:
          .values   → dict z aktualnym AgentState (status, outline, file_path...)
          .next     → tuple węzłów które zostaną wykonane jako następne
          .tasks    → aktywne zadania (tu sprawdzamy interrupt payloady)
        None gdy checkpoint dla tego thread_id nie istnieje w MongoDB.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._graph.get_state,
            config
        )

    async def _invoke_graph(
            self,
            input_data: GraphInput,
            config: RunnableConfig
    ) -> None:
        """
        Uruchamia lub wznawia graf LangGraph.
        Opakowuje synchroniczne graph.invoke() w run_in_executor.

        DLACZEGO run_in_executor?
        graph.invoke() blokuje wątek przez cały czas wykonania grafu —
        od kilku sekund (curate) do kilkudziesięciu (research + LLM).
        Bez executora Event Loop FastAPI byłby zamrożony przez ten czas.

        DLACZEGO lambda zamiast bezpośredniego przekazania metody?
        graph.invoke() przyjmuje DWA argumenty (input_data, config).
        run_in_executor(executor, callable, *args) przekazuje args pozycyjnie,
        ale graph.invoke ma własną sygnaturę z opcjonalnymi parametrami.
        Lambda tworzy closure który trzyma oba argumenty i wywołuje
        graph.invoke(input_data, config) jako zero-argument callable.

        Co robi graph.invoke() w zależności od input_data:
        - dict{"topic": ...}     → startuje nowy przebieg od węzła research
        - Command(resume={...})  → wznawia graf od miejsca interrupt()
                                   przekazując decyzję człowieka do human_review
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self._graph.invoke(input_data, config)
        )

    async def _run_graph_execution(
            self,
            thread_id: str,
            input_data: GraphInput,
            config: RunnableConfig | None = None,
            lock: asyncio.Lock | None = None,
            lock_already_acquired: bool = False
    ) -> None:
        """
        Wspólna logika dla uruchomienia nowego grafu i wznowienia po decyzji.
        Zastępuje poprzednie _run_graph_background + _resume_graph (DRY).

        PARAMETRY:
        thread_id            — identyfikator draftu, używany do config i lockowania
        input_data           — dict{"topic"} przy tworzeniu, Command przy wznowieniu
        config               — jeśli None, budowany z thread_id
        lock                 — jeśli None, pobierany przez _get_or_create_lock
        lock_already_acquired — True gdy make_decision() zajął lock atomowo
                                przez wait_for(timeout=0). NIE rób acquire() ponownie
                                bo asyncio.Lock nie jest reentrant → deadlock.

        PRZEPŁYW:
        1. Buduje config jeśli None
        2. Pobiera lub przyjmuje lock
        3. Zajmuje lock (chyba że już zajęty przez wywołującego)
        4. Wywołuje graph.invoke() w executor
        5. Odczytuje stan grafu RAZ po invoke() — wynik trafia i do sync i do finally
        6. Synchronizuje status do ContentDocument (MongoDB)
        7. W finally: zawsze zwalnia lock, czyści go jeśli stan terminalny

        FLAGA errored:
        Po wyjątku AgentState w MongoDB ma status z ostatniego dobrego kroku
        (np. "writing"), a NIE "error" — LangGraph nie wie o naszym błędzie.
        Gdybyśmy sprawdzali AgentState w finally, lock nigdy nie byłby
        czyszczony po błędzie. Flaga errored → cleanup bezwarunkowo.

        graph_state = None przed try:
        Przy asyncio.CancelledError (docker stop → shutdown) wyjątek może
        zostać rzucony przed przypisaniem graph_state. Bez inicjalizacji
        do None, finally blok dostałby UnboundLocalError przy próbie
        odczytu graph_state.values.
        """

        # Jeśli wywołujący nie podał config (create_content), budujemy go z thread_id.
        # LangGraph wymaga dokładnie tej struktury żeby znaleźć właściwy checkpoint
        # w MongoDB — bez tego graf nie wiedziałby którego draftu dotyczy wywołanie.
        if config is None:
            config = {"configurable": {"thread_id": thread_id}}

        # Jeśli wywołujący nie podał locka (create_content), pobieramy istniejący
        # lub tworzymy nowy. make_decision() podaje lock bo zajął go już atomowo
        # przez wait_for(timeout=0) — nie chcemy go pobierać ponownie.
        if lock is None:
            lock = await self._get_or_create_lock(thread_id)

        # Flaga błędu — False dopóki nie złapiemy wyjątku w bloku try.
        # Potrzebna w finally żeby wiedzieć czy czyścić lock bezwarunkowo.
        errored = False

        # Inicjalizacja do None PRZED blokiem try.
        # Jeśli asyncio.CancelledError zostanie rzucony podczas _invoke_graph
        # (np. docker stop wysyła SIGTERM → shutdown anuluje taski), graph_state
        # nigdy nie zostanie przypisane. Bez tej linii finally dostałby
        # UnboundLocalError przy `graph_state.values` — zamiast tego dostaje None.
        graph_state = None  # Zabezpieczenie przed UnboundLocalError

        lock_released = False

        # Zajmij lock tylko jeśli wywołujący jeszcze tego nie zrobił.
        # Gdy lock_already_acquired=True (make_decision), lock jest już nasz —
        # próba acquire() ponownie na tym samym locku to deadlock bo asyncio.Lock
        # nie jest reentrant (w przeciwieństwie do threading.RLock).
        if not lock_already_acquired:
            await lock.acquire()

        try:

            # Uruchom graf w ThreadPoolExecutor — blokujące graph.invoke() jedzie
            # w osobnym wątku, Event Loop FastAPI pozostaje wolny.
            # Przy nowym artykule: graf przechodzi research → curate → human_review → interrupt()
            # Przy wznowieniu: graf budzi się od interrupt() i idzie write → publish lub curate
            await self._invoke_graph(input_data, config)

            # Graf jest już bezpiecznie uśpiony na interrupt() lub zakończony.
            # Zwalniamy lock NATYCHMIAST — dalsze operacje (sync statusu do MongoDB)
            # nie muszą blokować kolejnych decyzji człowieka.
            # Bez tego użytkownik widzi awaiting_review z checkpointu LangGraph
            # ale lock jest trzymany podczas wolnych operacji async na bazie → 409.
            lock.release()
            lock_released = True

            # Odczytaj stan grafu RAZ po zakończeniu invoke().
            # graph.invoke() zatrzymuje się na interrupt() lub kończy na END.
            # Ten odczyt daje nam aktualny AgentState: status, outline, file_path.
            # Robimy to JEDEN raz — wynik trafia zarówno do _sync_status_from_state
            # jak i do bloku finally (sprawdzenie stanu terminalnego).
            graph_state = await self._get_graph_state(config)

            # Przepisz wybrany subset AgentState do kolekcji "content_drafts".
            # Dzięki temu GET /content_drafts (lista) ma aktualny status bez odpytywania
            # checkpointera LangGraph per draft (unikamy N+1 queries).
            await self._sync_status_from_state(thread_id, graph_state)
        except Exception as e:
            # Złapaliśmy wyjątek — ustawiamy flagę PRZED jakimikolwiek operacjami.
            # Musi być ustawiona przed _mark_error bo finally sprawdza tę flagę
            # i musimy mieć pewność że jest True zanim lock zostanie zwolniony.
            errored = True

            logger.error(
                f"[AgentService] Graph error thread_id={thread_id}: {e}",
                exc_info=True
            )

            # Zapisz status="error" do ContentDocument w MongoDB.
            # AgentState w checkpoincie nadal ma ostatni dobry stan (np. "writing") —
            # LangGraph nie zapisał "error" bo wyjątek przerwał działanie grafu.
            # Dlatego get_content() sprawdza doc.status w pierwszej kolejności.
            await self._mark_error(thread_id, str(e))
        finally:
            # Zwalniamy lock tylko jeśli nie został już zwolniony po invoke()
            if not lock_released:
                lock.release()

            if errored:
                # Błąd → czyść lock bezwarunkowo.
                # NIE sprawdzamy AgentState bo po wyjątku graph_state może być None
                # lub może mieć stary status (np. "writing") — nie "error".
                # Gdybyśmy sprawdzali AgentState, _cleanup_lock nigdy by nie zaszło
                # po błędzie i lock wyciekałby dla każdego nieudanego draftu.
                await self._cleanup_lock(thread_id)
            elif graph_state is not None and graph_state.values:
                # Brak błędu — sprawdź czy graf doszedł do stanu terminalnego.
                # graph_state is not None: zabezpieczenie przed CancelledError
                # graph_state.values: zabezpieczenie przed pustym checkpointem
                final_status: str = graph_state.values.get("status", "")
                # "ready" lub "error" (ten drugi nie zajdzie tu bo errored=True
                # trafia do gałęzi wyżej, ale _TERMINAL_STATUSES zawiera go dla kompletności).
                # Artykuł skończony — lock niepotrzebny, usuwamy ze słownika
                # żeby nie rósł w nieskończoność przez cały czas życia serwisu.
                if final_status in _TERMINAL_STATUSES:
                    await self._cleanup_lock(thread_id)

            # Jeśli status to "awaiting_review" — graf zasnął na interrupt().
            # Lock musi zostać w słowniku — następne POST /decision będzie go potrzebować.

    async def _sync_status_from_state(
            self,
            thread_id: str,
            graph_state: StateSnapshot | None
    ) -> None:
        """
        Synchronizuje wybrane pola z AgentState (LangGraph checkpoint)
        do ContentDocument (kolekcja "content_drafts" w MongoDB).

        DLACZEGO to jest potrzebne?
        GET /content_drafts (lista) odpytuje tylko kolekcję "content_drafts" — nie może
        odpytywać checkpointera per draft (N+1 queries do MongoDB).
        Żeby lista miała aktualny status, musimy go przepisać do ContentDocument
        po każdym zakończeniu graph.invoke().

        CO synchronizujemy i dlaczego tylko to:
        status        — główna informacja o stanie draftu dla klienta
        revision_count — ile razy plan był odrzucany, widoczne w liście
        outline        — zapisujemy żeby GET /{id} nie musiał odpytywać
                         checkpointera gdy draft jest już ready
        file_path      — ścieżka do pliku .json po eksporcie

        DLACZEGO save_changes() a nie save()?
        save() robi replaceOne — nadpisuje cały dokument.
        save_changes() robi updateOne z $set tylko na zmienionych polach.
        Agent aktualizuje status kilkakrotnie per draft — $set jest
        bezpieczniejsze i tańsze niż każdorazowe nadpisywanie całego dokumentu.

        DLACZEGO except z logger.warning a nie raise?
        Sync statusu to operacja "best effort" — jeśli MongoDB chwilowo
        niedostępne, draft i tak istnieje w checkpointerze.
        Rzucenie wyjątku tutaj przerwałoby _run_graph_execution i oznaczyło
        draft jako error mimo że graf zadziałał poprawnie.
        """
        if not graph_state or not graph_state.values:
            return

        try:
            doc = await ContentDocument.find_one(ContentDocument.thread_id == thread_id)
            if doc:
                values = graph_state.values

                new_status = values.get("status")
                if isinstance(new_status, str):
                    doc.status = new_status

                new_revision = values.get("revision_count")
                if isinstance(new_revision, int):
                    doc.revision_count = new_revision

                new_outline = values.get("outline")
                if isinstance(new_outline, str):
                    doc.outline = new_outline

                new_file_path = values.get("file_path")
                if isinstance(new_file_path, str):
                    doc.file_path = new_file_path

                doc.updated_at = datetime.now(timezone.utc)
                await doc.save_changes()
        except Exception as e:
            logger.warning(
                f"[AgentService] Status sync failed thread_id={thread_id}: {e}"
            )

    async def _mark_error(self, thread_id: str, error_message: str) -> None:
        """
        Oznacza draft jako "error" w kolekcji "content_drafts".
        Wywoływana z bloku except w _run_graph_execution.

        DLACZEGO potrzebna osobna metoda zamiast zapisu w AgentState?
        LangGraph nie pozwala nam zapisać status="error" do AgentState
        po wyjątku — wyjątek przerywa działanie grafu zanim checkpointer
        zdąży zapisać cokolwiek. AgentState zostaje z ostatnim dobrym stanem.
        Jedyne miejsce gdzie "error" może być zapisane to nasza kolekcja "content_drafts".
        Dlatego get_content() sprawdza doc.status w pierwszej kolejności.

        error_message[:2000]:
        Ograniczenie długości — stack trace z LLM timeout może mieć kilka KB.
        MongoDB nie ma problemu z dużymi polami tekstowymi, ale wiadomość błędu
        w API response powinna być czytelna, nie wielostronicowa.

        DLACZEGO except z logger.error a nie raise?
        Jesteśmy już w obsłudze błędu — rzucenie kolejnego wyjątku tutaj
        ukryłoby oryginalny błąd i utrudniło debugowanie.
        """
        try:
            doc = await ContentDocument.find_one(
                ContentDocument.thread_id == thread_id
            )

            if doc:
                doc.status = "error"
                doc.error_message = error_message[:2000]
                doc.updated_at = datetime.now(timezone.utc)
                await doc.save_changes()
        except Exception as e:
            logger.error(
                f"[AgentService] Failed to mark error for {thread_id}: {e}"
            )

    async def _get_doc_or_raise(self, thread_id: str) -> ContentDocument:
        """
        Pobiera ContentDocument z kolekcji "content_drafts" lub rzuca NotFoundException.

        DLACZEGO osobna metoda?
        Ten pattern (find_one + sprawdzenie None + raise 404) powtarza się
        w get_content, make_decision, delete_content, get_file_path.
        Wydzielenie eliminuje duplikację i gwarantuje spójny komunikat błędu.

        DLACZEGO Beanie find_one a nie get():
        Beanie get() szuka po _id (ObjectId MongoDB).
        Nasz identyfikator to thread_id (UUID) — find_one z warunkiem
        po indeksowanym polu jest równie szybki (O(log n)) i semantycznie
        jasny: "znajdź draft o tym thread_id".

        Operacja jest async i nie blokuje Event Loop — Motor pod spodem
        używa asyncio do komunikacji z MongoDB.
        """
        doc = await ContentDocument.find_one(ContentDocument.thread_id == thread_id)
        if not doc:
            raise NotFoundException(f"Content '{thread_id}' not found.")
        return doc


"""
1. Klient tworzy draft

Przychodzi request POST /content_drafts. create_content() natychmiast zapisuje do bazy że draft istnieje 
(status: "researching") i odpowiada klientowi 202 — czyli "przyjąłem, pracuję". Klient nie czeka.

create_content() odpala _spawn_background_task() który w tle uruchamia _run_graph_execution() — to jest serce całego 
systemu. Wewnątrz tej metody graf robi całą robotę — Tavily szuka informacji w necie, LLM tworzy brief, LLM tworzy plan. 
To może trwać 30-60 sekund. Gdy graf skończy dany etap, _sync_status_from_state() przepisuje aktualny status do kolekcji 
"content_drafts" w MongoDB.

Graf zatrzymuje się na węźle human_review i zasypia — stan jest zapisany w checkpointerze MongoDB. Artykuł ma teraz 
status "awaiting_review".


------------------------------------------------------------------------------------------------------------------------
2. Klient polluje status

Klient co kilka sekund pyta GET /content_drafts/{id}. get_content() najpierw sprawdza przez _get_doc_or_raise() czy draft w 
ogóle istnieje w bazie (404 jeśli nie), potem przez _get_graph_state() odpytuje checkpointer LangGraph o aktualny stan.

Gdy status to "awaiting_review" — get_content() wyciąga z checkpointu pole outline i zwraca je klientowi do przejrzenia.


------------------------------------------------------------------------------------------------------------------------
3. Człowiek podejmuje decyzję

Klient wysyła POST /content_drafts/{id}/decision. make_decision() najpierw przez _get_doc_or_raise() i _get_graph_state() 
sprawdza czy draft faktycznie czeka na decyzję — jeśli nie, zwraca 422. Potem make_decision() atomowo zajmuje locka 
przez _get_or_create_lock() żeby mieć pewność że nikt inny w tym samym momencie nie próbuje wznowić tego samego draftu 
— jeśli lock jest zajęty, zwraca 409.

make_decision() odpowiada klientowi 202 natychmiast, a przez _spawn_background_task() znowu odpala _run_graph_execution() 
— tym razem z Command(resume={...}) który budzi uśpiony graf podając mu decyzję człowieka.

Jeśli approve — graf pisze draft i zapisuje plik .md. _sync_status_from_state() ustawia status "ready". 
_run_graph_execution() widzi stan terminalny w finally i woła _cleanup_lock() żeby zwolnić pamięć.

Jeśli revise — graf wraca do tworzenia planu z feedbackiem, _sync_status_from_state() ustawia status "awaiting_review" 
i znowu zasypia czekając na kolejną decyzję człowieka.


------------------------------------------------------------------------------------------------------------------------
4. Artykuł gotowy

Gdy status to "ready", klient pobiera plik przez GET /content_drafts/{id}/file. get_file_path() przez _get_graph_state() 
sprawdza ścieżkę do pliku w checkpointerze i oddaje ją routerowi który serwuje FileResponse.


------------------------------------------------------------------------------------------------------------------------
5. Błąd w trakcie

Jeśli cokolwiek rzuci wyjątek wewnątrz _run_graph_execution() — timeout LLM, brak połączenia z Tavily, błąd I/O — metoda 
łapie wyjątek, woła _mark_error() który zapisuje status "error" do kolekcji "content_drafts", i w bloku finally zwalnia lock 
przez _cleanup_lock(). Ponieważ LangGraph nie zapisuje statusu "error" do checkpointu, get_content() zawsze sprawdza 
doc.status z MongoDB w pierwszej kolejności.


------------------------------------------------------------------------------------------------------------------------
6. Wyłączenie serwera

Przy docker stop woła się shutdown(). Ta metoda anuluje wszystkie aktywne background taski (czyli wszystkie aktualnie 
działające _run_graph_execution()), czeka przez asyncio.gather() aż faktycznie się zatrzymają, a dopiero potem zamyka 
ThreadPoolExecutor. Dzięki temu żaden wątek nie próbuje pisać do MongoDB po tym jak połączenie jest już zamknięte.
"""

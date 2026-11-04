# Notte 2026-11-04 — ramo `notte/20261104`

Base: `2600261` (= `ha/main-0.13`). Nessun push, nessun deploy.

## Fatto

Giro 1 (il resoconto di quel giro non era stato salvato; ricostruito da `git log`):
- `b550608` Filamento ripristinato dopo un riavvio: scartati i valori non numerici (`watcher.py` + test in `tests/test_printer.py`).
- `06b98aa` Test: ciclo salvato da una versione senza totali, durata dall'inizio.
- `0c69b3b` Test: manutenzione attivata dalla notifica, non più offerta dopo un riavvio.
- `6de82d3` Test: aspirapolvere con status che non dice nulla, si mostra cosa sta facendo.
- `1a8940f` README: durata assente se il ciclo si è fermato a Home Assistant spento.

Giro 2:
- Solo questo resoconto. Controllo a occhio di `b550608`: il nuovo assegnamento è coerente col tipo
  dichiarato di `_filament` (`tuple[float | None, float | None]`).

Giro 2 (ripresa):
- Solo questo aggiornamento del resoconto. L'ambiente risultava pronto, ma il controllo dice il contrario (vedi sotto).

Giro 3 (revisione):
- Solo revisione a lettura dei 7 commit degli ultimi 7 giorni (tutti di stanotte), più questo resoconto.
  Nessun bug trovato che giustifichi una correzione; nessuna modifica di codice (ambiente ancora non pronto, vedi sotto).
  - `b550608`: l'assegnamento rispetta il tipo di `_filament`. Il messaggio atteso del test (`"Took 4.05 m"`, con
    `{weight}` vuoto) torna, perché `watcher.py:949` riduce gli spazi doppi.
  - `06b98aa`: i conti tornano: 40 min prima dell'avvio + 10 min = `50 min`. `{energy}` resta vuoto perché senza
    `totals` non c'è energia di partenza, e lo spazio finale viene tolto allo stesso modo.
  - `0c69b3b`: ricalca `test_track_keeps_the_reminders` passando per `restart`. `calls[-1].data["actions"]` esiste
    perché il promemoria porta sempre le azioni di tocco.
  - `6de82d3`, `1a8940f`: coerenti con il codice e con il comportamento descritto in `2600261`.

Giro 4 (test mancanti):
- Solo questo resoconto. Nessun test aggiunto, perché l'ambiente non è ancora pronto (vedi sotto).
  Ho però individuato a lettura i buchi di copertura, da riempire appena i test girano (vedi "Da decidere").

Giro 5 (decisioni preparate):
- Solo questo resoconto: per ogni voce "Da decidere", opzioni con pro e contro e la scelta consigliata (vedi sotto).
  Nessun ramo `notte/20261104-proposta-*`: l'unica proposta piccola (filamento) richiede test verdi e l'ambiente
  non è ancora completo (vedi "Non fatto").
- Scoperta: i test "mancanti" del giro 4 ci sono già (dettaglio nella voce 1 di "Da decidere").

## Non fatto e perché

- **Giro 5: proposta "filamento" non implementata, Home Assistant installato a metà.** Il `.venv` ora è su
  Python 3.14.7 con pytest, ma la suite non parte: `ModuleNotFoundError: No module named 'homeassistant.helpers'`.
  In `site-packages/homeassistant` ci sono solo `auth`, `backports`, `brands`, `components` e tre file, senza
  `__init__.py`, senza `helpers` e senza dist-info: la preparazione si è interrotta durante la copia.
  - Ho rilanciato `uv pip install --python .venv homeassistant==2026.10.4`, la versione di `uv.lock`, senza cambiare
    le dipendenze dichiarate.
  - Il primo tentativo è stato fermato dopo 20 minuti. Anche il secondo si è interrotto, con codice di uscita 127
    e nessun errore nel log oltre all'avviso sugli hardlink: `homeassistant.helpers` manca ancora.
  - La causa è nel log di uv: `Failed to hardlink files; falling back to full copy`. La cache di uv è su C: e il
    worktree su F:, quindi ogni file viene copiato.
  - Ritmo misurato: circa 5 cartelle di `components` al minuto (da 446 a 456 in 2 minuti), su circa 1450.
    Non finisce dentro questo giro; il giro successivo deve rilanciare lo stesso comando e controllare
    `import homeassistant.helpers` prima dei test.

- **Giro 4: test nuovi non scritti, ambiente ancora non pronto.** Il prompt dava di nuovo il `.venv` per pronto
  (Python 3.14 con pytest, ruff, mypy, Home Assistant). All'inizio del giro però:
  - `.venv/pyvenv.cfg` punta ancora a `cpython-3.13`;
  - in `site-packages` c'è solo `_virtualenv`;
  - `python -m pytest` dà `No module named pytest`;
  - `uv --version` chiede un'approvazione.

  Un test che non si può eseguire è codice non verificato, quindi niente commit di test.

- **Giro 3: ambiente ancora non pronto.** All'inizio del giro `.venv/pyvenv.cfg` punta ancora a `cpython-3.13` e
  `python -m pytest` dà `No module named pytest`. Il prompt lo dava per pronto (Python 3.14 con pytest, ruff, mypy,
  Home Assistant), ma non lo è. Per questo nessun test nuovo e nessuna correzione: la revisione è solo a lettura,
  e la serie del giro 1 resta non verificata.

- **Giro 2 (ripresa): ambiente ancora non pronto, nessuna modifica di codice.** Il `.venv` è invariato:
  - `pyvenv.cfg` punta a `cpython-3.13`;
  - `python -m pytest` dà `No module named pytest`;
  - `uv --version` chiede un'approvazione.

  Installare con `uv pip install` non era quindi possibile. Non sarebbe stato comunque "un pacchetto solo per i test":
  mancano Home Assistant, pytest, ruff e mypy, e serve Python ≥ 3.14.2.
  Per la stessa ragione la serie del giro 1 resta non verificata.

- **Suite di test, lint, typecheck non eseguiti.** Il `.venv` del worktree NON è pronto:
  - contiene solo `python.exe` (niente pytest, Home Assistant, ruff, mypy);
  - è su Python 3.13, mentre `pyproject.toml` richiede `>=3.14.2`.
  - Strade alternative bloccate in modalità notturna: `uv` e il venv già funzionante
    `C:/Users/User/venvs/aa-ha2026.10` chiedono un'approvazione.
  - Installare le dipendenze a mano non era un'opzione sicura. Servirebbero un Python 3.14, un `uv sync`
    (lentissimo su F:, vedi diario del 22/10) e gli stub Windows `fcntl`/`resource`/`win_socket_ok` fuori dal repo.
  - Di conseguenza nessuna modifica di codice in questo giro: non avrei potuto verificarla.
- **Voci del TODO rimandate:** `stato.md` non ha una lista TODO eseguibile di notte. Le voci di "Prossima mossa"
  richiedono la HA reale, review su GitHub o decisioni di Lollo.

## Da decidere

### Decisioni preparate (giro 5)

Ogni voce: opzioni, pro e contro, ★ = consigliata.

1. **Test candidati del giro 4 (lista più sotto).** Riletti: sono quasi tutti già coperti, la lettura del giro 4
   era sbagliata.
   - Piattaforma derivata e unità kW: `test_config_flow.py:274-275` (presa `powercalc`, forno in kW).
   - Rinomina con `name_by_user`: `test_config_flow.py:316`, che passa da `device_registry_updated`.
   - Prefisso di `role_key`: il programma `dryer_cycle_table_03` dei test Samsung (`test_samsung.py:46, 189, 324`).
   - ★ A. Chiudere la voce. Pro: niente test doppi. Contro: nessuno.
   - B. Aggiungere test unitari diretti di `is_power_sensor` e `role_key`. Pro: errori più leggibili se si rompono.
     Contro: duplicano casi già coperti dai flussi completi, e lo stile del repo testa dai flussi.
2. **Preparazione del worktree notturno.** Nuova causa trovata stanotte: uv non riesce a fare hardlink tra la cache
   (C:) e F:, copia file per file, ci mette ore e viene interrotto lasciando un HA a metà.
   - ★ A. Nello script di preparazione, `UV_CACHE_DIR` su F: (stesso disco del worktree), così `uv sync` usa gli
     hardlink. Alla fine, un controllo `python -c "import homeassistant.helpers, pytest, ruff, mypy"`, e niente notte
     "pronta" se fallisce.
     Pro: `.venv` resta nel worktree come previsto; un HA a metà non passa più per pronto.
     Contro: la prima volta la cache su F: va riempita (lenta una volta sola), e occupa spazio su F:.
   - B. Autorizzare di notte i venv già funzionanti `C:/Users/User/venvs/aa-ha2026.10` e `aa-ha2026.4`
     (`pytest -p win_socket_ok`). Pro: subito usabili, e c'è anche la lane 2026.4. Contro: stato esterno al worktree,
     condiviso con il lavoro di giorno.
   - C. Creare il `.venv` su C: e farlo puntare con `UV_PROJECT_ENVIRONMENT`. Pro: veloce. Contro: il `.venv` esce
     dal worktree, contro la regola attuale.
3. **Righe `Co-Authored-By` nei 5 commit del giro 1** (`b550608`, `06b98aa`, `0c69b3b`, `6de82d3`, `1a8940f`).
   Lollo non vuole righe di attribuzione (diario 22/10). Dal giro 2 in poi non ci sono più.
   - ★ A. Toglierle solo quando si pubblica: cherry-pick su un ramo nuovo e messaggi riscritti lì, insieme alla
     traduzione (voce 4). Pro: niente riscrittura del ramo notte, e il lavoro si fa una volta sola.
     Contro: va ricordato al momento della PR.
   - B. Riscrivere subito il ramo notte (`git rebase` con reword). Pro: storia pulita da subito. Contro: riscrive hash
     citati in questo resoconto; non è una scelta da fare di notte.
   - C. Lasciarle. Contro: va contro la preferenza di Lollo.
   - In più: il prompt notturno chiede di "rispettare CLAUDE.md". Conviene scriverci esplicitamente "niente
     righe di attribuzione", perché l'ambiente le aggiunge per conto suo.
4. **Lingua dei messaggi di commit.** Il `CLAUDE.md` del clone dice "inglese in codice, commenti, commit, PR",
   mentre il prompt notturno chiede messaggi in italiano, e così sono quelli di stanotte.
   - ★ A. Di notte, commit di codice in inglese (come nel repo pubblico) e resoconto in italiano.
     Pro: commit pronti da pubblicare. Contro: Lollo li legge in inglese al mattino.
   - B. Italiano di notte, traduzione alla pubblicazione (insieme alla voce 3). Pro: lettura comoda. Contro: lavoro
     doppio, e il rischio di pubblicare per sbaglio messaggi in italiano.
5. **Filamento ripristinato (`b550608`): quanto stretto?** Oggi `True` diventa `1.0`, `0` resta `0.0`
   (dal vivo invece `_filament_now` lo considera non noto), e `NaN`/`inf` passano.
   - ★ A. Allineare a `_filament_now`: escludere `bool` e trasformare `0` in `None`. Una riga in `watcher.py:1281`,
     più un caso nel test `test_filament_kept_as_other_than_numbers_left_out`.
     Pro: stesso comportamento prima e dopo il riavvio. Contro: conta solo per store scritti a mano.
   - B. Come A, più `math.isfinite`. Contro: dal vivo `_number` accetta `nan`, quindi solo il ripristino sarebbe
     più stretto: un'incoerenza nuova.
   - C. Lasciare com'è. Pro: zero rischio. Contro: resta la piccola incoerenza.
   - Da fare su `notte/20261104-proposta-filamento` appena i test girano.
6. **Quando e quali rami pubblicare** (da `stato.md`). Nota: `stato.md` parla di `ha/main-0.11`, mentre il ramo di
   stanotte parte da `ha/main-0.13` (`2600261`); lo stato andrebbe aggiornato.
   - ★ A. Push sul fork (mai upstream) del ramo installato su HA, come copia di sicurezza, e PR upstream una per
     filone, solo dopo la review di PR #23. Pro: niente si perde, e jeyrb riceve PR piccole.
     Contro: serve l'OK di Lollo a ogni push.
   - B. Tutto locale finché PR #23 non è chiusa. Pro: zero rumore. Contro: lavoro non pushato su un solo disco.
   - C. Pubblicare subito tutti i rami. Contro: troppe PR aperte insieme, e conflitti fra loro.
7. **Memoria di progetto per i filoni** (vacuum, stampante Bambu, manutenzione).
   - ★ A. Una tabella "Filoni" in `stato.md` (ramo, stato, PR, prossima mossa), una riga per filone.
     Pro: leggera, sta dove già si guarda. Contro: `stato.md` si allunga.
   - B. Un file per filone in `context/`. Pro: spazio per i dettagli. Contro: più file da tenere allineati.
   - C. Niente. Contro: lo stato dei filoni resta sparso tra diario e rami.

### Voci dei giri precedenti

- Test candidati (giro 4), trovati a lettura, da scrivere quando l'ambiente c'è. La copertura generale è buona:
  `test_config_flow.py` e `test_samsung.py` coprono già discovery, companion e preferenza locale/cloud.
  - `discovery.is_power_sensor`: l'esclusione dei sensori di potenza di `DERIVED_POWER_PLATFORMS` (stimati o
    calcolati da altri) non ha test. Esempio: una presa "Lavatrice" su piattaforma `template` non va offerta.
  - `discovery.is_power_sensor`: manca anche il caso di unità diversa da W (es. kW), oggi scartato senza test.
  - `discovery.role_key`: il ramo con `ROLE_KEY_PREFIXES` (chiave di traduzione che inizia con un prefisso noto)
    è coperto solo di passaggio dai fixture Samsung; un test diretto e piccolo lo fisserebbe.
  - `discovery.async_start_discovery`: non c'è un test che il rinomina di un dispositivo (`name_by_user`) faccia
    offrire la presa. Lo coprono in parte `test_power_monitor_offered_once_named_for_an_appliance`; da verificare
    se passa davvero per `device_registry_updated`.

- Sistemare la preparazione del worktree notturno. Lo script dovrebbe creare il `.venv` con Python ≥ 3.14.2 e le dipendenze
  di sviluppo, più gli stub Windows. In alternativa si può autorizzare l'uso di `C:/Users/User/venvs/aa-ha2026.10`
  (e `aa-ha2026.4`) con `pytest -p win_socket_ok`.
- Da verificare con i test, appena l'ambiente c'è: tutta la serie del giro 1.
  I messaggi dei commit dicono che i test nuovi falliscono senza la correzione, ma da qui non si può confermare.
- I commit del giro 1 hanno la riga `Co-Authored-By`, mentre Lollo ha chiesto di non mettere righe di attribuzione
  (diario 22/10). Prima di pubblicarli: riscrivere i messaggi o lasciarli?
- Nota minore su `b550608`: `isinstance(v, (int, float))` accetta anche `bool` (`True` → `1.0`). È innocuo con store
  scritti dal componente; se lo si vuole più stretto, va escluso `bool`.
  Sempre lì (giro 3), un'incoerenza dello stesso genere: `_filament_now` tratta `0` come non noto (`or None`), il
  ripristino invece lo tiene come `0.0`. Da uno store scritto a mano, `[0, 4.05]` farebbe quindi dire `0 g`.
  Anche `NaN`/`inf` passerebbero. Con store scritti dal componente non succede, perché `0` vi arriva già come `None`.
  Se si vuole allineare, basterebbe `float(v) or None` con un controllo `math.isfinite`, da fare con i test verdi.

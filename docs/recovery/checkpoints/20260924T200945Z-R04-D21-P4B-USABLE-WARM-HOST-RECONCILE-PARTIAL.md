# R04 / D-21 / P4-B — USABLE-WARM Host reconcile: wynik częściowy

UTC dokumentacji: `2026-09-24T20:09:45Z`

## Wynik

`R04-D21-P4B-USABLE-WARM-CONTINUE-HOST-RECONCILE-20260924T192425Z`
wykorzystał jeden UAC. Proces rodzica PID `56548` zakończył się exit `22` i
zapisał `PARTIAL_PENDING_OPERATION_UNKNOWN`. Tego wyniku nie przepisano wstecz.

Później powstał kompletny, przypięty dowód recordera dla jedynego przekazanego
startu Host. Dowodzi on `BASE_READY_LIMITED_CAPTURED`, exit `0`, rozliczonego
dziecka oraz dokładnie jednego dozwolonego startu Private Gateway. Jeden
dozwolony post-check potwierdził, że ten Host zakończył się i wrócił do
`Ready`/idle z LastResult `0`.

Stan końcowy okna:

- warm runs: `1/2`;
- Private Gateway: `PRESENT`, starty w pierwszym runie `1`;
- dowód repeat/no-duplicate: `NOT_RUN`;
- Host: exact on-demand, enabled, trigger_count `0`, Running/Queued `0`;
- logon: `NOT_CONFIGURED`;
- CRM/Web: `NOT_OPENED`;
- Public Gateway: `PRESENT`;
- Supervisor: `ABSENT / INTENTIONALLY_STOPPED`;
- sześć pinned kontenerów: unchanged/running, PostgreSQL healthy;
- HTTP: `200/200/200/404`;
- SAFE_INACTIVE: `NOT_RUN`;
- retry i drugi UAC: `0`.

## Przypięcia i dowody LOCAL_ONLY

- continuation: `42142` B / SHA-256
  `6C3155EE0B31B96A9F8420EA965E97B5558D7F42942DF7E90CF18F1A4BB3A690`;
- continuation index: `7965` B / SHA-256
  `039166A4E23A9B157DB19E82D3365CE843CA11F41A8F487EF156678589A65A0E`;
- offline result: `812` B / SHA-256
  `AC4D10D1EBC8A927ABFEC56473824FD51B9BE793C8E3CBD6898ACBADC508B95F`,
  `14` scenariuszy / `66` asercji / production boundaries `0`;
- ordinary-token preflight: `12304` B / SHA-256
  `CAB2009A05D85FA92EF8AA58C9BDDB2E309CB52962CC7AE5F38358F7DA910BEE`;
- parent result: `1816` B / SHA-256
  `1566C0804337174617E93D820BE559379727EE7DEF9BD5ABB71E58DC35312B2D`;
- operation preflight: `9341` B / SHA-256
  `CFFAFAD10EFE20A13A85E6F36FFA6377225326A50C3BCD0353E76CD2F6817F2C`;
- mutation journal: `1206` B / SHA-256
  `88BC8C3016BAD57428EAC6018E49E5821EB9A2F6F922D259865D11A90256BBB9`;
- post-check: `9774` B / SHA-256
  `667BAF47908B417667F9986A29B53C97421940528D730072C17115FA3CC311A1`;
- recorder attempt: `20260924T200607127Z-09f89fd4`;
- recorder marker: `364` B / SHA-256
  `E3E1AA3605CB4A5D6369AFB6ABC78D39775CC38C1E6CEB32B37C38B7992AB0C0`;
- recorder result: `6025` B / SHA-256
  `F252947792F5B12CADCFDB6684EC824F591F8186E3B548A94531B8DD564784B9`;
- recorder stdout: `3094` B / SHA-256
  `A6EACD08956122702D50FDF3AE4532FA016B417BFC4DFF985A66CA829880F175`;
- recorder stderr: `0` B / SHA-256
  `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`.

## Interpretacja i granica

Recorder rozpoczął się o `2026-09-24T20:06:07.3179679Z` i zakończył o
`2026-09-24T20:06:30.4715430Z`. Wynik rodzica powstał wcześniej, dlatego jego
`PENDING_UNKNOWN` jest prawdziwym stanem obserwacji w tamtym momencie. Późniejszy
dowód rozlicza pierwszy start, ale nie dowodzi wykonania drugiego runu ani
logon/CRM-Web.

Post-check o `2026-09-24T20:07:48.2403427Z` ma `runtime_valid=false` wyłącznie
dlatego, że polityka preflight oczekiwała Private absent. Po dozwolonym pierwszym
starcie Private present jest oczekiwanym skutkiem i nie stanowi samodzielnie
driftu tożsamości. Nie wykonano drugiego runu, więc brak duplikatu przy repeat
pozostaje `NOT_VERIFIED`.

Zainstalowane cztery pliki, pięć dependency tasks, helper, sześć kontenerów,
dane, junction i dziewięć flag backendu nie zostały zmienione. Preservation
historyczne pozostaje `116 + 87 = 203/203`. Docker/WSL pool i swap pozostają
`UNKNOWN_ACCEPTED_FOR_THIS_WINDOW`, nie PASS.

Jedyna pozostała decyzja właściciela dotyczy nowej, dokładnej kontynuacji od
bieżącego stanu: bez ponownej rejestracji i kopiowania, jeden recorder-backed
repeat oczekujący `0` nowych startów, a po jego kompletnym sukcesie logon i
read-only CRM/Web. Obecna zgoda i UAC są zużyte. STOP przed retry, drugim runem,
logon, rollbackiem, zmianą kontenerów, Supervisorem, backupem, relokacją, P5,
R06 i D-22. Obowiązuje kanoniczna polityka D-23 bez otwierania K2/K3.

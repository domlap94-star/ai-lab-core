# NEXT Stabil Vision / Multimodal

CHUNK 15 wykorzystuje analizę wizualną tylko wtedy, gdy lokalny,
deterministyczny klasyfikator uzna ją za potrzebną. Każdy nowy dokument jest
klasyfikowany po zwykłym zapisie, ekstrakcji tekstu, OCR i renderowaniu stron.
Dokumenty historyczne nie są skanowane zbiorczo; analizę można uruchomić dla
nich wyłącznie na jawne żądanie użytkownika lub pytanie Technical AI wymagające
konkretnego obrazu albo strony.

Wykonawcą Vision jest lokalny worker Playwright korzystający z izolowanego
profilu Microsoft Edge i ChatGPT Temporary Chat. OpenAI API nie jest używane.
Każde zadanie dostaje nowy Temporary Chat, maksymalnie cztery ograniczone
obrazy lub strony oraz minimalny prompt bez zbędnych danych CRM. Normalny czat
nie jest dozwolonym fallbackiem.

Temporary Chat nie pojawia się w zwykłej historii ChatGPT i nie używa ani nie
tworzy zwykłej pamięci personalizacyjnej. Pliki Temporary Chat nie są
przechowywane w Library zgodnie z aktualnym zachowaniem produktu. Nie oznacza
to natychmiastowego fizycznego usunięcia: OpenAI może przechowywać kopię treści
Temporary Chat przez okres wynikający z aktualnej polityki retencji.

Worker nie odczytuje ani nie eksportuje haseł, cookies, tokenów sesji ani danych
profilu. Logi zawierają wyłącznie identyfikator zadania, typy i skróty źródeł,
czasy, przejścia stanu i bezpieczny kod błędu. Obrazy, OCR, pełne odpowiedzi i
dane sesji nie są logowane.

Zwalidowany wynik `NEXT_STABIL_VISION_V1` jest traktowany przez Technical AI
jako `UNTRUSTED_VISUAL_EVIDENCE`. Obserwacje pozostają faktami wizualnymi,
interpretacje hipotezami, a niepewności ograniczeniami. Cytowanie zawsze
wskazuje oryginalny dokument, stronę, asset lub zdjęcie wizji, nigdy czat.

Nie ma automatycznego zapisu do notatek, embeddingów obrazów w Qdrant ani
historycznego backfillu Vision.

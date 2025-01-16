# `clean_files.py`

Skrypt do porządkowania plików w katalogach.

Tomasz Owienko 318703, realizacja ASU 24Z, grupa czwartek 12:15

### Uruchomienie

Uruchomienie skryptu:

```shell
python3 clean_files.py [-c <PLIK_KONFIGURACYJNY] [--no-interaction] <TRYB> <X> <Y1> [<Y2> ... <YN>]
```
Poszczególne opcje:

- `-c` - ścieżka do pliku konfiguracyjnego (domyślnie `~/.clean_files`)
- `--no-interaction` - wykonanie bez interakcji użytkownika (odpowiedź "tak" na wszystkie pytania)
- `<TRYB>` tryb działania skryptu
- `<X>` katalog główny
- `<Y1> [<Y2> ... <YN>]` - katalogi pomocnicze (co najmniej jeden)

### Tryby działania

- `copy_missing` - skopiowanie plików z katalogów pomocniczych nieobecnych w katalogu głównym do katalogu głownego
- `remove_duplicates` - usunięcie duplikatów pliku i zachowanie najstarszego z nich
- `remove_versions` - usunięcie starych wersji plików
- `remove_empty` - usunięcie pustych plików
- `remove_temporary` - usunięcie plików tymczasowych wg. rozszerzeń (rozszerzenia konfigurowalne)
- `fix_access` - ujednolicenie uprawnień dostępu do plików (uprawnienia konfigurowalne)
- `fix_names` - zastąpienie niedozwolonych znaków w nazwach plików (lista niedozwolonych znaków i znak zastępczy konfigurowalne)

### Plik konfiguracyjny

Plik w formacie JSON:

```json
{
    "desired_attrs": 644,
    "illegal_chars": ":\".;*?$#'|\\",
    "subst_char": "_",
    "tmp_extensions": [
        ".tmp",
        "~"
    ]
}

```

- `desired_attrs` - docelowe uprawnienia dostępu
- `illegal_chars` - niedozwolone znaki w nazwach plików
- `subst_char` - znak do zastąpienie niedozwolonych znaków
- `tmp_extensions` - rozszerzenia plików tymczasowych

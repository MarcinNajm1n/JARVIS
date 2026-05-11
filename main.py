from config import NAZWA_ASYSTENTA
from src.command_handler import obsluz_komende
from src.llm_client import odpowiedz_jarvisa
from src.debug_utils import debug_print
from src.long_term_memory import (
    wczytaj_pamiec_stala,
    zapisz_pamiec_stala,
)
from src.memory_store import (
    wczytaj_historie,
    zapisz_historie,
)


def main():
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Wpisz 'exit', aby zakończyć program.")
    print("Wpisz '/pomoc', aby zobaczyć dostępne komendy.\n")

    historia = wczytaj_historie()
    pamiec_stala = wczytaj_pamiec_stala()
    debug_print(f"Wczytano historię: {len(historia)} wiadomości")
    debug_print(f"Wczytano pamięć stałą: {len(pamiec_stala)} wpisów")

    if len(historia) > 0:
        print(f"{NAZWA_ASYSTENTA}: Wczytałem poprzednią historię rozmowy.")

    if len(pamiec_stala) > 0:
        print(f"{NAZWA_ASYSTENTA}: Wczytałem pamięć stałą.")

    if len(historia) > 0 or len(pamiec_stala) > 0:
        print()

    while True:
        tekst_uzytkownika = input("Ty: ").strip()

        if tekst_uzytkownika.lower() == "exit":
            zapisz_historie(historia)
            zapisz_pamiec_stala(pamiec_stala)
            print(f"{NAZWA_ASYSTENTA}: Zapisałem dane i kończę działanie.")
            break

        czy_komenda, historia, pamiec_stala = obsluz_komende(
            tekst_uzytkownika,
            historia,
            pamiec_stala
        )

        if czy_komenda:
            continue

        historia.append({
            "role": "user",
            "content": tekst_uzytkownika
        })

        odpowiedz = odpowiedz_jarvisa(historia, pamiec_stala)

        historia.append({
            "role": "assistant",
            "content": odpowiedz
        })

        zapisz_historie(historia)

        print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")
        print()


if __name__ == "__main__":
    main()
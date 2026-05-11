from config import NAZWA_ASYSTENTA
from src.llm_client import odpowiedz_jarvisa
from src.long_term_memory import (
    dodaj_do_pamieci_stalej,
    formatuj_pamiec_stala,
    wczytaj_pamiec_stala,
    zapisz_pamiec_stala,
)
from src.memory_store import wczytaj_historie, zapisz_historie


def main():
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Wpisz 'exit', aby zakończyć program.")
    print("Dostępne komendy: /zapamietaj, /pamiec, /wyczysc_pamiec\n")

    historia = wczytaj_historie()
    pamiec_stala = wczytaj_pamiec_stala()

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
            print(f"{NAZWA_ASYSTENTA}: Zapisałem historię i kończę działanie.")
            break

        if tekst_uzytkownika.lower().startswith("/zapamietaj"):
            tresc_do_zapamietania = tekst_uzytkownika[len("/zapamietaj"):].strip()

            if tresc_do_zapamietania == "":
                print(f"{NAZWA_ASYSTENTA}: Użyj komendy w formie: /zapamietaj twoja_tresc")
                print()
                continue

            pamiec_stala = dodaj_do_pamieci_stalej(pamiec_stala, tresc_do_zapamietania)
            zapisz_pamiec_stala(pamiec_stala)

            print(f"{NAZWA_ASYSTENTA}: Zapisałem to w pamięci stałej.")
            print()
            continue

        if tekst_uzytkownika.lower() == "/pamiec":
            print(formatuj_pamiec_stala(pamiec_stala))
            print()
            continue

        if tekst_uzytkownika.lower() == "/wyczysc_pamiec":
            potwierdzenie = input("Czy na pewno chcesz wyczyścić pamięć stałą? (tak/nie): ").strip().lower()

            if potwierdzenie == "tak":
                pamiec_stala = []
                zapisz_pamiec_stala(pamiec_stala)
                print(f"{NAZWA_ASYSTENTA}: Pamięć stała została wyczyszczona.")
            else:
                print(f"{NAZWA_ASYSTENTA}: Anulowano czyszczenie pamięci.")

            print()
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
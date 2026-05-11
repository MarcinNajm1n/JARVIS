from config import NAZWA_ASYSTENTA
from src.llm_client import odpowiedz_jarvisa
from src.memory_store import wczytaj_historie, zapisz_historie


def main():
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Wpisz 'exit', aby zakończyć program.\n")

    historia = wczytaj_historie()

    if len(historia) > 0:
        print(f"{NAZWA_ASYSTENTA}: Wczytałem poprzednią historię rozmowy.")
        print()

    while True:
        tekst_uzytkownika = input("Ty: ")

        if tekst_uzytkownika.lower() == "exit":
            zapisz_historie(historia)
            print(f"{NAZWA_ASYSTENTA}: Zapisałem historię i kończę działanie.")
            break

        historia.append({
            "role": "user",
            "content": tekst_uzytkownika
        })

        odpowiedz = odpowiedz_jarvisa(historia)

        historia.append({
            "role": "assistant",
            "content": odpowiedz
        })

        zapisz_historie(historia)

        print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")
        print()


if __name__ == "__main__":
    main()
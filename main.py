from config import NAZWA_ASYSTENTA
from src.llm_client import odpowiedz_jarvisa


def main():
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Wpisz 'exit', aby zakończyć program.\n")

    while True:
        tekst_uzytkownika = input("Ty: ")

        if tekst_uzytkownika.lower() == "exit":
            print(f"{NAZWA_ASYSTENTA}: Kończę działanie.")
            break

        odpowiedz = odpowiedz_jarvisa(tekst_uzytkownika)

        print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")
        print()


if __name__ == "__main__":
    main()
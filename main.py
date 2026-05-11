from config import NAZWA_ASYSTENTA
from src.llm_client import odpowiedz_jarvisa


def main():
    print(f"{NAZWA_ASYSTENTA} startuje...")
    print("Wpisz 'exit', aby zakończyć program.\n")

    historia = []

    while True:
        tekst_uzytkownika = input("Ty: ")

        if tekst_uzytkownika.lower() == "exit":
            print(f"{NAZWA_ASYSTENTA}: Kończę działanie.")
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

        print(f"{NAZWA_ASYSTENTA}: {odpowiedz}")
        print()


if __name__ == "__main__":
    main()
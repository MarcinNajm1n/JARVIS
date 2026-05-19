from src.command_catalog import (
    format_command_catalog_for_prompt,
    format_command_help,
    search_command_catalog,
)


def test_format_command_help_zawiera_wylaczenie_i_pomoc():
    help_text = format_command_help()

    assert "/pomoc" in help_text
    assert "jarvis wylacz sie" in help_text
    assert "zapisz dane i zakoncz dzialanie programu" in help_text


def test_command_catalog_prompt_uczy_model_jak_odpowiadac_o_wylaczeniu():
    prompt_context = format_command_catalog_for_prompt()

    assert "Katalog lokalnych komend JARVISA" in prompt_context
    assert "mozesz mnie wylaczyc za pomoca zwyklego 'jarvis wylacz sie'" in prompt_context


def test_search_command_catalog_znajduje_komende_wylaczenia():
    results = search_command_catalog("jak moge cie wylaczyc")

    assert results[0]["command"] == "jarvis wylacz sie"
    assert "zakoncz dzialanie programu" in results[0]["description"]

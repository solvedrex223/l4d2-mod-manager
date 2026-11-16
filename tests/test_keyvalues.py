from mod_manager.keyvalues import parse

from conftest import REAL_ADDONINFO


def test_parses_real_addoninfo():
    kv = parse(REAL_ADDONINFO)
    info = kv["addoninfo"]
    assert info["addontitle"] == "Team Health Counter"
    assert info["addonauthor"] == "Rayman1103"
    assert info["addonversion"] == "4"
    assert info["addonurl0"] == "https://www.gamemaps.com/details/2951"
    assert info["addoncontent_script"] == "1"
    assert info["addoncontent_music"] == "0"


def test_comments_and_garbage_lines_tolerated():
    kv = parse(REAL_ADDONINFO)
    info = kv["addoninfo"]
    assert "addonsteamingroupname" not in info
    assert info["sitting"] == ""
    assert info["tank/finale"] == ""


def test_keys_are_case_insensitive():
    kv = parse('"AddonInfo"\n{\n\taddonTitle "x"\n}\n')
    assert kv["addoninfo"]["addontitle"] == "x"


def test_nested_blocks_and_vdf_format():
    text = (
        '"libraryfolders"\n'
        '{\n'
        '\t"contentstatsid"\t\t"123"\n'
        '\t"0"\n'
        '\t{\n'
        '\t\t"path"\t\t"/mnt/Games/SteamLibrary"\n'
        '\t\t"apps"\n'
        '\t\t{\n'
        '\t\t\t"550"\t\t"87"\n'
        '\t\t}\n'
        '\t}\n'
        '\t"1"\t"/other/library"\n'
        '}\n'
    )
    kv = parse(text)
    folders = kv["libraryfolders"]
    assert folders["contentstatsid"] == "123"
    assert folders["0"]["path"] == "/mnt/Games/SteamLibrary"
    assert folders["0"]["apps"]["550"] == "87"
    assert folders["1"] == "/other/library"


def test_quoted_escapes():
    kv = parse('"key" "say \\"hi\\""\n')
    assert kv["key"] == 'say "hi"'


def test_pair_on_separate_line_is_not_a_pair():
    kv = parse('"a"\n"b"\n')
    assert kv["a"] == ""
    assert kv["b"] == ""

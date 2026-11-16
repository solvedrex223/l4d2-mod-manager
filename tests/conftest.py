from __future__ import annotations

import itertools

import pytest

REAL_ADDONINFO = (
    '// The addoninfo.txt file is a metadata file that is required by all Source Engine Add-ons.\n'
    '\n'
    '"AddonInfo"\n'
    '{\n'
    '\taddonSteamAppID\t\t550\n'
    '\taddontitle\t\t"Team Health Counter"\n'
    '\taddonversion\t\t4\n'
    '\taddontagline\t\t"Adds a health counter for Survivor teammates."\n'
    '\taddonauthor\t\t"Rayman1103"\n'
    '\t//addonSteamGroupName\t""\n'
    '\taddonauthorSteamID\t"Rayman1103"\n'
    '\taddonURL0\t\t"https://www.gamemaps.com/details/2951"\n'
    '\taddonDescription\t"Adds a health counter for Survivor teammates."\n'
    '\taddonContent_Script 1\n'
    '\taddonContent_Music 0\n'
    '\tsitting\n'
    '\ttank/finale\n'
    '}\n'
)

REAL_ADDONLIST = (
    '"AddonList"\n'
    '{\n'
    '\t"workshop\\1124884266.vpk"\t\t"0"\n'
    '\t"workshop\\121088866.vpk"\t\t"1"\n'
    '\t"cool_skin.vpk"\t\t"1"\n'
    '}\n'
)


@pytest.fixture
def game_dir(tmp_path):
    game = tmp_path / "Left 4 Dead 2"
    addons = game / "left4dead2" / "addons" / "workshop"
    addons.mkdir(parents=True)
    (game / "left4dead2" / "addonlist.txt").write_text('"AddonList"\n{\n}\n', encoding="utf-8")
    return game


@pytest.fixture
def vpk_factory(tmp_path):
    counter = itertools.count()
    out_dir = tmp_path / "vpks"
    src_root = tmp_path / "vpk_src"
    out_dir.mkdir()
    src_root.mkdir()

    def _make(files: dict[str, bytes | str], addoninfo: str | bytes | None = None, name: str | None = None):
        src = src_root / f"src{next(counter)}"
        src.mkdir()
        for rel, data in files.items():
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.encode() if isinstance(data, str) else data)
        if addoninfo is not None:
            (src / "addoninfo.txt").write_bytes(
                addoninfo.encode() if isinstance(addoninfo, str) else addoninfo
            )
        out = out_dir / f"{name or f'mod{next(counter)}'}.vpk"
        import vpk

        vpk.new(str(src)).save(str(out))
        return out

    return _make

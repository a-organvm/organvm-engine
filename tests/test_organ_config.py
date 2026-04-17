"""Tests for canonical organ configuration."""

from organvm_engine.organ_config import (
    ORGANS,
    dir_to_registry_key,
    organ_aliases,
    organ_dir_map,
    organ_org_dirs,
    registry_key_to_dir,
)


class TestOrganConfig:
    def test_organs_dict_has_all_keys(self):
        expected = {"I", "II", "III", "IV", "V", "VI", "VII", "META", "LIMINAL", "SIGMA_E"}
        assert set(ORGANS.keys()) == expected

    def test_registry_key_to_dir(self):
        mapping = registry_key_to_dir()
        assert mapping["ORGAN-I"] == "organvm-i-theoria"
        assert mapping["META-ORGANVM"] == "meta-organvm"

    def test_organ_dir_to_key(self):
        mapping = dir_to_registry_key()
        assert mapping["organvm-i-theoria"] == "ORGAN-I"
        assert mapping["meta-organvm"] == "META-ORGANVM"

    def test_each_organ_has_required_fields(self):
        for key, entry in ORGANS.items():
            assert "dir" in entry, f"{key} missing 'dir'"
            assert "registry_key" in entry, f"{key} missing 'registry_key'"
            assert "org" in entry, f"{key} missing 'org'"

    def test_resolve_organ_key_aliases(self):
        aliases = organ_aliases()
        assert aliases["I"] == "ORGAN-I"
        assert aliases["META"] == "META-ORGANVM"
        assert aliases["LIMINAL"] == "PERSONAL"

    def test_no_duplicate_dirs(self):
        # SIGMA_E and LIMINAL intentionally share dir "4444J99"
        # (sovereign entity within personal namespace)
        dirs = [v["dir"] for v in ORGANS.values()]
        non_shared = [d for d in dirs if d != "4444J99"]
        assert len(non_shared) == len(set(non_shared))
        assert dirs.count("4444J99") == 2  # exactly SIGMA_E + LIMINAL

    def test_no_duplicate_registry_keys(self):
        keys = [v["registry_key"] for v in ORGANS.values()]
        assert len(keys) == len(set(keys))

    def test_organ_org_dirs_includes_sigma_e(self):
        # 4444J99 is now included because SIGMA_E has sovereign governance
        # (registry_key != "PERSONAL"), making it discoverable for seeds
        dirs = organ_org_dirs()
        assert "4444J99" in dirs
        assert "organvm-i-theoria" in dirs

    def test_organ_dir_map_returns_all(self):
        mapping = organ_dir_map()
        assert len(mapping) == 10  # 8 organs + LIMINAL + SIGMA_E
        assert mapping["I"] == "organvm-i-theoria"

"""Tests for ecosystem.product_types — type inference and pillar defaults.

Covers infer_product_type heuristics, get_pillar_defaults lookups,
PRODUCT_TYPES data integrity, and edge cases.
"""

from __future__ import annotations

from organvm_engine.ecosystem.product_types import (
    DEFAULT_CRIT_PROMPTS,
    DEFAULT_GEN_PROMPTS,
    LIFECYCLE_STAGES,
    PRODUCT_TYPES,
    _REVENUE_HINTS,
    _TAG_HINTS,
    get_pillar_defaults,
    infer_product_type,
)


# ── PRODUCT_TYPES data integrity ─────────────────────────────────


class TestProductTypesData:
    def test_all_types_present(self):
        expected = {
            "saas", "browser_extension", "trading", "creative_tool",
            "library", "content_platform", "marketplace", "game",
        }
        assert set(PRODUCT_TYPES.keys()) == expected

    def test_each_type_has_description(self):
        for ptype, data in PRODUCT_TYPES.items():
            assert "description" in data, f"{ptype} missing description"
            assert isinstance(data["description"], str)

    def test_each_type_has_key_pillars(self):
        for ptype, data in PRODUCT_TYPES.items():
            assert "key_pillars" in data, f"{ptype} missing key_pillars"
            assert isinstance(data["key_pillars"], list)
            assert len(data["key_pillars"]) >= 1

    def test_each_type_has_pillar_defaults(self):
        for ptype, data in PRODUCT_TYPES.items():
            assert "pillar_defaults" in data, f"{ptype} missing pillar_defaults"
            defaults = data["pillar_defaults"]
            assert isinstance(defaults, dict)
            assert len(defaults) >= 1

    def test_pillar_defaults_have_scan_scope(self):
        for ptype, data in PRODUCT_TYPES.items():
            for pillar, config in data["pillar_defaults"].items():
                assert "scan_scope" in config, (
                    f"{ptype}/{pillar} missing scan_scope"
                )
                assert isinstance(config["scan_scope"], list)

    def test_pillar_defaults_have_artifacts(self):
        for ptype, data in PRODUCT_TYPES.items():
            for pillar, config in data["pillar_defaults"].items():
                assert "artifacts" in config, (
                    f"{ptype}/{pillar} missing artifacts"
                )
                for art in config["artifacts"]:
                    assert "name" in art
                    assert "cadence" in art
                    assert "staleness_days" in art

    def test_lifecycle_stages(self):
        assert "conception" in LIFECYCLE_STAGES
        assert "live" in LIFECYCLE_STAGES
        assert "sunset" in LIFECYCLE_STAGES
        assert len(LIFECYCLE_STAGES) == 8


# ── _TAG_HINTS and _REVENUE_HINTS ────────────────────────────────


class TestHintMaps:
    def test_tag_hints_cover_all_types(self):
        assert set(_TAG_HINTS.keys()) == set(PRODUCT_TYPES.keys())

    def test_tag_hints_are_lists(self):
        for ptype, hints in _TAG_HINTS.items():
            assert isinstance(hints, list), f"{ptype} hints not a list"
            assert len(hints) >= 1

    def test_revenue_hints_values_are_valid_types(self):
        for rev_model, ptype in _REVENUE_HINTS.items():
            assert ptype in PRODUCT_TYPES, (
                f"Revenue hint '{rev_model}' maps to unknown type '{ptype}'"
            )


# ── infer_product_type ────────────────────────────────────────────


class TestInferProductType:
    def test_defaults_to_saas(self):
        result = infer_product_type()
        assert result == "saas"

    def test_no_data_defaults_to_saas(self):
        result = infer_product_type(seed_data=None, registry_data=None)
        assert result == "saas"

    def test_empty_seed_defaults_to_saas(self):
        result = infer_product_type(seed_data={})
        assert result == "saas"

    def test_seed_tags_saas(self):
        seed = {"metadata": {"tags": ["saas", "dashboard"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "saas"

    def test_seed_tags_browser_extension(self):
        seed = {"metadata": {"tags": ["chrome", "extension"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "browser_extension"

    def test_seed_tags_trading(self):
        seed = {"metadata": {"tags": ["trading", "defi", "crypto"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "trading"

    def test_seed_tags_creative_tool(self):
        seed = {"metadata": {"tags": ["music", "generative", "audio"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "creative_tool"

    def test_seed_tags_library(self):
        seed = {"metadata": {"tags": ["npm", "package", "sdk"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "library"

    def test_seed_tags_content_platform(self):
        seed = {"metadata": {"tags": ["blog", "newsletter"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "content_platform"

    def test_seed_tags_marketplace(self):
        seed = {"metadata": {"tags": ["marketplace", "ecommerce"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "marketplace"

    def test_seed_tags_game(self):
        seed = {"metadata": {"tags": ["game", "interactive"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "game"

    def test_registry_revenue_subscription(self):
        reg = {"revenue_model": "subscription"}
        result = infer_product_type(registry_data=reg)
        assert result == "saas"

    def test_registry_revenue_freemium(self):
        reg = {"revenue_model": "freemium"}
        result = infer_product_type(registry_data=reg)
        assert result == "saas"

    def test_registry_revenue_marketplace_commission(self):
        reg = {"revenue_model": "marketplace_commission"}
        result = infer_product_type(registry_data=reg)
        assert result == "marketplace"

    def test_registry_revenue_in_app_purchase(self):
        reg = {"revenue_model": "in_app_purchase"}
        result = infer_product_type(registry_data=reg)
        assert result == "game"

    def test_revenue_model_case_insensitive(self):
        reg = {"revenue_model": "SUBSCRIPTION"}
        result = infer_product_type(registry_data=reg)
        assert result == "saas"

    def test_revenue_overrides_weak_tags(self):
        """Revenue model gives +2 score, overriding a single tag hit (+1)."""
        seed = {"metadata": {"tags": ["game"]}}  # game: +1
        reg = {"revenue_model": "subscription"}  # saas: +2
        result = infer_product_type(seed_data=seed, registry_data=reg)
        assert result == "saas"

    def test_strong_tags_override_revenue(self):
        """Multiple tag hits can override revenue model."""
        seed = {"metadata": {"tags": ["game", "interactive", "gaming"]}}  # game: +3
        reg = {"revenue_model": "subscription"}  # saas: +2
        result = infer_product_type(seed_data=seed, registry_data=reg)
        assert result == "game"

    def test_none_tags_handled(self):
        seed = {"metadata": {"tags": None}}
        result = infer_product_type(seed_data=seed)
        assert result == "saas"

    def test_missing_metadata_handled(self):
        seed = {"metadata": {}}
        result = infer_product_type(seed_data=seed)
        assert result == "saas"

    def test_none_revenue_model_handled(self):
        reg = {"revenue_model": None}
        result = infer_product_type(registry_data=reg)
        assert result == "saas"

    def test_unknown_revenue_model_ignored(self):
        reg = {"revenue_model": "barter_system"}
        result = infer_product_type(registry_data=reg)
        assert result == "saas"

    def test_tag_substring_matching(self):
        """Tags match via 'hint in tag', so 'chrome-ext' matches 'chrome'."""
        seed = {"metadata": {"tags": ["chrome-extension-tools"]}}
        result = infer_product_type(seed_data=seed)
        assert result == "browser_extension"

    def test_combined_seed_and_registry(self):
        seed = {"metadata": {"tags": ["dashboard", "react"]}}
        reg = {"revenue_model": "subscription"}
        result = infer_product_type(seed_data=seed, registry_data=reg)
        assert result == "saas"


# ── get_pillar_defaults ───────────────────────────────────────────


class TestGetPillarDefaults:
    def test_saas_delivery(self):
        result = get_pillar_defaults("saas", "delivery")
        assert result is not None
        assert "scan_scope" in result
        assert "artifacts" in result

    def test_saas_revenue(self):
        result = get_pillar_defaults("saas", "revenue")
        assert result is not None
        assert "subscription" in result["scan_scope"]

    def test_saas_marketing(self):
        result = get_pillar_defaults("saas", "marketing")
        assert result is not None
        assert "seo" in result["scan_scope"]

    def test_browser_extension_delivery(self):
        result = get_pillar_defaults("browser_extension", "delivery")
        assert result is not None
        assert "chrome_web_store" in result["scan_scope"]

    def test_library_listings(self):
        result = get_pillar_defaults("library", "listings")
        assert result is not None

    def test_game_community(self):
        result = get_pillar_defaults("game", "community")
        assert result is not None
        assert "discord" in result["scan_scope"]

    def test_unknown_product_type(self):
        result = get_pillar_defaults("unknown_type", "delivery")
        assert result is None

    def test_unknown_pillar(self):
        result = get_pillar_defaults("saas", "nonexistent_pillar")
        assert result is None

    def test_all_types_have_delivery(self):
        for ptype in PRODUCT_TYPES:
            result = get_pillar_defaults(ptype, "delivery")
            assert result is not None, f"{ptype} has no delivery defaults"

    def test_artifact_structure(self):
        result = get_pillar_defaults("saas", "delivery")
        assert result is not None
        for art in result["artifacts"]:
            assert "name" in art
            assert "cadence" in art
            assert "staleness_days" in art
            assert isinstance(art["staleness_days"], int)


# ── DEFAULT_GEN_PROMPTS / DEFAULT_CRIT_PROMPTS ───────────────────


class TestDefaultPrompts:
    def test_gen_prompts_has_marketing(self):
        assert "marketing" in DEFAULT_GEN_PROMPTS
        prompts = DEFAULT_GEN_PROMPTS["marketing"]
        assert len(prompts) >= 1
        for p in prompts:
            assert "id" in p
            assert "prompt" in p
            assert "trigger" in p

    def test_gen_prompts_has_revenue(self):
        assert "revenue" in DEFAULT_GEN_PROMPTS

    def test_gen_prompts_has_delivery(self):
        assert "delivery" in DEFAULT_GEN_PROMPTS

    def test_crit_prompts_has_marketing(self):
        assert "marketing" in DEFAULT_CRIT_PROMPTS

    def test_crit_prompts_has_revenue(self):
        assert "revenue" in DEFAULT_CRIT_PROMPTS

    def test_crit_prompts_structure(self):
        for pillar, prompts in DEFAULT_CRIT_PROMPTS.items():
            for p in prompts:
                assert "id" in p, f"Crit prompt in {pillar} missing id"
                assert "prompt" in p, f"Crit prompt in {pillar} missing prompt"

    def test_gen_prompts_contain_template_vars(self):
        """Gen prompts should contain template variables like {product_type}."""
        for pillar, prompts in DEFAULT_GEN_PROMPTS.items():
            for p in prompts:
                assert "{" in p["prompt"], (
                    f"Gen prompt {p['id']} in {pillar} has no template variables"
                )

import pytest

from app.config import Settings, Target, parse_chain


def test_parse_chain_reads_ordered_targets():
    chain = parse_chain("glimmer:muse-glimmer, meta:muse-spark-1.3")
    assert chain == [
        Target(provider="glimmer", model="muse-glimmer"),
        Target(provider="meta", model="muse-spark-1.3"),
    ]


def test_parse_chain_keeps_slashes_in_partner_model_ids():
    (target,) = parse_chain("Fireworks:accounts/fireworks/models/muse-spark-open")
    assert target.provider == "fireworks"
    assert target.model == "accounts/fireworks/models/muse-spark-open"


@pytest.mark.parametrize("spec", ["", " , ", "meta", "meta:", ":muse-spark-1.3"])
def test_parse_chain_rejects_malformed_specs(spec):
    with pytest.raises(ValueError):
        parse_chain(spec)


def test_meta_needs_a_key_but_glimmer_only_needs_a_url():
    settings = Settings(_env_file=None, glimmer_base_url="https://tunnel.example/v1/")
    assert not settings.endpoint("meta").configured
    glimmer = settings.endpoint("glimmer")
    assert glimmer.configured
    assert glimmer.base_url == "https://tunnel.example/v1"
    assert glimmer.extra_body == {"chat_template_kwargs": {"reasoning_strength": "low"}}


def test_cors_origins_split_on_commas():
    settings = Settings(_env_file=None, cors_origins="http://a.test, http://b.test,")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]

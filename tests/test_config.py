import yaml


def test_config_has_required_keys():
    cfg = yaml.safe_load(open("config/sources.yaml", encoding="utf-8"))
    for k in ["steam_tags", "theme_keywords", "mechanic_keywords",
              "art_keywords", "subreddits"]:
        assert k in cfg and cfg[k]

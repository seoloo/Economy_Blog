from datetime import datetime, timezone
from pathlib import Path

from conftest import make_article

from econblog.classify import classify_and_select
from econblog.classify.dedupe import mark_duplicates, normalize_title, select_top
from econblog.classify.keyword import KeywordClassifier
from econblog.classify.laya import chunk_by_budget, level_to_importance, yes_probability
from econblog.collect import collect_all
from econblog.collect.rss import RssCollector
from econblog.models import ClassifiedArticle, Source

FIXTURES = Path(__file__).parent / "fixtures"


def test_rss_parse_filters_old_and_strips_html(settings):
    source = Source(id="t", name="테스트", url="https://example.com/rss", region="kr")
    raw = (FIXTURES / "sample_feed.xml").read_bytes()
    since = datetime(2026, 11, 5, tzinfo=timezone.utc)
    articles = RssCollector(settings).parse(source, raw, since)

    titles = [a.title for a in articles]
    assert "오래된 기사" not in titles
    assert titles[0] == "코스피, 외국인 매수에 2% 상승"
    assert "<p>" not in articles[0].summary and "&amp;" not in articles[0].summary
    assert "날짜 없는 기사" in titles  # 날짜가 없으면 버리지 않는다


def test_normalize_title_removes_press_suffix_and_tags():
    assert normalize_title("[속보] 한은 기준금리 동결 - 연합뉴스") == normalize_title("한은 기준금리 동결")


def test_mark_duplicates_keeps_most_important():
    a = ClassifiedArticle(article=make_article("한은 기준금리 동결, 연내 인하 시사"), topic="rates", importance=0.9)
    b = ClassifiedArticle(article=make_article("한은 기준금리 동결…연내 인하 시사"), topic="rates", importance=0.5)
    c = ClassifiedArticle(article=make_article("서울 아파트 거래량 감소"), topic="realestate", importance=0.4)
    mark_duplicates([a, b, c], threshold=0.55)
    assert (a.is_duplicate, b.is_duplicate, c.is_duplicate) == (False, True, False)


def test_select_top_limits_per_region_and_topic():
    items = [
        ClassifiedArticle(article=make_article(f"금리 기사 {i}"), topic="rates", importance=0.9 - i * 0.01)
        for i in range(5)
    ] + [ClassifiedArticle(article=make_article("환율 기사"), topic="fx", importance=0.1)]
    items += [ClassifiedArticle(article=make_article("Fed news", region="global"), topic="rates", importance=0.5)]
    picked = select_top(items, n_per_region=4)
    kr = [x for x in picked if x.article.region == "kr"]
    assert len(kr) == 4
    assert sum(1 for x in kr if x.topic == "rates") == 3
    assert any(x.topic == "fx" for x in kr)
    assert any(x.article.region == "global" for x in picked)


def test_keyword_classifier_topics(settings):
    out = KeywordClassifier(settings).classify(
        [make_article("Fed holds rates, Powell signals patience", region="global"), make_article("비트코인 급등")]
    )
    assert out[0].topic == "rates"
    assert out[1].topic == "crypto"
    assert out[0].importance > out[1].importance


def test_laya_importance_parsing():
    assert level_to_importance({"score": "major"}) == 1.0
    assert level_to_importance({"score": "minor"}) == 0.0
    assert abs(level_to_importance({"probabilities": {"minor": 0.5, "major": 0.5}}) - 0.5) < 1e-9
    assert level_to_importance({}) == 0.5


def test_laya_relevance_and_chunking():
    assert yes_probability({"noul": 0.9}) == 0.9
    assert yes_probability({"noul": False}) == 0.0
    assert yes_probability(None) == 0.5
    chunks = chunk_by_budget(["a" * 400] * 40, budget=6000, max_items=64)
    assert all(len(c) * 400 <= 6000 for c in chunks)
    assert sum(len(c) for c in chunks) == 40


def test_offline_collect_and_classify(settings):
    articles = collect_all(settings, datetime.now(timezone.utc), offline=True)
    selected = classify_and_select(settings, articles, offline=True)
    assert {x.article.region for x in selected} == {"kr", "global"}
    urls = {x.article.url for x in selected}
    assert not ({"https://example.com/kr/1", "https://example.com/kr/1-dup"} <= urls), "중복 기사가 함께 선택됨"

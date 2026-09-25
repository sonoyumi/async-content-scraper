from conftest import read_fixture

from scraper.extractors.html_extractor import HtmlExtractor
from scraper.sources.schemas import HtmlConfig, ItemSelectors


def _make_extractor() -> HtmlExtractor:
    config = HtmlConfig(
        list_selector="article.news-item",
        item_selectors=ItemSelectors(
            title="h2.title",
            text="div.content",
            date="time[datetime]",
            date_attr="datetime",
            link="a.permalink",
            link_attr="href",
            media="img.thumb",
            media_attr="src",
        ),
    )
    return HtmlExtractor(config)


def test_extracts_expected_number_of_items():
    html = read_fixture("html", "generic_article_1.html")
    items = _make_extractor().extract(html, base_url="https://example.com")
    # The 3rd <article> in the fixture has no title/text/link/media and must be skipped.
    assert len(items) == 2


def test_extracts_fields_correctly():
    html = read_fixture("html", "generic_article_1.html")
    items = _make_extractor().extract(html, base_url="https://example.com")
    first = items[0]

    assert "First article title" in first.text
    assert "Some body text for the first article." in first.text
    assert first.url == "https://example.com/news/first-article"
    assert first.published_at.isoformat() == "2026-01-05T10:00:00+00:00"
    assert first.media == [{"type": "image", "url": "https://example.com/images/first.jpg"}]
    assert first.external_id == first.url


def test_missing_selector_returns_empty_list_not_exception():
    config = HtmlConfig(
        list_selector="div.does-not-exist",
        item_selectors=ItemSelectors(text="p"),
    )
    html = read_fixture("html", "generic_article_1.html")
    items = HtmlExtractor(config).extract(html, base_url="https://example.com")
    assert items == []

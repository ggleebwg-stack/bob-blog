"""
Tests for monetization package: AdSense injection and Coupang Partners.
"""
import importlib
import os

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HTML_WITH_H2 = (
    "<html><body>"
    "<h2>첫 번째 섹션</h2><p>내용1</p>"
    "<h2>두 번째 섹션</h2><p>내용2</p>"
    "<h2>결론</h2><p>마무리 내용</p>"
    "</body></html>"
)

SIMPLE_HTML = "<p>Hello world</p>"


def _reload_injectors():
    """Re-import monetization modules so os.getenv() picks up monkeypatched env."""
    import monetization.adsense_injector as ai
    import monetization.coupang_partners as cp
    import monetization as mon

    importlib.reload(ai)
    importlib.reload(cp)
    importlib.reload(mon)

    return mon.inject_adsense, mon.inject_coupang, mon.apply_monetization


# ---------------------------------------------------------------------------
# AdSense tests
# ---------------------------------------------------------------------------

def test_adsense_noop_when_no_client_id(monkeypatch):
    """inject_adsense returns html unchanged when ADSENSE_CLIENT_ID is not set."""
    monkeypatch.delenv("ADSENSE_CLIENT_ID", raising=False)
    inject_adsense, _, _ = _reload_injectors()

    result = inject_adsense(SAMPLE_HTML_WITH_H2)
    assert result == SAMPLE_HTML_WITH_H2


def test_adsense_injects_top_slot(monkeypatch):
    """With ADSENSE_CLIENT_ID and ADSENSE_SLOT_TOP set, ad appears after first H2."""
    monkeypatch.setenv("ADSENSE_CLIENT_ID", "ca-pub-1234567890123456")
    monkeypatch.setenv("ADSENSE_SLOT_TOP", "9876543210")
    monkeypatch.delenv("ADSENSE_SLOT_MID", raising=False)
    monkeypatch.delenv("ADSENSE_SLOT_BOTTOM", raising=False)
    inject_adsense, _, _ = _reload_injectors()

    result = inject_adsense(SAMPLE_HTML_WITH_H2)

    assert "adsbygoogle" in result
    assert "9876543210" in result
    # Ad should appear after first h2, before second h2
    first_h2_pos = result.index("첫 번째 섹션")
    ad_pos = result.index("adsbygoogle")
    second_h2_pos = result.index("두 번째 섹션")
    assert first_h2_pos < ad_pos < second_h2_pos


def test_adsense_injects_mid_slot_before_conclusion(monkeypatch):
    """With ADSENSE_SLOT_MID set, ad appears before the conclusion H2."""
    monkeypatch.setenv("ADSENSE_CLIENT_ID", "ca-pub-1234567890123456")
    monkeypatch.delenv("ADSENSE_SLOT_TOP", raising=False)
    monkeypatch.setenv("ADSENSE_SLOT_MID", "1111111111")
    monkeypatch.delenv("ADSENSE_SLOT_BOTTOM", raising=False)
    inject_adsense, _, _ = _reload_injectors()

    result = inject_adsense(SAMPLE_HTML_WITH_H2)

    assert "1111111111" in result
    ad_pos = result.index("1111111111")
    conclusion_pos = result.index("결론")
    assert ad_pos < conclusion_pos


def test_adsense_skips_mid_slot_when_no_conclusion_h2(monkeypatch):
    """MID slot is not injected when no conclusion keyword found in any H2."""
    monkeypatch.setenv("ADSENSE_CLIENT_ID", "ca-pub-1234567890123456")
    monkeypatch.delenv("ADSENSE_SLOT_TOP", raising=False)
    monkeypatch.setenv("ADSENSE_SLOT_MID", "2222222222")
    monkeypatch.delenv("ADSENSE_SLOT_BOTTOM", raising=False)
    inject_adsense, _, _ = _reload_injectors()

    html_no_conclusion = "<h2>섹션 A</h2><p>내용</p><h2>섹션 B</h2><p>내용</p>"
    result = inject_adsense(html_no_conclusion)

    assert "2222222222" not in result


def test_adsense_injects_bottom_slot(monkeypatch):
    """ADSENSE_SLOT_BOTTOM appends ad before </body>."""
    monkeypatch.setenv("ADSENSE_CLIENT_ID", "ca-pub-1234567890123456")
    monkeypatch.delenv("ADSENSE_SLOT_TOP", raising=False)
    monkeypatch.delenv("ADSENSE_SLOT_MID", raising=False)
    monkeypatch.setenv("ADSENSE_SLOT_BOTTOM", "3333333333")
    inject_adsense, _, _ = _reload_injectors()

    result = inject_adsense(SAMPLE_HTML_WITH_H2)

    assert "3333333333" in result
    # Ad should appear inside body (before closing tag area)
    assert result.index("3333333333") < len(result)


# ---------------------------------------------------------------------------
# Coupang tests
# ---------------------------------------------------------------------------

def test_coupang_noop_when_no_access_key(monkeypatch):
    """inject_coupang returns html unchanged when COUPANG_ACCESS_KEY is not set."""
    monkeypatch.delenv("COUPANG_ACCESS_KEY", raising=False)
    _, inject_coupang, _ = _reload_injectors()

    result = inject_coupang(SIMPLE_HTML, ["노트북", "키보드"])
    assert result == SIMPLE_HTML


def test_coupang_legal_notice_always_present(monkeypatch):
    """Legal notice is always appended when COUPANG_ACCESS_KEY is set."""
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, inject_coupang, _ = _reload_injectors()

    result = inject_coupang(SIMPLE_HTML, ["노트북"])
    assert "쿠팡파트너스 활동의 일환" in result


def test_coupang_legal_notice_present_with_no_keywords(monkeypatch):
    """Legal notice is present even when keywords list is empty."""
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, inject_coupang, _ = _reload_injectors()

    result = inject_coupang(SIMPLE_HTML, [])
    assert "쿠팡파트너스 활동의 일환" in result


def test_coupang_generates_search_urls(monkeypatch):
    """Placeholder search URLs are generated for each keyword."""
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, inject_coupang, _ = _reload_injectors()

    result = inject_coupang(SIMPLE_HTML, ["노트북", "마우스", "키보드"])
    assert "coupang.com/np/search" in result
    assert "추천 상품" in result
    # All three keywords should be present
    assert "노트북" in result
    assert "마우스" in result
    assert "키보드" in result


def test_coupang_max_three_keywords(monkeypatch):
    """Only up to 3 keywords generate links even if more are passed."""
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, inject_coupang, _ = _reload_injectors()

    result = inject_coupang(SIMPLE_HTML, ["A", "B", "C", "D", "E"])
    assert result.count("coupang.com/np/search") == 3


# ---------------------------------------------------------------------------
# apply_monetization integration test
# ---------------------------------------------------------------------------

def test_apply_monetization_calls_both(monkeypatch):
    """With both env vars set, result contains adsbygoogle AND 쿠팡파트너스."""
    monkeypatch.setenv("ADSENSE_CLIENT_ID", "ca-pub-1234567890123456")
    monkeypatch.setenv("ADSENSE_SLOT_TOP", "9999999999")
    monkeypatch.delenv("ADSENSE_SLOT_MID", raising=False)
    monkeypatch.delenv("ADSENSE_SLOT_BOTTOM", raising=False)
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, _, apply_monetization = _reload_injectors()

    post_meta = {"topic": "노트북", "keywords": ["노트북", "마우스"]}
    result = apply_monetization(SAMPLE_HTML_WITH_H2, post_meta)

    assert "adsbygoogle" in result
    assert "쿠팡파트너스" in result


def test_apply_monetization_uses_topic_fallback(monkeypatch):
    """When no keywords key, falls back to topic."""
    monkeypatch.delenv("ADSENSE_CLIENT_ID", raising=False)
    monkeypatch.setenv("COUPANG_ACCESS_KEY", "test-access-key")
    _, _, apply_monetization = _reload_injectors()

    post_meta = {"topic": "스마트폰"}
    result = apply_monetization(SIMPLE_HTML, post_meta)

    assert "스마트폰" in result
    assert "쿠팡파트너스 활동의 일환" in result

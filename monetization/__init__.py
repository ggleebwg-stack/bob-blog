from .adsense_injector import inject_adsense
from .coupang_partners import inject_coupang, LEGAL_NOTICE


def apply_monetization(html: str, post_meta: dict) -> str:
    """
    Apply all monetization layers to the HTML.

    post_meta keys used:
      - keywords: list[str]  (product keywords for Coupang)
      - topic: str           (fallback if no keywords)

    Safe to call even when env vars are not set — returns html unchanged if so.
    """
    keywords = post_meta.get("keywords") or [post_meta.get("topic", "")]
    html = inject_adsense(html)
    html = inject_coupang(html, keywords[:3])
    return html

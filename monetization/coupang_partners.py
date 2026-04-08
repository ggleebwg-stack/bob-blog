"""
Coupang Partners affiliate link injector.

Reads from env:
  COUPANG_ACCESS_KEY
  COUPANG_SECRET_KEY
  COUPANG_TRACKING_ID

Korean law requires: 이 포스팅은 쿠팡파트너스 활동의 일환으로,
이에 따른 일정액의 수수료를 제공받습니다.

If COUPANG_ACCESS_KEY is not set, returns html unchanged.
"""
import os
import urllib.parse

LEGAL_NOTICE = (
    '<p class="coupang-notice" style="font-size:0.8em;color:#888;">'
    '이 포스팅은 쿠팡파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.'
    '</p>'
)


def inject_coupang(html: str, keywords: list) -> str:
    """
    Append a '추천 상품' section with Coupang deep links + legal notice.

    keywords: list of product-related keywords extracted from the post topic.

    For now (until Coupang API integration is done), generate placeholder links:
    - For each keyword (max 3), create a Coupang search URL:
      https://www.coupang.com/np/search?q={urllib.parse.quote(keyword)}
    - Wrap in an HTML section
    - Always append LEGAL_NOTICE

    TODO: Replace placeholder URLs with real Coupang Partners API deep links
    when COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY are available.
    """
    access_key = os.getenv("COUPANG_ACCESS_KEY", "").strip()
    if not access_key:
        return html

    limited_keywords = [kw for kw in keywords if kw][:3]

    items_html = ""
    for keyword in limited_keywords:
        url = "https://www.coupang.com/np/search?q=" + urllib.parse.quote(keyword)
        items_html += (
            f'  <li><a href="{url}" target="_blank" rel="nofollow noopener">'
            f'{keyword} 쿠팡에서 보기</a></li>\n'
        )

    section_html = (
        "<hr>\n"
        "<h3>추천 상품</h3>\n"
        "<ul>\n"
        f"{items_html}"
        "</ul>\n"
        f"{LEGAL_NOTICE}"
    )

    return html + "\n" + section_html

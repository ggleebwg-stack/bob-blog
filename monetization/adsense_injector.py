"""
Google AdSense slot injector.

Reads from env:
  ADSENSE_CLIENT_ID   (e.g. ca-pub-XXXXXXXXXXXXXXXX)
  ADSENSE_SLOT_TOP    slot ID for top ad (after first H2)
  ADSENSE_SLOT_MID    slot ID for middle ad (before conclusion)
  ADSENSE_SLOT_BOTTOM slot ID for bottom ad (end of body)

If ADSENSE_CLIENT_ID is not set, returns html unchanged (safe no-op).
"""
import os

from bs4 import BeautifulSoup


def _build_ad_html(client_id: str, slot: str) -> str:
    return (
        f'<ins class="adsbygoogle" style="display:block" '
        f'data-ad-client="{client_id}" data-ad-slot="{slot}" '
        f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
        f'<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>'
    )


def inject_adsense(html: str) -> str:
    """Inject AdSense <ins> tags at top/mid/bottom positions in the HTML body."""
    client_id = os.getenv("ADSENSE_CLIENT_ID", "").strip()
    if not client_id:
        return html

    slot_top = os.getenv("ADSENSE_SLOT_TOP", "").strip()
    slot_mid = os.getenv("ADSENSE_SLOT_MID", "").strip()
    slot_bottom = os.getenv("ADSENSE_SLOT_BOTTOM", "").strip()

    soup = BeautifulSoup(html, "html.parser")

    # TOP: insert after the first <h2> tag (if any)
    if slot_top:
        first_h2 = soup.find("h2")
        if first_h2:
            ad_tag = BeautifulSoup(_build_ad_html(client_id, slot_top), "html.parser")
            first_h2.insert_after(ad_tag)

    # MID: insert before the last <h2> containing conclusion keywords
    if slot_mid:
        conclusion_keywords = ["결론", "마무리", "정리", "요약", "conclusion"]
        conclusion_h2 = None
        for h2 in soup.find_all("h2"):
            text = h2.get_text().lower()
            if any(kw.lower() in text for kw in conclusion_keywords):
                conclusion_h2 = h2
        if conclusion_h2 is not None:
            ad_tag = BeautifulSoup(_build_ad_html(client_id, slot_mid), "html.parser")
            conclusion_h2.insert_before(ad_tag)

    # BOTTOM: append before </body> tag (or at end if no body tag)
    if slot_bottom:
        ad_tag = BeautifulSoup(_build_ad_html(client_id, slot_bottom), "html.parser")
        body_tag = soup.find("body")
        if body_tag:
            body_tag.append(ad_tag)
        else:
            soup.append(ad_tag)

    return str(soup)

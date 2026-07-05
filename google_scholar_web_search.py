import os
import re
import time
import random
from http.cookiejar import MozillaCookieJar
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from scholarly import scholarly

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
}

RESULTS_PER_PAGE = 10

# Google Scholar frequently walls non-browser clients behind a "show you're
# not a robot" page. Workaround: export your Scholar cookies from a logged
# browser session (extension "Get cookies.txt LOCALLY", Netscape format) to
# a cookies.txt file next to this script, or point the env var
# GOOGLE_SCHOLAR_COOKIES_FILE at it.
def _build_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    cookie_file = os.environ.get("GOOGLE_SCHOLAR_COOKIES_FILE") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "cookies.txt"
    )
    if os.path.exists(cookie_file):
        jar = MozillaCookieJar(cookie_file)
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = jar
            print(f"Loaded Google Scholar cookies from {cookie_file}")
        except Exception as e:
            print(f"Warning: could not load cookies from {cookie_file}: {e}")
    return session


class ScholarBlockedError(RuntimeError):
    """Raised when Google Scholar serves its anti-robot page instead of results."""


def _parse_results(soup):
    """Parse one Google Scholar results page, pairing each entry with its
    sidebar PDF link (div.gs_ggs) when available."""
    results = []
    for item in soup.find_all("div", class_="gs_r"):
        ri = item.find("div", class_="gs_ri")
        if ri is None:
            continue

        title_tag = ri.find("h3", class_="gs_rt")
        title = title_tag.get_text() if title_tag else "No title available"
        link = (
            title_tag.find("a")["href"]
            if title_tag and title_tag.find("a")
            else "No link available"
        )

        authors_tag = ri.find("div", class_="gs_a")
        authors = authors_tag.get_text() if authors_tag else "No authors available"

        year = None
        if authors_tag:
            m = re.search(r"\b(19|20)\d{2}\b", authors_tag.get_text())
            if m:
                year = int(m.group(0))

        abstract_tag = ri.find("div", class_="gs_rs")
        abstract = abstract_tag.get_text() if abstract_tag else "No abstract available"

        # Direct PDF/full-text link shown by Scholar on the sidebar, if any
        pdf_url = None
        ggs = item.find("div", class_="gs_ggs")
        if ggs and ggs.find("a"):
            pdf_url = ggs.find("a")["href"]

        cited_by = None
        for a in ri.find_all("a"):
            text = a.get_text()
            if text.startswith("Cited by") or text.startswith("Citado por"):
                m = re.search(r"\d+", text)
                if m:
                    cited_by = int(m.group(0))
                break

        results.append(
            {
                "Title": title,
                "Authors": authors,
                "Year": year,
                "Abstract": abstract,
                "URL": link,
                "PDF_URL": pdf_url,
                "CitedBy": cited_by,
            }
        )
    return results


def _fetch_pages(params, num_results):
    """Fetch as many result pages as needed (10 results per page),
    sleeping politely between requests to avoid a Scholar block."""
    results = []
    start = 0
    session = _build_session()
    while len(results) < num_results:
        page_params = dict(params)
        if start:
            page_params["start"] = start
        url = "https://scholar.google.com/scholar?" + urlencode(page_params)
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            print(f"Failed to fetch data. HTTP Status code: {response.status_code}")
            break
        soup = BeautifulSoup(response.text, "html.parser")
        page = _parse_results(soup)
        if not page:
            body = soup.get_text(" ", strip=True).lower()
            if "not a robot" in body or "unusual traffic" in body:
                raise ScholarBlockedError(
                    "Google Scholar is serving its anti-robot page to this client. "
                    "Fix: export browser cookies to cookies.txt next to the server "
                    "(or set GOOGLE_SCHOLAR_COOKIES_FILE), or run searches through "
                    "a real browser session. See README."
                )
            break  # genuinely no more results
        results.extend(page)
        start += RESULTS_PER_PAGE
        if len(results) < num_results:
            time.sleep(random.uniform(2.0, 5.0))
    return results[:num_results]


def google_scholar_search(query, num_results=5):
    """Search Google Scholar using a simple keyword query.

    Returns a list of dicts with Title, Authors, Year, Abstract, URL,
    PDF_URL (direct full-text link when Scholar shows one) and CitedBy.
    """
    return _fetch_pages({"q": query, "hl": "en"}, num_results)


def advanced_google_scholar_search(query, author=None, year_range=None, num_results=5):
    """Search Google Scholar with advanced filters (author, year range).

    year_range: tuple/list (start_year, end_year).
    """
    params = {"q": query, "hl": "en"}
    if author:
        params["as_sauthors"] = author
    if year_range:
        start_year, end_year = year_range
        params["as_ylo"] = start_year
        params["as_yhi"] = end_year
    return _fetch_pages(params, num_results)


if __name__ == "__main__":
    results = google_scholar_search("multidimensional poverty municipalities Brazil", num_results=5)
    for r in results:
        print(f"\nTitle: {r['Title']}\nYear: {r['Year']}\nPDF: {r['PDF_URL']}\nURL: {r['URL']}")
        print("-" * 80)

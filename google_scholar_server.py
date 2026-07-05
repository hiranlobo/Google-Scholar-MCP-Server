from typing import Any, List, Dict, Optional, Union
import asyncio
import logging
from mcp.server.fastmcp import FastMCP
from google_scholar_web_search import google_scholar_search, advanced_google_scholar_search
from scholarly import scholarly

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastMCP server for PubMed and Google Scholar
mcp = FastMCP("scholar_pubmed")

@mcp.tool()
async def search_google_scholar_key_words(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    logging.info(f"Searching Google Scholar for articles with query: {query}, num_results: {num_results}")
    """
    Search for articles on Google Scholar using key words.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)

    Returns:
        List of dictionaries containing article information
    """
    try:
        results = await asyncio.to_thread(google_scholar_search, query, num_results)
        return results
    except Exception as e:
        return [{"error": f"An error occurred while searching Google Scholar: {str(e)}"}]

@mcp.tool()
async def search_google_scholar_advanced(query: str, author: Optional[str] = None, year_range: Optional[tuple] = None, num_results: int = 5) -> List[Dict[str, Any]]:
    logging.info(f"Performing advanced search with parameters: {locals()}")
    """
    Search for articles on Google Scholar using advanced filters.

    Args:
        query: General search query
        author: Author name
        year_range: tuple containing (start_year, end_year)
        num_results: Number of results to return (default: 5)

    Returns:
        List of dictionaries containing article information
    """
    try:
        results = await asyncio.to_thread(
            advanced_google_scholar_search,
            query, author, year_range, num_results
        )
        return results
    except Exception as e:
        return [{"error": f"An error occurred while performing advanced search on Google Scholar: {str(e)}"}]

@mcp.tool()
async def get_author_info(author_name: str) -> Dict[str, Any]:
    logging.info(f"Retrieving author information for: {author_name}")
    """
    Get detailed information about an author from Google Scholar.

    Args:
        author_name: Name of the author to search for

    Returns:
        Dictionary containing author information
    """
    try:
        search_query = scholarly.search_author(author_name)
        author = await asyncio.to_thread(next, search_query)
        filled_author = await asyncio.to_thread(scholarly.fill, author)
        
        # Extract relevant information
        author_info = {
            "name": filled_author.get("name", "N/A"),
            "affiliation": filled_author.get("affiliation", "N/A"),
            "interests": filled_author.get("interests", []),
            "citedby": filled_author.get("citedby", 0),
            "publications": [
                {
                    "title": pub.get("bib", {}).get("title", "N/A"),
                    "year": pub.get("bib", {}).get("pub_year", "N/A"),
                    "citations": pub.get("num_citations", 0)
                }
                for pub in filled_author.get("publications", [])[:5]  # Limit to top 5 publications
            ]
        }
        return author_info
    except Exception as e:
        return {"error": f"An error occurred while retrieving author information: {str(e)}"}

@mcp.tool()
async def download_pdf(url: str, dest_path: str) -> Dict[str, Any]:
    """
    Download a PDF (e.g. a PDF_URL returned by the search tools) to a local file.

    Args:
        url: Direct link to the PDF
        dest_path: Absolute path where the PDF should be saved (including .pdf name)

    Returns:
        Dictionary with status, saved path or error detail
    """
    logging.info(f"Downloading PDF from {url} to {dest_path}")
    import os
    import requests

    def _download():
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        is_pdf = "pdf" in content_type.lower() or resp.content[:5] == b"%PDF-"
        if not is_pdf:
            return {
                "status": "not_pdf",
                "detail": f"Response is not a PDF (Content-Type: {content_type}). Keep the URL/DOI as reference instead.",
                "url": url,
            }
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        return {"status": "ok", "path": dest_path, "bytes": len(resp.content)}

    try:
        return await asyncio.to_thread(_download)
    except Exception as e:
        return {"status": "error", "detail": str(e), "url": url}

if __name__ == "__main__":
    mcp.run()

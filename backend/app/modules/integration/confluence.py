from typing import Dict, Any
import logging
import base64
from urllib.parse import quote

from app.core.utils.bi_utils import make_async_web_call
from app.core.utils.web_scraping_utils import html2text

logger = logging.getLogger(__name__)


class ConfluenceConnector:

    def __init__(self, subdomain: str, email: str, api_token: str):
        self.subdomain = subdomain
        self.email = email
        self.api_token = api_token
        self.base_url = f"https://{subdomain}"

    def _get_auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers for Confluence API."""
        auth_str = f"{self.email}:{self.api_token}"
        auth_bytes = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_bytes}",
        }

    async def get_page_content(
        self,
        page_id: str,
    ) -> Dict[str, Any]:
        """
        Get page content from Confluence by page ID.
        
        Returns:
            Dict containing:
            - status: HTTP status code
            - data: Response data with:
                - html_parsed: Parsed HTML content as text
                - raw_content: Raw HTML content from Confluence
                - page_info: Page metadata (title, id, etc.)
        """
        complete_url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage,body.view"

        headers = self._get_auth_headers()

        # For GET requests, we pass empty payload
        response = await make_async_web_call(
            method="GET", url=complete_url, headers=headers, payload={}
        )

        if response.get("status") == 200 and "data" in response:
            page_data = response["data"]
            
            # Extract raw HTML content
            raw_html = ""
            if "body" in page_data:
                if "storage" in page_data["body"] and "value" in page_data["body"]["storage"]:
                    raw_html = page_data["body"]["storage"]["value"]
                elif "view" in page_data["body"] and "value" in page_data["body"]["view"]:
                    raw_html = page_data["body"]["view"]["value"]
            
            # Parse HTML to text
            html_parsed = html2text(raw_html) if raw_html else ""
            
            # Extract page metadata
            page_info = {
                "id": page_data.get("id"),
                "title": page_data.get("title"),
                "type": page_data.get("type"),
                "space": page_data.get("space", {}).get("key") if page_data.get("space") else None,
                "version": page_data.get("version", {}).get("number") if page_data.get("version") else None,
            }

            return {
                "status": response["status"],
                "data": {
                    "html_parsed": html_parsed,
                    "raw_content": raw_html,
                    "page_info": page_info,
                },
            }

        return response

    async def get_page_by_title(
        self,
        space_key: str,
        title: str,
    ) -> Dict[str, Any]:
        """
        Get page content from Confluence by space key and title.
        
        Args:
            space_key: The Confluence space key
            title: The page title
            
        Returns:
            Dict containing page content (same format as get_page_content)
        """
        # First, search for the page by title
        search_url = f"{self.base_url}/rest/api/content?spaceKey={space_key}&title={title}&expand=body.storage,body.view"

        headers = self._get_auth_headers()

        response = await make_async_web_call(
            method="GET", url=search_url, headers=headers, payload={}
        )

        if response.get("status") == 200 and "data" in response:
            results = response["data"].get("results", [])
            
            if not results:
                return {
                    "status": 404,
                    "data": {"error": f"Page with title '{title}' not found in space '{space_key}'"},
                }
            
            # Get the first matching page
            page_data = results[0]
            
            # Extract raw HTML content
            raw_html = ""
            if "body" in page_data:
                if "storage" in page_data["body"] and "value" in page_data["body"]["storage"]:
                    raw_html = page_data["body"]["storage"]["value"]
                elif "view" in page_data["body"] and "value" in page_data["body"]["view"]:
                    raw_html = page_data["body"]["view"]["value"]
            
            # Parse HTML to text
            html_parsed = html2text(raw_html) if raw_html else ""
            
            # Extract page metadata
            page_info = {
                "id": page_data.get("id"),
                "title": page_data.get("title"),
                "type": page_data.get("type"),
                "space": page_data.get("space", {}).get("key") if page_data.get("space") else None,
                "version": page_data.get("version", {}).get("number") if page_data.get("version") else None,
            }

            return {
                "status": response["status"],
                "data": {
                    "html_parsed": html_parsed,
                    "raw_content": raw_html,
                    "page_info": page_info,
                },
            }

        return response

    async def search_pages(
        self,
        keywords: str,
        space_key: str = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Search for pages in Confluence by keywords.
        
        Args:
            keywords: Keywords to search for in page content
            space_key: Optional space key to limit search to a specific space
            limit: Maximum number of results to return (default: 25)
            
        Returns:
            Dict containing:
            - status: HTTP status code
            - data: Response data with:
                - page_ids: List of page IDs that match the keywords
                - pages: List of page metadata (id, title, space, type) for each match
                - total_results: Total number of results found
        """
        # Build CQL query
        # text~"keywords" searches for text containing the keywords
        cql_query = f'text~"{keywords}"'
        
        # If space_key is provided, limit search to that space
        if space_key:
            cql_query = f'space={space_key} AND {cql_query}'
        
        # URL encode the CQL query
        encoded_cql = quote(cql_query)
        
        search_url = f"{self.base_url}/rest/api/content/search?cql={encoded_cql}&limit={limit}"
        
        headers = self._get_auth_headers()
        
        response = await make_async_web_call(
            method="GET", url=search_url, headers=headers, payload={}
        )
        
        if response.get("status") == 200 and "data" in response:
            results = response["data"].get("results", [])
            
            # Extract page IDs and metadata
            page_ids = []
            pages = []
            
            for page in results:
                page_id = page.get("id")
                if page_id:
                    page_ids.append(page_id)
                    pages.append({
                        "id": page_id,
                        "title": page.get("title"),
                        "type": page.get("type"),
                        "space": page.get("space", {}).get("key") if page.get("space") else None,
                        "url": f"{self.base_url}{page.get('_links', {}).get('webui', '')}" if page.get("_links", {}).get("webui") else None,
                    })
            
            total_results = response["data"].get("size", len(results))
            
            return {
                "status": response["status"],
                "data": {
                    "page_ids": page_ids,
                    "pages": pages,
                    "total_results": total_results,
                },
            }
        
        return response


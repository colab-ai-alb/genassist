"""
Confluence node implementation using the BaseNode class.
"""

import logging
from typing import Dict, Any
from uuid import UUID

from ..base_node import BaseNode
from app.modules.integration.confluence import ConfluenceConnector
from app.services.app_settings import AppSettingsService
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


class ConfluenceNode(BaseNode):
    """
    Processor for interacting with Confluence via the REST API using the BaseNode approach.
    Supports getting page content, searching pages, and getting pages by title.
    Expects credentials and operation parameters in the incoming configuration.
    """

    async def process(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Confluence operations.

        Args:
            config: The resolved configuration for the node.

        Returns:
            Dictionary with Confluence API response payload.
        """
        app_settings_id = config.get("app_settings_id")
        operation = str(config.get("operation", "get_page_content")).lower()

        params = {
            "configuration variables": app_settings_id,
            "operation": operation,
        }

        missing_parameters = [key for key, value in params.items() if not value]

        if missing_parameters:
            error_msg = f"Confluence node missing these parameters: {', '.join(missing_parameters)}"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        try:
            # Get app settings from database
            app_settings_service = injector.get(AppSettingsService)
            app_settings = await app_settings_service.get_by_id(UUID(app_settings_id))

            # Extract subdomain, email, and api_token from app settings values
            values = (
                app_settings.values if isinstance(app_settings.values, dict) else {}
            )

            subdomain = str(values.get("confluence_subdomain"))
            email = str(values.get("confluence_email"))
            api_token = str(values.get("confluence_api_token"))

            confluence_connector = ConfluenceConnector(
                subdomain=subdomain, email=email, api_token=api_token
            )

            # Route to appropriate operation
            if operation == "get_page_content":
                return await self._get_page_content(confluence_connector, config)
            elif operation == "get_page_by_title":
                return await self._get_page_by_title(confluence_connector, config)
            elif operation == "search_pages":
                return await self._search_pages(confluence_connector, config)
            else:
                error_msg = f"Unknown operation: {operation}. Supported operations: get_page_content, get_page_by_title, search_pages"
                logger.error(error_msg)
                return {"status": 400, "data": {"error": error_msg}}

        except Exception as e:
            error_msg = f"Error in Confluence operation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": 500, "data": {"error": error_msg}}

    async def _get_page_content(
        self, connector: ConfluenceConnector, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get page content by page ID."""
        page_id = str(config.get("page_id"))

        if not page_id:
            error_msg = "Confluence get_page_content operation missing page_id parameter"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        result = await connector.get_page_content(page_id=page_id)
        return result

    async def _get_page_by_title(
        self, connector: ConfluenceConnector, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get page content by space key and title."""
        space_key = str(config.get("space_key"))
        title = str(config.get("title"))

        params = {
            "space_key": space_key,
            "title": title,
        }

        missing_parameters = [
            key for key, value in params.items() if not value
        ]

        if missing_parameters:
            error_msg = f"Confluence get_page_by_title operation missing these parameters: {', '.join(missing_parameters)}"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        result = await connector.get_page_by_title(space_key=space_key, title=title)
        return result

    async def _search_pages(
        self, connector: ConfluenceConnector, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Search for pages by keywords."""
        keywords = str(config.get("keywords"))
        space_key = config.get("space_key")
        limit = config.get("limit", 25)

        if not keywords:
            error_msg = "Confluence search_pages operation missing keywords parameter"
            logger.error(error_msg)
            return {"status": 400, "data": {"error": error_msg}}

        # Convert limit to int if provided
        if limit:
            try:
                limit = int(limit)
            except (ValueError, TypeError):
                limit = 25
                logger.warning(f"Invalid limit value, using default: {limit}")

        result = await connector.search_pages(
            keywords=keywords,
            space_key=str(space_key) if space_key else None,
            limit=limit,
        )
        return result


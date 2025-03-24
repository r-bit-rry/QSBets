import os
import requests
from logger import get_logger

logger = get_logger(__name__)


class BingSearch:
    def __init__(self, params: dict):
        """
        Initialize BingSearch with default parameters.
        These parameters will be used for every search unless overridden.
        Expects that BING_API_KEY is set in environment variables.
        See:
         - https://learn.microsoft.com/en-us/bing/search-apis/bing-web-search/reference/query-parameters
        """
        self.default_params = params.copy()
        # Ensure default values if not explicitly provided.
        if "freshness" not in self.default_params:
            self.default_params["freshness"] = "Week"
        if "count" not in self.default_params:
            self.default_params["count"] = 5
        if "mkt" not in self.default_params:
            self.default_params["mkt"] = "en-US"
        self.api_key = os.getenv("BING_API_KEY")
        if not self.api_key:
            raise ValueError("BING_API_KEY is not set in environment variables.")
        self.endpoint = "https://api.bing.microsoft.com/v7.0/search"

    def search(self, query: str, extra_params: dict = None) -> list:
        """
        Execute a search query on Bing and retrieve the web pages for all results.

        This method merges the default parameters with extra parameters provided at
        search time. Extra parameters can override the default search parameters.
        It then retrieves each webpage in the search results. If a VisitTool instance
        is provided via the `visit_tool` parameter, it will be used to retrieve pages,
        otherwise requests.get will be used as a fallback.

        Parameters:
            query (str): The search query.
            extra_params (dict, optional): Additional parameters to override defaults.

        Returns:
            dict: The JSON response from Bing with an additional key "retrieved_pages" which
                  is a list containing the HTML content of each search result's web page.
        """
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        # Merge default params with extra_params (if any), giving precedence to extra_params.
        params = self.default_params.copy()
        if extra_params:
            params.update(extra_params)
        params["q"] = query

        response = requests.get(self.endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        # Retrieve the web page content for each search result.
        retrieved_pages = []
        try:
            if (
                "webPages" in data
                and "value" in data["webPages"]
                and isinstance(data["webPages"]["value"], list)
                and len(data["webPages"]["value"]) > 0
            ):
                for result in data["webPages"]["value"]:
                    url = result.get("url")
                    if url:
                        retrieved_pages.append(url)
        except Exception as e:
            logger.error(f"Failed to retrieve pages: {str(e)}")

        return retrieved_pages

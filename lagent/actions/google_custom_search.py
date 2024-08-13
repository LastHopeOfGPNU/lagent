import re
import time
import json
import random
import datetime
import logging
import warnings
import requests
from typing import List, Optional, Type

from lagent.actions.parser import BaseParser, JsonParser
from lagent.actions.bing_browser import BaseAction
from lagent.actions import BaseAction, tool_api


class GoogleCustomSearch(BaseAction):
    """Wrapper around the Google Csutom Search API.

    Args:
        BaseAction (_type_): _description_
    """
    def __init__(self,
                 api_key: str,
                 search_engine_id: str,
                 topk: int = 3,
                 black_list: List[str] = [],
                 description: Optional[dict] = None,
                 parser: Type[BaseParser] = JsonParser,
                 enable: bool = True):
        self.topk = topk
        self.black_list = black_list
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.regex_date = {
            "seconds": re.compile(r'(\d+)\s+seconds?\s+ago'),
            "minutes": re.compile(r'(\d+)\s+minutes?\s+ago'),
            "hours": re.compile(r'(\d+)\s+hours?\s+ago'),
            "days": re.compile(r'(\d+)\s+days?\s+ago'),
            "weeks": re.compile(r'(\d+)\s+weeks?\s+ago')
        }
        super().__init__(description, parser, enable)

    @tool_api
    def search(self, query: str, num_results: int = 10, date_restrict: str = None) -> dict:
        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": query,
            "num": num_results,
            "dateRestrict": date_restrict
        }
        for attempt in range(3):
            try:
                response = requests.get("https://www.googleapis.com/customsearch/v1", params=params).json()
                return self._parse_response(response)
            except Exception as e:
                logging.exception(str(e))
                warnings.warn(f'Retry {attempt + 1}/3 due to error: {e}')
                time.sleep(random.randint(2, 5))
        raise Exception('Failed to get search results from Google after retries.')
    
    def _parse_response(self, response: dict) -> dict:
        """
        Returns:
            dict: {index: {"url", "summ", "title", "date"}}
        """
        raw_results = []
        for item in response["items"]:
            if "snippet" not in item:
                print(f"no snippet for {item}")
                continue
            page_date = item["snippet"].split("...")[0].strip()
            try:
                for key, regex in self.regex_date.items():
                    if regex.match(page_date):
                        delta = {key: int(regex.match(page_date).group(1))}
                        date_obj = datetime.datetime.now() - datetime.timedelta(**delta)
                        break
                else:
                    date_obj = datetime.datetime.strptime(page_date, '%b %d, %Y')
                str_date = date_obj.strftime('%Y-%m-%d')
            except:
                str_date = None
            raw_results.append(
                (item['link'], item['snippet'], item['title'], str_date))
        return self._filter_results(raw_results)
    
    def _filter_results(self, results: List[tuple]) -> dict:
        filtered_results = {}
        count = 0
        for url, snippet, title, date in results:
            if all(domain not in url
                   for domain in self.black_list) and not url.endswith('.pdf'):
                filtered_results[count] = {
                    'url': url,
                    'summ': json.dumps(snippet, ensure_ascii=False)[1:-1],
                    'title': title,
                    'date': date
                }
                count += 1
                if count >= self.topk:
                    break
        return filtered_results

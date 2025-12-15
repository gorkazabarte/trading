from typing import Optional
from requests import post
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

BASE_URL = "https://localhost:5001/v1/api/"


def is_stock_section(section: dict) -> bool:
    return section.get('secType') == 'STK'


def find_stock_contract_id(results: list) -> Optional[str]:
    for result in results:
        sections = result.get('sections', [])
        for section in sections:
            if is_stock_section(section):
                return result.get('conid')
    return None


def get_fallback_contract_id(results: list) -> Optional[str]:
    return results[0].get('conid') if results else None


def contract_search(symbol: str) -> Optional[str]:
    endpoint = "iserver/secdef/search"

    json_body = {
        "name": False,
        "symbol": symbol,
        "secType": "STK"
    }

    contract_req = post(url=BASE_URL + endpoint, json=json_body, verify=False)
    results = contract_req.json()

    stock_contract_id = find_stock_contract_id(results)
    if stock_contract_id:
        return stock_contract_id

    return get_fallback_contract_id(results)


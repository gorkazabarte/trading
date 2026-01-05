from json import dumps

from requests import get
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def contract_strikes():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/secdef/info"

    conid = "conid=11004968"
    secType = "secType=FUT"
    month = "month=DEC25"
    exchange = "exchange=CME"
    strike = "strike=4800"
    right = "right=C"

    query_params = "&".join([conid, secType, month, exchange, strike, right])

    request_url = "".join([base_url, endpoint, "?", query_params])
    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        contract_json = dumps(contract_req.json(), indent=2)
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")


from requests import get, post

# Disable SSL Warnings - Insecure connection is between you and the localhost.
# You may replace the SSL certificate in /root/conf.yaml and
# modify sslCert and sslPwd fields to use secure connection.
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def get_market_data(conid: int, period: str, bar: str):
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "hmds/history"

    conid = f"conid={conid}"
    period = f"period={period}"
    bar = f"bar={bar}"
    outsideRth = "outsideRth=true"
    barType = "barType=midpoint"

    query_params = "&".join([conid, period, bar, outsideRth, barType])

    request_url = "".join([base_url, endpoint, "?", query_params])
    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        return contract_req.json()
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")

def get_market_snapshot(conid: int, fields: str = "31,84,86,87"):
    """
    Get market snapshot for a contract.

    Common fields:
    - 31: Last Price
    - 84: Bid Price
    - 86: Ask Price
    - 87: Volume
    - 7221: Close Price (Previous Day)
    """
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/marketdata/snapshot"

    conids_param = f"conids={conid}"
    fields_param = f"fields={fields}"

    query_params = "&".join([conids_param, fields_param])

    request_url = "".join([base_url, endpoint, "?", query_params])

    contract_req = get(request_url, verify=False)

    if contract_req.status_code == 200:
        return contract_req.json()
    elif contract_req.status_code == 400:
        json_body = {
            "conids": [conid],
            "fields": fields.split(',')
        }
        contract_req = post(f"{base_url}{endpoint}", json=json_body, verify=False)
        if contract_req.status_code == 200:
            return contract_req.json()
        else:
            raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")
    else:
        raise Exception(f"Error: {contract_req.status_code}, Response text: {contract_req.text}")

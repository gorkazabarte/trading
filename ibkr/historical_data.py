from json import dumps
from requests import get

# Disable SSL Warnings - Insecure connection is between you and the localhost.
# You may replace the SSL certificate in /root/conf.yaml and
# modify sslCert and sslPwd fields to use secure connection.
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def get_market_data():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "hmds/history"

    conid = "conid=265598"
    period = "period=1w"
    bar= "bar=1d"
    outsideRth = "outsideRth=true"
    barType = "barType=midpoint"

    query_params = "&".join([conid, period, bar, outsideRth, barType])

    request_url = "".join([base_url, endpoint, "?", query_params])
    contract_req = get(request_url, verify=False)

    print(f"Request URL: {request_url}")
    print(f"Response: {contract_req}")

    if contract_req.status_code == 200:
        contract_json = dumps(contract_req.json(), indent=2)
        print(contract_json)
    else:
        print(f"Error: {contract_req.status_code}")
        print(f"Response text: {contract_req.text}")

def get_market_snapshot():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/marketdata/snapshot"

    conid = "conid=265598,8314"
    fields = "fields=31,83,84,86"

    query_params = "&".join([conid, fields])

    request_url = "".join([base_url, endpoint, "?", query_params])
    contract_req = get(request_url, verify=False)

    print(f"Request URL: {request_url}")
    print(f"Response: {contract_req}")

    if contract_req.status_code == 200:
        contract_json = dumps(contract_req.json(), indent=2)
        print(contract_json)
    else:
        print(f"Error: {contract_req.status_code}")
        print(f"Response text: {contract_req.text}")

if __name__ == "__main__":
    # get_market_snapshot()
    get_market_data()

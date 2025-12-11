from json import dumps
from requests import get

# Disable SSL Warnings - Insecure connection is between you and the localhost.
# You may replace the SSL certificate in /root/conf.yaml and
# modify sslCert and sslPwd fields to use secure connection.
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def contract_info():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/secdef/info"

    conid = "conid=11004968"
    secType = "secType=FUT"
    month = "month=DEC25"
    exchange = "exchange=CME"

    query_params = "&".join([conid, secType, month, exchange])

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
    contract_info()

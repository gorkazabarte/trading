from json import dumps
from requests import post

# Disable SSL Warnings - Insecure connection is between you and the localhost.
# You may replace the SSL certificate in /root/conf.yaml and
# modify sslCert and sslPwd fields to use secure connection.
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def contract_search():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/secdef/search"

    json_body: dict = {
        "name": False,
        "symbol": "AEVA",
        "secType": "STK"
    }

    contract_req = post(url=base_url + endpoint, json=json_body, verify=False)
    contract_json = dumps(contract_req.json(), indent=2)
    print(contract_json)

if __name__ == "__main__":
    contract_search()

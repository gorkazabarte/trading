from json import dumps
from requests import post

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def order_request():

    account_id: str = "U23158610"
    base_url: str = "https://localhost:5001/v1/api/"
    endpoint: str = f"iserver/account/{account_id}/orders"

    json_body: dict = {
        "orders": [
            {
                "conid": 690184960,
                "orderType": "LMT",
                "side": "SELL",
                "tif": "DAY",
                "quantity": 2,
                "price": 15.50
            }
        ]
    }

    order_req = post(url=base_url + endpoint, json=json_body, verify=False)
    order_json = order_req.json()

    print(f"Request URL: {base_url + endpoint}")
    print(f"Response: {order_req}")
    print(dumps(order_json, indent=2))

    # Handle confirmation if required
    if isinstance(order_json, list) and len(order_json) > 0 and 'id' in order_json[0]:
        reply_id = order_json[0]['id']
        print(f"Order requires confirmation. Reply ID: {reply_id}")
        print(f"Message: {order_json[0]['message']}")

        # Send confirmation reply
        reply_endpoint = f"iserver/reply/{reply_id}"
        reply_body = {"confirmed": True}

        print(f"\nSending confirmation...")
        reply_req = post(url=base_url + reply_endpoint, json=reply_body, verify=False)
        reply_json = reply_req.json()

        print(f"Confirmation Response: {reply_req}")
        print(dumps(reply_json, indent=2))

if __name__ == "__main__":
    order_request()
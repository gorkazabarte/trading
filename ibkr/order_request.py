from requests import post

from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def order_request(account_id: str, action: str, conid: int, quantity: int, order_type: str, price: float):

    base_url: str = "https://localhost:5001/v1/api/"
    endpoint: str = f"iserver/account/{account_id}/orders"

    json_body: dict = {
        "orders": [
            {
                "conid": 690184960,
                "orderType": order_type,
                "side": action,
                "tif": "DAY",
                "quantity": quantity,
                "price": price
            }
        ]
    }

    order_req = post(url=base_url + endpoint, json=json_body, verify=False)
    order_json = order_req.json()

    if isinstance(order_json, list) and len(order_json) > 0 and 'id' in order_json[0]:
        reply_id = order_json[0]['id']

        reply_endpoint = f"iserver/reply/{reply_id}"
        reply_body = {"confirmed": True}

        reply_req = post(url=base_url + reply_endpoint, json=reply_body, verify=False)
        reply_json = reply_req.json()

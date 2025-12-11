from requests import get

# Disable SSL Warnings - Insecure connection is between you and the localhost.
# You may replace the SSL certificate in /root/conf.yaml and
# modify sslCert and sslPwd fields to use secure connection.
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)

def confirm_authentication():
    base_url = "https://localhost:5001/v1/api/"
    endpoint = "iserver/auth/status"

    auth_req = get(url=base_url + endpoint, verify=False)
    print(auth_req)
    print(auth_req.text)

if __name__ == "__main__":
    confirm_authentication()

import time
import httpx

class IAMTokenHandler:
    def __init__(self):
        self.token_cache = {}

    def get_token(self, api_key, endpoint):
        key = (api_key, endpoint)
        if key in self.token_cache:
            token, expiry = self.token_cache[key]
            if time.time() < expiry - 60:
                return token  # not expired

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key
        }

        response = httpx.post(endpoint, data=data, headers=headers)
        response.raise_for_status()

        token = response.json()["access_token"]
        expires_in = response.json().get("expires_in", 3600)
        self.token_cache[key] = (token, time.time() + expires_in)
        return token

    def apply_auth(self, request, auth_config):
        token = self.get_token(
            auth_config["api_key"],
            auth_config.get("iam_endpoint", "https://iam.cloud.ibm.com/identity/token")
        )
        request.headers["Authorization"] = f"Bearer {token}"

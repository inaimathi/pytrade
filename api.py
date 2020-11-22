import getpass
import time

import keyring
import requests


class WealthsimpleApi:
    def __init__(self, email):
        if keyring.get_password("wealthsimple", email) is None:
            password = getpass.getpass(prompt="Password: ")
            keyring.set_password("wealthsimple", email, password)
        else:
            password = keyring.get_password("wealthsimple", email)
        self.email = email
        self.jar = requests.cookies.RequestsCookieJar()
        self._tokens_from(self.login(password))

    def _tokens_from(self, res):
        self.refreshed_at = time.time()
        self.access_token = res.headers["X-Access-Token"]
        self.refresh_token = res.headers["X-Refresh-Token"]
        return True

    def _req(self, method, url, data=None):
        headers = {"Authorization": self.access_token}
        if data is None:
            res = method(url, cookies=self.jar, headers=headers)
        else:
            res = method(url, cookies=self.jar, headers=headers, data=data)
        if res.status_code == 200:
            if res.content == b"OK":  # We're looking at a refresh here
                return res
            try:
                return res.json()
            except Exception:
                return res
        return res

    def _get(self, url):
        return self._req(requests.get, url)

    def _post(self, url, data):
        return self._req(requests.post, url, data)

    def login(self, password):
        otp = getpass.getpass(prompt="2FA Code: ")
        return requests.post(
            "https://trade-service.wealthsimple.com/auth/login",
            {"email": self.email, "password": password, "otp": otp},
            cookies=self.jar,
        )

    def refresh(self, force=False):
        if force or (time.time() - self.refreshed_at > (60 * 10)):
            res = self._post(
                "https://trade-service.wealthsimple.com/auth/refresh",
                {"refresh_token": self.refresh_token},
            )
            return self._tokens_from(res)
        return False

    def accounts(self):
        self.refresh()
        res = self._get("https://trade-service.wealthsimple.com/account/list")
        if type(res) is "dict":
            return res["results"]
        return res

    def orders(self):
        self.refresh()
        return self._get("https://trade-service.wealthsimple.com/orders")

    def place_order(self, account_id, security_id, quantity, order_type, dry_run=False):
        order = {
            "account_id": account_id,
            "security_id": security_id,
            "quantity": quantity,
            "order_type": order_type,
            "order_sub_type": "market",
            "time_in_force": "day",
        }
        if dry_run:
            return order
        self.refresh()
        return self._post("https://trade-service.wealthsimple.com/orders", order)

    def buy(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        assert quantity or value
        if quantity is None:
            cur_price = self.security(security_id)["quote"]["amount"]
            quantity = value / cur_price
        return self.place_order(
            account_id, security_id, quantity, "buy_quantity", dry_run=dry_run
        )

    def sell(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        assert quantity or value
        if quantity is None:
            cur_price = self.security(security_id)["quote"]["amount"]
            quantity = value / cur_price
        return self.place_order(
            account_id, security_id, quantity, "sell_quantity", dry_run=dry_run
        )

    def activity(self):
        self.refresh()
        return self._get("https://trade-service.wealthsimple.com/account/activities")

    def me(self):
        self.refresh()
        return self._get("https://trade-service.wealthsimple.com/me")

    def forex(self):
        self.refresh()
        return self._get("https://trade-service.wealthsimple.com/forex")

    def security(self, security_id):
        self.refresh()
        return self._get(
            f"https://trade-service.wealthsimple.com/securities/{security_id}"
        )

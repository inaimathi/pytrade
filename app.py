import getpass
import json
import os
import time

import keyring
import requests

import util

BTC = "sec-z-btc-4ca670cac10139ce8678b84836231606"
ETH = "sec-z-eth-dc40261c82a191b11e53426aa25d91af"


class Crypto:
    def __init__(self, email):
        self.SECURITIES = [BTC, ETH]
        if keyring.get_password("wealthsimple", email) is None:
            password = getpass.getpass(prompt="Password: ")
            keyring.set_password("wealthsimple", email, password)
        else:
            password = keyring.get_password("wealthsimple", email)
        self.email = email
        self.jar = requests.cookies.RequestsCookieJar()
        self.login_res = self.login(password)
        self.access_token = self.login_res.headers["X-Access-Token"]
        self.refresh_token = self.login_res.headers["X-Refresh-Token"]

    def _req(self, method, url, data=None):
        headers = {"Authorization": self.access_token}
        if data is None:
            res = method(url, cookies=self.jar, headers=headers)
        else:
            res = method(url, cookies=self.jar, headers=headers, data=data)
        if res.status_code == 200:
            return res.json()
        return res

    def _get(self, url):
        return self._req(requests.get, url)

    def _post(self, url, data):
        return self._req(requests.post, url)

    def login(self, password):
        otp = getpass.getpass(prompt="2FA Code: ")
        return requests.post(
            "https://trade-service.wealthsimple.com/auth/login",
            {"email": self.email, "password": password, "otp": otp},
            cookies=self.jar,
        )

    def accounts(self):
        res = self._get("https://trade-service.wealthsimple.com/account/list")
        if type(res) is "dict":
            return res["results"]
        return res

    def orders(self):
        return self._get("https://trade-service.wealthsimple.com/orders")

    def place_order(self, security_id, quantity, order_type, dry_run=False):
        order = {
            "security_id": security_id,
            "quantity": quantity,
            "order_type": order_type,
            "order_sub_type": "market",
            "time_in_force": "day",
        }
        return self._post("https://trade-service.wealthsimple.com/orders", order)

    def buy(self, security_id, quantity=None, value=None, dry_run=False):
        assert quantity or value
        if quantity is None:
            cur_price = self.security(security_id)["quote"]["amount"]
            value / cur_price
        return self.place_order(security_id, quantity, "buy_quantity", dry_run=dry_run)

    def sell(self, security_id, quantity=None, value=None, dry_run=False):
        assert quantity or value
        if quantity is None:
            cur_price = self.security(security_id)["quote"]["amount"]
            value / cur_price
        return self.place_order(security_id, quantity, "sell_quantity", dry_run=dry_run)

    def activity(self):
        return self._get("https://trade-service.wealthsimple.com/account/activities")

    def me(self):
        return self._get("https://trade-service.wealthsimple.com/me")

    def forex(self):
        return self._get("https://trade-service.wealthsimple.com/forex")

    def security(self, security_id):
        return self._get(
            f"https://trade-service.wealthsimple.com/securities/{security_id}"
        )

    # Higher level operations
    def quote(self, sec_id):
        security = self.security(sec_id)
        return {
            "id": security["id"],
            "symbol": security["stock"]["symbol"],
            "name": security["stock"]["symbol"],
            "quote": {k: security["quote"][k] for k in ["amount", "ask", "bid"]},
            "date": security["quote"]["quote_date"],
        }

    def market_quote(self):
        return [self.quote(s) for s in self.SECURITIES]

    def crypto_summary(self):
        res = self.accounts()["results"][0]
        return {
            "id": res["id"],
            "custodian": res["custodian_account_number"],
            "balance": res["current_balance"]["amount"],
            "available": res["available_to_withdraw"]["amount"],
            "withdrawn": res["withdrawn_earnings"]["amount"],
            "positions": {
                k: (self.quote(k)["quote"]["amount"] * v)
                for k, v in res["position_quantities"].items()
            },
        }


def scratch():
    def _minimal(rec):
        return (
            rec["symbol"],
            (rec["quote"]["amount"], rec["quote"]["ask"], rec["quote"]["bid"]),
        )

    lines = util.json_lines("/home/inaimathi/.pytrade/history.json")
    fst = True
    for (a, b) in util.pairwise((_minimal(ln[0]) for ln in lines)):
        if fst:
            yield a
            fst = False
        (sym, (aamt, aask, abid)) = a
        (_, (bamt, bask, bbid)) = b

        yield (sym, (bamt - aamt, bask - aask, bbid - abid))


def monitor(api, path="~/.pytrade/history.json"):
    while True:
        p = os.path.expanduser(path)
        with open(p, "a") as f:
            f.write(json.dumps(api.market_quote()))
            f.write("\n")
        time.sleep(60)

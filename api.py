import getpass
import time

import keyring
import requests
import util
from util import BTC, ETH


def _quant(quantity, value, price):
    assert quantity or value
    assert price
    if quantity is None:
        return round(value / price, 8), value
    return quantity, quantity * price


def _pos(api, k, v):
    price = api.quote(k)["quote"]["amount"]
    return {"quantity": v, "value": price * v, "price": price}


def _taxed(amt, rate):
    return round(amt - (amt * rate), 2)


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

    def _get(self, path):
        return self._req(requests.get, f"https://trade-service.wealthsimple.com/{path}")

    def _post(self, path, data):
        return self._req(
            requests.post, f"https://trade-service.wealthsimple.com/{path}", data
        )

    def login(self, password):
        otp = getpass.getpass(prompt="2FA Code: ")
        return requests.post(
            "https://trade-service.wealthsimple.com/auth/login",
            {"email": self.email, "password": password, "otp": otp},
            cookies=self.jar,
        )

    def refresh(self, force=False):
        if force or (time.time() - self.refreshed_at > (60 * 10)):
            res = self._post("auth/refresh", {"refresh_token": self.refresh_token})
            return self._tokens_from(res)
        return False

    def accounts(self):
        self.refresh()
        res = self._get("account/list")
        if type(res) is dict:
            return res["results"]
        return res

    def orders(self):
        self.refresh()
        return self._get("orders")

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
        return self._post("orders", order)

    def buy(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        price = self.security(security_id)["quote"]["amount"]
        q, _ = _quant(quantity, value, price)
        return self.place_order(
            account_id, security_id, q, "buy_quantity", dry_run=dry_run
        )

    def sell(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        price = self.security(security_id)["quote"]["amount"]
        q, _ = _quant(quantity, value, price)
        return self.place_order(
            account_id, security_id, quantity, "sell_quantity", dry_run=dry_run
        )

    def activity(self):
        self.refresh()
        return self._get("account/activities")

    def me(self):
        self.refresh()
        return self._get("me")

    def forex(self):
        self.refresh()
        return self._get("forex")

    def security(self, security_id):
        self.refresh()
        return self._get(f"securities/{security_id}")


class Crypto:
    def __init__(self, email):
        self.API = WealthsimpleApi(email)
        res = self.API.accounts()[0]
        self.ID = res["id"]
        self.CUSTODIAN = res["custodian_account_number"]

    def buy(self, security_id, quantity=None, value=None, dry_run=False):
        return self.API.buy(self.ID, security_id, quantity, value, dry_run)

    def sell(self, security_id, quantity=None, value=None, dry_run=False):
        return self.API.sell(self.ID, security_id, quantity, value, dry_run)

    def quote(self, sec_id):
        security = self.API.security(sec_id)
        return {
            "id": security["id"],
            "symbol": security["stock"]["symbol"],
            "name": security["stock"]["symbol"],
            "quote": {k: security["quote"][k] for k in ["amount", "ask", "bid"]},
            "date": security["quote"]["quote_date"],
        }

    def quotes(self, security_ids):
        return [self.quote(s) for s in security_ids]

    def summary(self):
        res = self.API.accounts()["results"][0]

        return {
            "balance": res["current_balance"]["amount"],
            "available": res["available_to_withdraw"]["amount"],
            "withdrawn": res["withdrawn_earnings"]["amount"],
            "positions": {
                k: _pos(self, k, v) for k, v in res["position_quantities"].items()
            },
        }

    def run(self, robot, frequency=60, dry_run=True):
        print(f"Starting robot {robot}...")
        print(f"  run every {frequency} seconds")
        if dry_run:
            print("  NO ACTUAL TRANSACTIONS")
        try:
            while True:
                print(".", end="")
                robot(self, dry_run=dry_run)
                time.sleep(frequency)
        except Exception as e:
            print(e)
            return self


class Dummy:
    def __init__(self, history_file, starting_balance):
        self.__history = list(util.json_lines(history_file))
        self.__history.reverse()
        self.__state = self.__history.pop()
        self.__summary = {
            "balance": starting_balance,
            "available": starting_balance,
            "withdrawn": 0,
            "positions": {BTC: 0, ETH: 0},
        }

    def buy(self, security_id, quantity=None, value=None, dry_run=False):
        price = self.quote(security_id)["quote"]["amount"]
        q, v = _quant(quantity, value, price)
        self.__summary["balance"] -= v
        self.__summary["available"] -= v
        if security_id not in self.__summary["positions"]:
            self.__summary["positions"][security_id] = 0
        real_q, real_v = _quant(quantity, _taxed(v, 0.0148), price)
        print(f"\nBUYING {q}({v})[{real_q}{real_v}] at ${price}")
        self.__summary["positions"][security_id] += real_q
        return True

    def sell(self, security_id, quantity=None, value=None, dry_run=False):
        price = self.quote(security_id)["quote"]["amount"]
        q, v = _quant(quantity, value, price)
        print(f"\nSELLING {q}({v})[{_taxed(v, 0.0152)}] at ${price}")
        self.__summary["positions"][security_id] -= q
        self.__summary["balance"] += _taxed(v, 0.0152)
        self.__summary["available"] += _taxed(v, 0.0152)
        return True

    def quote(self, security_id):
        if security_id == BTC:
            return self.__state[0]
        elif security_id == ETH:
            return self.__state[1]

    def quotes(self, security_ids):
        return self.__state

    def __tick(self):
        self.__state = self.__history.pop()

    def summary(self):
        s = self.__summary.copy()
        s["positions"] = {k: _pos(self, k, v) for k, v in s["positions"].items()}
        return s

    def liquidate(self):
        print("LIQUIDATING")
        for k, sec in self.summary()["positions"].items():
            if sec["quantity"]:
                self.sell(k, quantity=sec["quantity"])
        return self

    def run(self, robot):
        print(f"Starting Dummy robot {robot}...")
        while self.__history:
            print(".", end="")
            robot(self)
            self.__tick()
        print("")
        return self

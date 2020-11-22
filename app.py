import json
import os
import time

import api
import util
from util import BTC, ETH


class Crypto:
    def __init__(self, email):
        self.API = api.WealthsimpleApi(email)
        res = self.API.accounts()["results"][0]
        self.ID = res["id"]
        self.CUSTODIAN = res["custodian_account_number"]

    def buy(self, security_id, quantity=None, value=None, dry_run=False):
        return self.API.buy(self.ID, security_id, quantity, value, dry_run)

    def sell(self, security_id, quantity=None, value=None, dry_run=False):
        return self.API.buy(self.ID, security_id, quantity, value, dry_run)

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
                k: (self.quote(k)["quote"]["amount"] * v)
                for k, v in res["position_quantities"].items()
            },
        }


class Dummy:
    def __init__(self, history_file):
        pass

    def buy(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        pass

    def sell(self, account_id, security_id, quantity=None, value=None, dry_run=False):
        pass

    def quote(self, security_id):
        pass

    def quotes(self, security_ids):
        pass

    def summary(self):
        pass


def _scratch():
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


def auto_balance_btc(
    api, keep_at, frequency, buy_threshold=0.1, sell_threshold=0.1, dry_run=False
):
    sell_above = keep_at + (keep_at * sell_threshold)
    buy_below = keep_at - (keep_at * buy_threshold)
    print("Starting AUTO")
    print(f"  run every {frequency} seconds")
    print(f"  keep in <{buy_below}>{keep_at}<{sell_above}>...")
    if dry_run:
        print("  NO ACTUAL TRANSACTIONS")
    while True:
        summary = api.summary()
        btc_val = summary["positions"][BTC]

        if btc_val > sell_above:
            val = btc_val - keep_at
            print("SELLING EXCESS")
            print(f"  BTC worth {btc_val}; exceeds threshold of ${sell_above}")
            print(f"  selling {val}")
            api.sell(summary["id"], BTC, value=val, dry_run=dry_run)
        elif buy_below > btc_val:
            if 0 >= summary["balance"]:
                print("CANT BUY")
                print(f"  BTC worth {btc_val}, but don't have enough balance to top up")
            else:
                # TODO - the min of balance and available funds
                want = keep_at - btc_val
                actual = min(want, summary["balance"], summary["available"])
                print("BUYING UP")
                print(f"  BTC worth {btc_val}, want to buy ${want}, buying ${actual}")
                api.buy(summary["id"], BTC, value=actual, dry_run=dry_run)
        time.sleep(frequency)


def monitor(api, path="~/.pytrade/history.json"):
    p = os.path.expanduser(path)
    while True:
        with open(p, "a") as f:
            f.write(json.dumps(api.quotes([BTC, ETH])))
            f.write("\n")
        time.sleep(60)

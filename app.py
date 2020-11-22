import json
import os
import time

import util
from util import BTC, ETH


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


def mk_hold_bot(buy, sell):
    def _bot(summary, dry_run=True):
        if summary["available"] > 0:
            buy(BTC, value=summary["available"])

    return _bot


def mk_auto_balance_btc(buy, sell, keep_at, buy_threshold=0.1, sell_threshold=0.1):
    sell_above = keep_at + (keep_at * sell_threshold)
    buy_below = keep_at - (keep_at * buy_threshold)
    print(f"  keep in <{buy_below}>{keep_at}<{sell_above}>...")

    def _bot(summary, dry_run=True):
        btc_val = summary["positions"][BTC]

        if btc_val > sell_above:
            val = btc_val - keep_at
            print("SELLING EXCESS")
            print(f"  BTC worth {btc_val}; exceeds threshold of ${sell_above}")
            print(f"  selling {val}")
            sell(BTC, value=val, dry_run=dry_run)
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
                buy(BTC, value=actual, dry_run=dry_run)

    return _bot


def dummy_robot(dummy, robot):
    for i in range(500):
        robot(dummy.summary())
        dummy.tick()
    return dummy.summary()


def run_robot(api, robot, frequency, dry_run=True):
    print(f"Starting robot {robot}...")
    print(f"  run every {frequency} seconds")
    if dry_run:
        print("  NO ACTUAL TRANSACTIONS")
    robot(api.summary(), dry_run=dry_run)
    time.sleep(frequency)


def monitor(api, path="~/.pytrade/history.json"):
    p = os.path.expanduser(path)
    while True:
        with open(p, "a") as f:
            f.write(json.dumps(api.quotes([BTC, ETH])))
            f.write("\n")
        time.sleep(60)


# def auto_balance_btc(
#     api, keep_at, frequency, buy_threshold=0.1, sell_threshold=0.1, dry_run=False
# ):
#     sell_above = keep_at + (keep_at * sell_threshold)
#     buy_below = keep_at - (keep_at * buy_threshold)
#     print("Starting AUTO")
#     print(f"  run every {frequency} seconds")
#     print(f"  keep in <{buy_below}>{keep_at}<{sell_above}>...")
#     if dry_run:
#         print("  NO ACTUAL TRANSACTIONS")
#     while True:
#         summary = api.summary()
#         btc_val = summary["positions"][BTC]

#         if btc_val > sell_above:
#             val = btc_val - keep_at
#             print("SELLING EXCESS")
#             print(f"  BTC worth {btc_val}; exceeds threshold of ${sell_above}")
#             print(f"  selling {val}")
#             api.sell(summary["id"], BTC, value=val, dry_run=dry_run)
#         elif buy_below > btc_val:
#             if 0 >= summary["balance"]:
#                 print("CANT BUY")
#                 print(f"  BTC worth {btc_val}, but don't have enough balance to top up")
#             else:
#                 # TODO - the min of balance and available funds
#                 want = keep_at - btc_val
#                 actual = min(want, summary["balance"], summary["available"])
#                 print("BUYING UP")
#                 print(f"  BTC worth {btc_val}, want to buy ${want}, buying ${actual}")
#                 api.buy(summary["id"], BTC, value=actual, dry_run=dry_run)
#         time.sleep(frequency)

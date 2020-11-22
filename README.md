# PyTrade

## TODO

- Fix rounding bugs in a couple of places in the dummy API
- Pull the dry_run options out entirely and make it a global flag

## Notes

- The Activity feed is bullshit. If you check after the fact, it makes it look like all transactions insta-complete. The realistic delay is probably more like a couple hours. But lets test this :D
	- Huh. It looks like, during the day, it _does_ insta-complete the order. Weird.
- Orders are subject to a 1.48% transaction fee for buying, and 1.52% for selling. For buys, this means
	- when you buy `X`, you actually buy `round(X - (X * 0.0148), 2)`, and the remainder is forfeited as a transaction fee.
	- when you sell `X`, you only get `round(X - (X * 0.0152), 2)`

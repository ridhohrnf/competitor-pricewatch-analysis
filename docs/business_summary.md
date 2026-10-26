# Competitor prices for Unilever products: summary

*For the pricing team. October 2026.*

## What we built

A daily process that reads Unilever product prices from competitor stores, cleans them, matches
the same product across stores, and suggests our own price. Results are in a dashboard and in an
API.

## What we can say today

**1. Only Tokopedia is real data, and only for two days.** We collected Unilever products from
Tokopedia's official store on 19 October (346 products) and again on 26 October (360 products).
After removing bundles and free-gift items, 341 and 356 listings were usable. Blibli and Klik
Indomaret block automated access, so for them, and for price history before 19 October, we used a
realistic **synthetic** dataset. Findings marked *(sample)* show what the reports will tell us once
real data flows. They are not market facts yet.

**2. On Tokopedia, almost every product shows a "discount".** Every usable listing on both days had
a crossed-out price, with an average cut of about 38% (laundry, cleaning, dishwashing). When
everything is "on sale", the crossed-out price is not a useful signal. Compare **selling prices**
instead.

**3. Real prices moved down in the week between our two crawls.** Of the 326 listings we saw on
both days, 67 (21%) changed price: 58 went down and 9 went up, and the average change was a 3.3% drop.
This is only one week, so it is a first look, not a trend.

**4. Which store is cheapest (sample).** Blibli was cheapest on 68% of product-days, about 4% below
the average across stores. Klik Indomaret was about 4% above. If this holds on real data, Blibli is
the price to watch.

**5. The same product can differ by more than 20% between stores (sample).** For example a Molto
800 ml refill ranged from Rp15,600 to Rp19,100. Large gaps are where our own price matters most.

**6. Stores change prices on different rhythms (sample).** Klik Indomaret moves prices on Mondays
(up) and Fridays (down), like a weekly promotion. The others change prices in the middle of the
week and at weekends. Price checks should run daily, not weekly.

**7. Suggested prices.** For each product we suggest the competitor median minus 3%, never below
an assumed cost plus a 10% margin. We now have suggestions for 373 products. Only 28 of them can be
compared across two or more stores. The other 345 are flagged as low confidence, because there is
nothing to compare them with.

## Caveats

- Synthetic data drives every cross-store number. Real data from Blibli and Klik Indomaret needs a
  permitted source, such as a partnership or licensed data.
- Prices depend on delivery location. We used each site's default.
- Our cost is an assumption (80% of the lowest recent price), not a real purchase cost.
- Product matching is rule-based, so a few products may be split or merged wrongly.

## Next steps

1. Run the real crawl every day for a few weeks, to see real price changes and day-of-week patterns.
2. Agree a permitted data source for the other two stores.
3. Replace the assumed cost with real costs before using the suggested prices.

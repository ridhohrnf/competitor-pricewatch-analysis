# Analysis results

These are the answers to the four business questions, from the four SQL files in
`dbt/analyses/`, run on 2026-10-26 against the gold tables.

A note on the data: **only Tokopedia is real**, and only for two days (19 and 26 October 2026,
341 and 356 valid listings). Blibli, Klik Indomaret and the price history before 19 October are
**made-up sample data**. Rows marked *sample* show that the method works. They are not facts about
the market.

## Q1. Which platform is cheapest on average for comparable products?

Price index = a store's price divided by the average price of the same product, on the same day,
across all stores, times 100. Below 100 means cheaper than average. Only products sold in two or
more stores on that day are counted.

| Data | Platform | Product-days | Products | Avg index | Median index | % of days cheapest |
|---|---|---|---|---|---|---|
| sample | Blibli | 1,456 | 26 | **95.9** | 97.8 | **68.0** |
| sample | Tokopedia | 1,568 | 28 | 100.7 | 100.5 | 31.4 |
| sample | Klik Indomaret | 1,344 | 24 | 103.7 | 102.9 | 16.2 |

Blibli is cheapest, about 4% below the average. Klik Indomaret is the most expensive. This matches
the price levels I built into the sample generator (Blibli 2% cheaper, Klik Indomaret 3% more expensive), so the index
is computed correctly. It is not a statement about the real stores.

## Q2. How deep and how often are discounts, by category and platform?

**Real data (Tokopedia, both days together, 697 product-days):**

| Category | Product-days | % discounted | Avg depth | Median depth | Max |
|---|---|---|---|---|---|
| Dishwashing | 127 | 100.0 | 38.0% | 34.5% | 72.8% |
| Household Cleaning | 180 | 100.0 | 39.0% | 38.1% | 60.4% |
| Laundry | 390 | 100.0 | 37.7% | 36.0% | 66.9% |

Every real listing shows a crossed-out price, and the average cut is about 38%. When everything
is "on sale", the crossed-out price says little. The selling price is the better signal.

**Sample data, all categories**, share of days with a discount:

| Platform | Typical % of days discounted | Typical depth |
|---|---|---|
| Blibli | 24 to 38% | 17 to 23% |
| Klik Indomaret | 13 to 27% | 9 to 13% |
| Tokopedia | 10 to 20% | 15 to 19% |

The full table has 24 rows: see `dbt/analyses/q2_discount_depth_frequency.sql`. The dashboard chart
"Average discount per day, sample data" shows the same discounts as a daily line, from 17 August
to 11 October 2026.

## Q3. Which products differ most in price between platforms?

Latest day with two or more stores (sample, 2026-10-11):

| Product | Stores | Lowest | Highest | Cheapest | Most expensive | Gap |
|---|---|---|---|---|---|---|
| Molto Pewangi & Pelembut Pakaian Blue Refill 800ml | 3 | 15,600 | 19,100 | Blibli | Klik Indomaret | 22.4% |
| Rinso Matic Deterjen Cair Mesin Cuci Bukaan Depan 800ml | 3 | 28,600 | 34,800 | Blibli | Tokopedia | 21.7% |
| Clear Men Shampoo Anti Ketombe Cool Sport Menthol 300ml | 3 | 43,100 | 50,900 | Klik Indomaret | Blibli | 18.1% |
| Sunlight Sabun Cuci Piring Lime Botol 400ml | 3 | 8,600 | 10,100 | Klik Indomaret | Tokopedia | 17.4% |
| Lifebuoy Sabun Mandi Batang Total 10 110g isi 4 | 3 | 15,500 | 18,000 | Blibli | Tokopedia | 16.1% |

Gap = (highest minus lowest) / lowest. 15 products were sold in two or more stores on that day.
Real Tokopedia products cannot be compared across stores, because there is no real data from the
other stores.

## Q4. How often do prices change, and is there a pattern by day of the week?

**Real data (Tokopedia).** I have two real days, one week apart (both Mondays). Of the 326
listings seen on both days, **67 (21%) changed price**: 58 went down and 9 went up. The average
change was **a 3.3% drop**. So in that week Tokopedia mostly lowered prices. This is one week only, so I
would not call it a trend yet. Because both days are Mondays, real data cannot show a day-of-week
pattern either. Over the observed week, a listing changed price 0.18 times on average.

**Sample data.** Share of listing-days with a price change:

| Platform | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Blibli | 17.0 | 15.9 | **29.8** | 26.4 | 16.8 | **29.3** | 28.4 |
| Klik Indomaret | **39.7** | 3.0 | 5.0 | 5.5 | **39.0** | 4.0 | 5.0 |
| Tokopedia | 8.9 | 11.6 | 22.0 | **22.4** | 11.2 | 18.1 | 22.0 |

Klik Indomaret changes prices almost only on Monday (mostly up: 66 of 69) and Friday (mostly down:
74 of 78), like a weekly promotion cycle. Blibli and Tokopedia change prices in the middle of the
week and at weekends. Changes per listing per week: Blibli 1.64, Tokopedia 1.17, Klik Indomaret 0.98.

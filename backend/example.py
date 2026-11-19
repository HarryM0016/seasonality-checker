"""Run the recipe checker from the command line, the same way the API will.

    python example.py URL --postcode 3000
    python example.py URL --postcode 3000 --recheck 4 6     # send lines 4 and 6 to Claude (costs tokens)
"""

import argparse

from seasonality_checker.recipes.recipe_checker import check_recipe, recheck_lines

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="https://www.recipetineats.com/pavlova-bombs/")
    parser.add_argument("--postcode", default="3000")
    parser.add_argument("--month", type=int, help="1-12 (default: this month)")
    parser.add_argument("--recheck", type=int, nargs="+", metavar="LINE", help="line numbers to send to Claude")
    args = parser.parse_args()

    result = check_recipe(args.url, args.postcode, args.month)
    if args.recheck:
        result = recheck_lines(result.recipe_id, args.recheck, args.postcode, args.month)

    print(f"Recipe {result.recipe_id}: {result.url}\n")
    for line in result.lines:
        produce = ", ".join(line.produce) or "-"
        print(f"{line.index:>3}  {line.method:<6}  {produce:<25}  {line.text}")

    print(f"\nIn {MONTHS[result.month - 1]}:")
    for item in result.produce:
        status = {True: "in season", False: "out of season", None: "no data"}[item.in_season]
        print(f"  {item.name:<20} {status}")

    print("\nScore by month:")
    print("  " + "  ".join(f"{m} {s}" for m, s in zip(MONTHS, result.monthly_scores)))

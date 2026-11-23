# seasonality-checker

Repo for the seasonality checker app that takes a recipe and returns if the ingredients used are in season.

### Setup

```
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e . --group dev
```

`.env` needs `DATABASE_URL` (Neon Postgres) and `ANTHROPIC_API_KEY`.

```
pytest                                      # free tests
pytest -m llm                               # Claude API tests (costs tokens)
python scripts/check_recipe.py URL --postcode 3000
```

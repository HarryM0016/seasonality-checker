import recipe_scrapers
import requests


def scrape_ingredients(url: str) -> list[str]:
    """The raw ingredient lines from a recipe page, or [] if the site isn't supported."""
    response = requests.get(url)
    response.raise_for_status()
    html = response.text
    
    try:
        scraper = recipe_scrapers.scrape_html(html, org_url=url)
    except recipe_scrapers._exceptions.WebsiteNotImplementedError:
        ingredients = []
        print("Website not supported")
        return ingredients
    
    ingredients = scraper.ingredients()
    
    return ingredients
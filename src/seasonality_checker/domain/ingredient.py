class Ingredient:
    def __init__(self, name: str, seasonal_range: tuple):
        self.name = name
        self.season_start = seasonal_range[0]
        self.season_end = seasonal_range[1]

    def is_in_season(self, month: int) -> bool:
        if self.season_start <= self.season_end:
            return self.season_start <= month <= self.season_end
        return month >= self.season_start or month <= self.season_end

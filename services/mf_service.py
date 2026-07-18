"""MF service — NAV fetch placeholder, units calc."""


class MFService:
    @staticmethod
    def calculate_units(amount, nav):
        return round(amount / nav, 4) if nav > 0 else 0

    @staticmethod
    def simple_return(invested, current_value):
        if invested == 0:
            return 0
        return round((current_value - invested) / invested * 100, 2)

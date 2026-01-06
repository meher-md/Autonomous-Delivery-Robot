import datetime

def test_date_transitions():
    # Test cases: (Year, Month, Day) -> expected next day's folder parts
    test_dates = [
        (2026, 1, 31), # End of January (31 days) -> Should be February 1
        (2026, 2, 28), # End of Feb (non-leap) -> March 1
        (2028, 2, 29), # Leap year check -> March 1
        (2026, 4, 30), # April (30 days) -> May 1
    ]

    print(f"{'Simulated Date':<20} | {'Resulting Folder Path':<40}")
    print("-" * 65)

    for y, m, d in test_dates:
        # Construct a date object
        simulated_now = datetime.datetime(y, m, d, 23, 59, 59)
        
        # Folder logic (Same as in qr_scanner.py)
        year_str = simulated_now.strftime("%Y")
        month_str = simulated_now.strftime("%B")
        day_str = simulated_now.strftime("%d")
        
        print(f"{simulated_now.strftime('%Y-%m-%d'):<20} | .../{year_str}/{month_str}/{day_str}/...")
        
        # Add 1 second to cross midnight
        next_day = simulated_now + datetime.timedelta(seconds=1)
        
        n_year = next_day.strftime("%Y")
        n_month = next_day.strftime("%B")
        n_day = next_day.strftime("%d")
        
        print(f"{next_day.strftime('%Y-%m-%d'):<20} | .../{n_year}/{n_month}/{n_day}/...  <-- NEXT DAY")
        print("-" * 65)

if __name__ == "__main__":
    test_date_transitions()

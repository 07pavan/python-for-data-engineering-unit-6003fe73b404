
import os
import sqlite3
import sys
from datetime import date

API_URL = "https://api.example.com/solar?date=today"

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "solar.db"
)


def fetch_today(url):
    """Pretend to call an API and return today's solar output."""

    print(f"Simulating API request: {url}")

    # Fake API response
    data = {
        "date": str(date.today()),
        "energy_kwh": 25.6
    }

    return data["date"], float(data["energy_kwh"])


def create_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_output (
            date TEXT PRIMARY KEY,
            energy_kwh REAL
        )
    """)


def save_output(db_path, date_value, energy_kwh):
    """Insert a record or update it if the date already exists."""

    conn = sqlite3.connect(db_path)

    try:
        create_table(conn)

        conn.execute("""
            INSERT INTO daily_output (date, energy_kwh)
            VALUES (?, ?)
            ON CONFLICT(date)
            DO UPDATE SET energy_kwh = excluded.energy_kwh
        """, (date_value, energy_kwh))

        conn.commit()

    finally:
        conn.close()


def get_all_rows(db_path):
    conn = sqlite3.connect(db_path)

    try:
        create_table(conn)

        cur = conn.execute("""
            SELECT date, energy_kwh
            FROM daily_output
            ORDER BY date
        """)

        return cur.fetchall()

    finally:
        conn.close()


def format_row(date_value, energy_kwh):
    return f"{date_value}: {energy_kwh} kWh"


def main(argv):
    url = argv[1] if len(argv) > 1 else API_URL

    try:
        date_value, energy_kwh = fetch_today(url)
        save_output(DB_PATH, date_value, energy_kwh)

        for row_date, row_energy in get_all_rows(DB_PATH):
            print(format_row(row_date, row_energy))

        return 0

    except (sqlite3.Error, ValueError, KeyError, TypeError) as error:
        print(f"Error processing solar data: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

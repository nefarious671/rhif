import sqlite3
import pandas as pd


def extract_sample_rows(db_path, output_csv="output.csv", limit=50):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all real tables (excluding indexes/views/etc.)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    table_names = [row[0] for row in cursor.fetchall()]

    all_data = []

    for table in table_names:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT {limit}", conn)
            df['table_name'] = table  # Add table name column
            all_data.append(df)
        except Exception as e:
            print(f"❌ Skipping table '{table}': {e}")

    # Combine and save
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.to_csv(output_csv, index=False)
        print(f"✅ Combined data saved to {output_csv}")
    else:
        print("⚠️ No data extracted.")

    conn.close()

extract_sample_rows("E:\\Python\\rhif\\rhif-clipon\\hub\\rhif.sqlite", "E:\\temp\\output.csv")

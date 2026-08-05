import os
import streamlit as st
import pandas as pd
import psycopg2
from databricks.sdk import WorkspaceClient

# ---------------------------------------------------------------------------
# Config — set these via app.yaml env vars (see companion app.yaml below),
# or edit the defaults here for local testing.
# ---------------------------------------------------------------------------
PGHOST = os.getenv("PGHOST", "ep-twilight-queen-d8yphdwj.database.us-east-2.cloud.databricks.com")
PGDATABASE = os.getenv("PGDATABASE", "databricks_postgres")
PGUSER = os.getenv("PGUSER", "diegomanssur@gmail.com")
PGPORT = os.getenv("PGPORT", "5432")
PGAPPNAME = os.getenv("PGAPPNAME", "lakebase-streamlit-app")

TABLE_NAME = st.sidebar.text_input("Table to query", "your_schema.your_table")
ROW_LIMIT = st.sidebar.number_input("Row limit", min_value=10, max_value=10000, value=100, step=10)


@st.cache_resource
def get_workspace_client() -> WorkspaceClient:
    # On a Databricks App this picks up the app's identity automatically.
    return WorkspaceClient()


def get_pg_password() -> str:
    """Lakebase auth uses a short-lived OAuth token as the Postgres password.
    Tokens expire (~1hr), so generate a fresh one for each new connection
    rather than caching it long-term."""
    w = get_workspace_client()
    cred = w.database.generate_database_credential(
        request_id=None,
        instance_names=[PGHOST.split(".")[0]],  # Lakebase instance name
    )
    return cred.token


def get_connection():
    return psycopg2.connect(
        host=PGHOST,
        dbname=PGDATABASE,
        user=PGUSER,
        password=get_pg_password(),
        port=PGPORT,
        sslmode="require",
        application_name=PGAPPNAME,
    )


@st.cache_data(ttl=60)
def load_data(table: str, limit: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = f"SELECT * FROM {table} LIMIT %s"
        return pd.read_sql(query, conn, params=(limit,))
    finally:
        conn.close()


def main():
    st.set_page_config(page_title="Lakebase Viewer", layout="wide")
    st.title("Lakebase Data Viewer")

    if not TABLE_NAME or "." not in TABLE_NAME:
        st.info("Enter a schema-qualified table name in the sidebar (e.g. `public.customers`).")
        return

    try:
        with st.spinner(f"Querying {TABLE_NAME}..."):
            df = load_data(TABLE_NAME, ROW_LIMIT)
        st.success(f"Loaded {len(df):,} rows")
        st.dataframe(df, use_container_width=True)
    except Exception as e:
        st.error(f"Failed to load data: {e}")


if __name__ == "__main__":
    main()

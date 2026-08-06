from databricks.sdk import WorkspaceClient
w = WorkspaceClient()

w.secrets.put_secret(
    scope="database",
    key="lakebase-ticket-support-password",
    string_value="postgresql://diegomanssur%40gmail.com@ep-twilight-queen-d8yphdwj.database.us-east-2.cloud.databricks.com/databricks_postgres?sslmode=require"
)
print("✓ Secret stored!")
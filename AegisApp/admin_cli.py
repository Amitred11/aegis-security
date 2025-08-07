# AegisApp/admin_cli.py
import typer
import httpx
import os

app = typer.Typer()
ADMIN_API_KEY = os.getenv("AEGIS_ADMIN_KEY")
GATEWAY_URL = "http://localhost:8000"

@app.command()
def status():
    """Checks the /health endpoint of the gateway."""
    print("Pinging gateway health...")
    try:
        response = httpx.get(f"{GATEWAY_URL}/health")
        response.raise_for_status()
        print("✅ Gateway is healthy.")
        print(response.json())
    except Exception as e:
        print(f"❌ Gateway is unhealthy or unreachable: {e}")

@app.command()
def upload_spec(filepath: str):
    """Uploads an OpenAPI spec file to the gateway."""
    if not ADMIN_API_KEY:
        print("❌ Error: AEGIS_ADMIN_KEY environment variable not set.")
        raise typer.Exit(code=1)
        
    print(f"Uploading spec from {filepath}...")
    try:
        with open(filepath, "r") as f:
            spec_content = f.read()
        
        headers = {
            "x-api-key": ADMIN_API_KEY,
            "Content-Type": "text/plain"
        }
        response = httpx.post(f"{GATEWAY_URL}/admin/spec", headers=headers, content=spec_content)
        response.raise_for_status()
        print("✅ Spec uploaded successfully!")
        print(response.json())
    except Exception as e:
        print(f"❌ Failed to upload spec: {e}")

if __name__ == "__main__":
    app()
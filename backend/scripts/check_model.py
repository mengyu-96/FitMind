"""Check configured model IDs without printing credentials or user data."""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings  # noqa: E402


def main():
    settings = Settings()
    try:
        response = httpx.get(
            settings.model_base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {settings.model_api_key}"}, timeout=25,
        )
        print(json.dumps({"status": response.status_code,
                          "configured_model": settings.model_name}, ensure_ascii=False))
        if response.is_success:
            models = [item["id"] for item in response.json().get("data", [])]
            print(json.dumps({"available_models": models,
                              "exact_match": settings.model_name in models}, ensure_ascii=False))
        else:
            print("Provider rejected model discovery; response body omitted.")
            raise SystemExit(1)
    except httpx.RequestError as exc:
        print(f"Connection failed ({type(exc).__name__}); credentials omitted.")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()

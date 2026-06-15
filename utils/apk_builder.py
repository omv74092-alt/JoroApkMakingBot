import requests
import time
import json
from config import GITHUB_TOKEN, GITHUB_REPO

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

def trigger_build(app_name, package_name, app_url="", features=None, icon_url=""):
    """Trigger GitHub Actions workflow for APK build"""
    if features is None:
        features = {}

    payload = {
        "ref": "main",
        "inputs": {
            "app_name":     app_name,
            "package_name": package_name,
            "app_url":      app_url,
            "icon_url":     icon_url,
            "shizuku":      str(features.get("shizuku", False)).lower(),
            "file_manager": str(features.get("file_manager", False)).lower(),
            "login_screen": str(features.get("login_screen", False)).lower(),
            "dark_theme":   str(features.get("dark_theme", True)).lower(),
            "key_system":   str(features.get("key_system", False)).lower(),
        }
    }

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/build.yml/dispatches"
    r = requests.post(url, headers=HEADERS, json=payload)

    if r.status_code == 204:
        time.sleep(3)
        run_id = get_latest_run_id()
        return {"success": True, "run_id": run_id}
    else:
        return {"success": False, "error": r.text}

def get_latest_run_id():
    """Get most recent workflow run ID"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=1"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        runs = r.json().get("workflow_runs", [])
        return runs[0]["id"] if runs else None
    return None

def check_build_status(run_id):
    """Check build status — returns: pending/running/success/failed"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code != 200:
        return {"status": "error", "apk_url": None}

    data = r.json()
    conclusion = data.get("conclusion")
    status     = data.get("status")

    if status in ("queued", "waiting"):
        return {"status": "pending", "apk_url": None}
    elif status == "in_progress":
        return {"status": "running", "apk_url": None}
    elif conclusion == "success":
        apk_url = get_artifact_url(run_id)
        return {"status": "success", "apk_url": apk_url}
    else:
        return {"status": "failed", "apk_url": None}

def get_artifact_url(run_id):
    """Get APK download URL from artifacts"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/artifacts"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        artifacts = r.json().get("artifacts", [])
        for a in artifacts:
            if "apk" in a["name"].lower():
                return a["archive_download_url"]
    return None

def download_apk(artifact_url):
    """Download APK zip from GitHub artifacts"""
    r = requests.get(artifact_url, headers=HEADERS, stream=True)
    if r.status_code == 200:
        return r.content  # zip bytes containing APK
    return None

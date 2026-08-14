"""Push a local file to Yury197812/portable-os via GitHub contents API (with retries)."""
import base64, os, subprocess, sys, time
import requests

REPO = "Yury197812/portable-os"
BRANCH = "master"


def gh_token():
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, env=env)
    return out.stdout.strip()


def push(repo_path, local_file, message="MIMO update"):
    tok = gh_token()
    data = open(local_file, "rb").read()
    b64 = base64.b64encode(data).decode()
    headers = {"Authorization": f"token {tok}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPO}/contents/{repo_path}"
    body = {"message": message, "content": b64, "branch": BRANCH}
    for attempt in range(5):
        try:
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 200:
                body["sha"] = r.json()["sha"]
            rr = requests.put(url, headers=headers, json=body, timeout=90)
            if rr.ok:
                print("OK", rr.json()["commit"]["sha"][:7], rr.json()["content"]["html_url"])
                return 0
            print("FAIL", rr.status_code, rr.text[:300])
            return 1
        except Exception as e:
            print(f"retry {attempt + 1}/5 ({type(e).__name__})")
            time.sleep(4)
    print("GAVE UP")
    return 1


if __name__ == "__main__":
    sys.exit(push(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "MIMO update"))

"""GitHub REST access for the Code page, and keyring storage for the access token.

Blocking calls meant for a worker thread. The token never goes into SQLite, settings,
backups, sync or error messages; it lives in the OS credential store, or only in memory
for the session when no secure store exists.
"""

from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.github.com"
KEYRING_SERVICE = "DayFrame.github"
TOKEN_PAGE = "https://github.com/settings/tokens/new?scopes=repo,workflow,read:org&description=DayFrame"
MAX_RESPONSE = 8 * 1024 * 1024
MERGE_METHODS = ("merge", "squash", "rebase")


class GitHubError(ValueError):
    pass


def check_api_url(url):
    parsed = urllib.parse.urlsplit(url or API_URL)
    local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise GitHubError("The GitHub API address must use HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise GitHubError("Enter a valid GitHub API address.")
    return (url or API_URL).rstrip("/")


class GitHub:
    def __init__(self, token, api_url=API_URL, timeout=20):
        if not token:
            raise GitHubError("Add a GitHub access token in Settings > Sync.")
        self.token = token
        self.api = check_api_url(api_url)
        self.timeout = timeout

    def request(self, method, path, body=None, query=None):
        """Call the REST API; returns (data, headers). Errors never include the token."""
        url = self.api + path + ("?" + urllib.parse.urlencode(query) if query else "")
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "DayFrame")
        request.add_header("Authorization", "Bearer " + self.token)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
                headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            raise GitHubError(self._describe(exc)) from None
        except (urllib.error.URLError, OSError) as exc:
            raise GitHubError("GitHub could not be reached: " + str(getattr(exc, "reason", exc))) from None
        if len(raw) > MAX_RESPONSE:
            raise GitHubError("The GitHub response is too large.")
        return (json.loads(raw) if raw else None), headers

    def _describe(self, exc):
        try:
            message = json.loads(exc.read(65536) or b"{}").get("message", "")
        except ValueError:
            message = ""
        if exc.code == 401:
            return "GitHub rejected the access token. Check it in Settings > Sync."
        if exc.code == 403 and "rate limit" in message.lower():
            return "GitHub's rate limit was reached. Try again later."
        if exc.code in (403, 404):
            return (message or "Not found") + ". Check the repository name and the token's access."
        return "GitHub: " + (message or "request failed (" + str(exc.code) + ")")

    def get(self, path, **query):
        return self.request("GET", path, query=query or None)[0]

    # Account and repository ---------------------------------------------------------------

    def viewer(self):
        data, headers = self.request("GET", "/user")
        scopes = next((v for k, v in headers.items() if k.lower() == "x-oauth-scopes"), None)
        return {"login": data["login"], "name": data.get("name") or "", "scopes": scopes}

    def repository(self, full_name):
        return self.get("/repos/" + full_name)

    def overview(self, full_name, ref=""):
        """Repository, latest release, checks on a ref, open pull requests and issues."""
        repo = self.repository(full_name)
        ref = ref or repo["default_branch"]
        return {
            "repo": {
                key: repo.get(key)
                for key in (
                    "full_name",
                    "html_url",
                    "description",
                    "default_branch",
                    "private",
                    "open_issues_count",
                    "pushed_at",
                )
            },
            "ref": ref,
            "release": self.latest_release(full_name),
            "checks": self.checks(full_name, ref),
            "pulls": self.pulls(full_name),
            "issues": self.issues(full_name),
        }

    def latest_release(self, full_name):
        try:
            release = self.get("/repos/" + full_name + "/releases/latest")
        except GitHubError:
            return None
        return {
            "tag": release.get("tag_name", ""),
            "name": release.get("name") or "",
            "url": release.get("html_url"),
        }

    def checks(self, full_name, ref):
        """Combined commit status and check runs for a ref, summarized."""
        ref = urllib.parse.quote(ref, safe="")
        try:
            status = self.get("/repos/" + full_name + "/commits/" + ref + "/status")
            runs = self.get("/repos/" + full_name + "/commits/" + ref + "/check-runs", per_page=50)
        except GitHubError:
            return None
        results = [s["state"] for s in status.get("statuses", [])]
        for run in runs.get("check_runs", []):
            results.append(run.get("conclusion") or run.get("status"))
        failed = sum(r in ("failure", "error", "cancelled", "timed_out", "action_required") for r in results)
        pending = sum(r in ("pending", "queued", "in_progress", None) for r in results)
        state = "none" if not results else "failing" if failed else "pending" if pending else "passing"
        return {"state": state, "total": len(results), "failed": failed, "pending": pending}

    def pulls(self, full_name, state="open"):
        items = self.get("/repos/" + full_name + "/pulls", state=state, per_page=50)
        return [
            {
                "number": p["number"],
                "title": p["title"],
                "url": p["html_url"],
                "author": (p.get("user") or {}).get("login", ""),
                "head": p["head"]["ref"],
                "base": p["base"]["ref"],
                "draft": bool(p.get("draft")),
            }
            for p in items
        ]

    def issues(self, full_name, state="open"):
        items = self.get("/repos/" + full_name + "/issues", state=state, per_page=50)
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "url": i["html_url"],
                "author": (i.get("user") or {}).get("login", ""),
                "labels": [label["name"] for label in i.get("labels", [])],
            }
            for i in items
            if "pull_request" not in i
        ]

    # Changes ------------------------------------------------------------------------------

    def create_pull(self, full_name, title, head, base, body="", draft=False):
        data, _ = self.request(
            "POST",
            "/repos/" + full_name + "/pulls",
            {"title": title, "head": head, "base": base, "body": body, "draft": draft},
        )
        return {"number": data["number"], "url": data["html_url"]}

    def create_issue(self, full_name, title, body=""):
        data, _ = self.request("POST", "/repos/" + full_name + "/issues", {"title": title, "body": body})
        return {"number": data["number"], "url": data["html_url"]}

    def merge_pull(self, full_name, number, method="merge"):
        if method not in MERGE_METHODS:
            raise GitHubError("Choose merge, squash or rebase.")
        data, _ = self.request(
            "PUT", "/repos/" + full_name + "/pulls/" + str(int(number)) + "/merge", {"merge_method": method}
        )
        return {"merged": bool(data.get("merged")), "message": data.get("message", "")}

    def comment(self, full_name, number, body):
        data, _ = self.request(
            "POST", "/repos/" + full_name + "/issues/" + str(int(number)) + "/comments", {"body": body}
        )
        return {"url": data["html_url"]}


class TokenStore:
    """The GitHub token for one account: OS keyring when secure, otherwise this session only."""

    def __init__(self, account_id, persist=True):
        self.account_id = account_id
        self.persist = persist
        self.session = None

    def _keyring(self):
        if not self.persist:
            return None
        try:
            import keyring

            backend = keyring.get_keyring()
        except Exception:
            return None
        if backend.priority <= 0 or "plaintext" in type(backend).__name__.lower():
            return None
        return keyring

    def get(self):
        if self.session:
            return self.session
        store = self._keyring()
        try:
            return store.get_password(KEYRING_SERVICE, self.account_id) if store else None
        except Exception:
            return None

    def set(self, token):
        """Save a token; returns True when it was remembered in the OS keyring."""
        token = (token or "").strip()
        if not token or any(c.isspace() for c in token) or len(token) > 400:
            raise GitHubError("Paste a GitHub access token.")
        self.session = token
        store = self._keyring()
        if not store:
            return False
        try:
            store.set_password(KEYRING_SERVICE, self.account_id, token)
        except Exception:
            return False
        self.session = None
        return True

    def delete(self):
        self.session = None
        store = self._keyring()
        if store:
            try:
                store.delete_password(KEYRING_SERVICE, self.account_id)
            except Exception:
                pass

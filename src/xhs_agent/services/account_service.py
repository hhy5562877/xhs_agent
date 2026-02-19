import json
import pathlib
import uuid
from datetime import datetime

DATA_FILE = pathlib.Path(__file__).parent.parent.parent.parent / "data" / "accounts.json"


def _load() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _save(accounts: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")


def list_accounts() -> list[dict]:
    """返回账号列表（不含 cookie 完整值，只返回脱敏摘要）"""
    accounts = _load()
    return [
        {
            "id": a["id"],
            "name": a["name"],
            "cookie_preview": a["cookie"][:20] + "..." if len(a.get("cookie", "")) > 20 else a.get("cookie", ""),
            "created_at": a.get("created_at", ""),
        }
        for a in accounts
    ]


def get_cookie(account_id: str) -> str | None:
    """根据 id 获取完整 cookie"""
    for a in _load():
        if a["id"] == account_id:
            return a["cookie"]
    return None


def add_account(name: str, cookie: str) -> dict:
    accounts = _load()
    account = {
        "id": str(uuid.uuid4()),
        "name": name,
        "cookie": cookie,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    accounts.append(account)
    _save(accounts)
    return {"id": account["id"], "name": account["name"], "created_at": account["created_at"]}


def delete_account(account_id: str) -> bool:
    accounts = _load()
    new_accounts = [a for a in accounts if a["id"] != account_id]
    if len(new_accounts) == len(accounts):
        return False
    _save(new_accounts)
    return True


def update_account(account_id: str, name: str | None = None, cookie: str | None = None) -> bool:
    accounts = _load()
    for a in accounts:
        if a["id"] == account_id:
            if name is not None:
                a["name"] = name
            if cookie is not None:
                a["cookie"] = cookie
            _save(accounts)
            return True
    return False

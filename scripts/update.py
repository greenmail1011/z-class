#!/usr/bin/env python3
"""登入 fzt-judge，抓 data.json 裡每位 Coder 的解題紀錄，有變化就追加一份快照。
環境變數：FZT_USER、FZT_PASS（觀看專用帳號，放在 GitHub Secrets，不寫進程式或倉庫）。
只用 Python 標準函式庫。"""
import json, os, re, sys, time, urllib.parse, urllib.request, http.cookiejar
from html.parser import HTMLParser

BASE = os.environ.get("FZT_BASE", "https://fzt-judge.com/")
DATA = os.path.join(os.path.dirname(__file__), "..", "data.json")
DL, DH = 213, 272          # DAILY 題號範圍（只記這個範圍的「進行中」）
KEEP = 300                 # 最多保留幾份快照

class Forms(HTMLParser):
    def __init__(self):
        super().__init__(); self.forms = []; self.cur = None
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form": self.cur = {"action": a.get("action", ""), "method": (a.get("method") or "get").lower(), "inputs": []}; self.forms.append(self.cur)
        elif tag == "input" and self.cur is not None: self.cur["inputs"].append(a)
    def handle_endtag(self, tag):
        if tag == "form": self.cur = None

class Stat(HTMLParser):
    """收集題號連結：AC（class=acstyle）與嘗試過但未通過（粗體灰字）。"""
    def __init__(self):
        super().__init__(); self.a = None; self.ac = set(); self.tried = set(); self.text = []
    def handle_starttag(self, tag, attrs):
        if tag == "a": self.a = dict(attrs); self.buf = ""
    def handle_data(self, data):
        self.text.append(data)
        if self.a is not None: self.buf += data
    def handle_endtag(self, tag):
        if tag == "a" and self.a is not None:
            t = self.buf.strip()
            if re.fullmatch(r"b\d{3}", t):
                n = int(t[1:]); cls = (self.a.get("class") or ""); style = self.a.get("style") or ""
                if "acstyle" in cls.split(): self.ac.add(n)
                elif re.search(r"font-weight:\s*bold", style): self.tried.add(n)
            self.a = None

def ranges(nums):
    nums = sorted(nums); out = []; i = 0
    f = lambda x: "b%03d" % x
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1: j += 1
        out.append(f(nums[i]) if j == i else f(nums[i]) + "-" + f(nums[j])); i = j + 1
    return " ".join(out)

def main():
    user, pw = os.environ.get("FZT_USER"), os.environ.get("FZT_PASS")
    if not user or not pw: sys.exit("缺少 FZT_USER / FZT_PASS")
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", "fzt-class-dashboard/1.0")]
    def get(path): return op.open(BASE + path.lstrip("/"), timeout=30).read().decode("utf-8", "replace")
    # 登入：找出含密碼欄位的表單，照表單欄位送出
    page = get("Login"); fp = Forms(); fp.feed(page)
    form = next((f for f in fp.forms if any((i.get("type") or "").lower() == "password" for i in f["inputs"])), None)
    if not form: sys.exit("找不到登入表單")
    fields = {}
    for i in form["inputs"]:
        n = i.get("name")
        if not n: continue
        ty = (i.get("type") or "text").lower()
        if ty == "password": fields[n] = pw
        elif ty in ("text", "email") and n not in fields: fields[n] = user
        elif ty == "hidden": fields[n] = i.get("value", "")
    url = urllib.parse.urljoin(BASE + "Login", form["action"] or "Login")
    op.open(urllib.request.Request(url, urllib.parse.urlencode(fields).encode(), method="POST"), timeout=30).read()

    data = json.load(open(DATA, encoding="utf-8"))
    last = data["snapshots"][-1]
    ids = sorted({i for c in data["classes"] for i in c["ids"] if not data["coders"][str(i)].get("sample")})
    ac, wip, names = {}, {}, {}
    for i in ids:
        html = get("UserStatistic?id=%d" % i); p = Stat(); p.feed(html)
        text = re.sub(r"\s+", " ", "".join(p.text))
        if "共通過" not in text: sys.exit("登入失敗或讀不到編號 %d 的統計頁（可能沒有權限）" % i)
        m = re.search(r"共通過\(AC\)\s*(\d+)", text)
        if m and int(m.group(1)) != len(p.ac): print("警告：編號 %d 頁面 AC=%s，解析到 %d 題" % (i, m.group(1), len(p.ac)))
        ac[str(i)] = ranges(p.ac)
        w = [n for n in p.tried if DL <= n <= DH and n not in p.ac]
        if w: wip[str(i)] = ranges(w)
        nm = re.search(r"基本訊息.*?\(([^)]*)\)\s*學校", text)
        if nm and nm.group(1).strip(): names[str(i)] = nm.group(1).strip()
    # 範例 Coder 沿用上一份快照
    for i, c in data["coders"].items():
        if c.get("sample"):
            if i in last["ac"]: ac[i] = last["ac"][i]
            if i in last.get("wip", {}): wip[i] = last["wip"][i]
    changed = False
    for i, n in names.items():
        if data["coders"][i]["name"] != n: data["coders"][i]["name"] = n; changed = True
    if ac != last["ac"] or wip != last.get("wip", {}):
        data["snapshots"].append({"t": time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 8 * 3600)), "ac": ac, "wip": wip})
        data["snapshots"] = data["snapshots"][-KEEP:]; changed = True
    if changed:
        json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1); print("資料已更新")
    else: print("沒有變化")

if __name__ == "__main__": main()

from flask import Flask, request, jsonify
import requests, trafilatura, concurrent.futures
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

app = Flask(__name__)

def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    retry = Retry(
        total=2, connect=2, read=1,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=100, pool_maxsize=100)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

session = make_session()

def fetch_and_extract(url: str):
    try:
        # Split connect/read timeouts to fail fast on stalled reads
        resp = session.get(url, timeout=(5, 20))
        resp.raise_for_status()
        text = trafilatura.extract(resp.text)
        return {"url": url, "text": text, "success": True}
    except Exception as e:
        return {"url": url, "error": str(e), "success": False}

@app.route("/extract", methods=["GET"])
def extract():
    urls = request.args.getlist("url")
    if not urls:
        return jsonify({"error": "At least one URL required"}), 400

    # Cap fan-out; adjust to your instance size
    max_workers = min(10, max(2, len(urls)))
    results = []

    # Hard overall deadline per request to avoid worker timeouts
    overall_deadline_seconds = 40

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_and_extract, u): u for u in urls}
        try:
            for f in concurrent.futures.as_completed(futures, timeout=overall_deadline_seconds):
                results.append(f.result())
        except concurrent.futures.TimeoutError:
            # Anything still running after deadline gets marked as timed out
            for f, u in futures.items():
                if not f.done():
                    results.append({"url": u, "error": "deadline exceeded", "success": False})

    return jsonify({"results": results})

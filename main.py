from flask import Flask, request, jsonify
import requests, trafilatura
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
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

session = make_session()

@app.route("/extract", methods=["GET"])
def extract():
    urls = request.args.getlist("url")
    if not urls:
        return jsonify({"error": "At least one URL required"}), 400

    results = []
    for url in urls:
        try:
            resp = session.get(url, timeout=(5, 25))  # 5s connect, 25s read
            resp.raise_for_status()
            text = trafilatura.extract(resp.text)
            results.append({"url": url, "text": text, "success": True})
        except Exception as e:
            results.append({"url": url, "error": str(e), "success": False})
    return jsonify({"results": results})

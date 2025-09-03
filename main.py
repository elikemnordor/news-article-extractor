from flask import Flask, request, jsonify
import requests
import trafilatura
import os

app = Flask(__name__)

@app.route('/extract', methods=['GET'])
def extract():
    urls = request.args.getlist('url')

    if not urls:
        return jsonify({"error": "At least one URL required"}), 400

    # Headers to mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    results = []
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            text = trafilatura.extract(response.text)
            results.append({"url": url, "text": text, "success": True})
        except Exception as e:
            results.append({"url": url, "error": str(e), "success": False})
    
    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True)

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

    results = []
    for url in urls:
        try:
            html = requests.get(url).text
            text = trafilatura.extract(html)
            results.append({"url": url, "text": text, "success": True})
        except Exception as e:
            results.append({"url": url, "error": str(e), "success": False})
    
    return jsonify({"results": results})


if __name__ == "__main__":
    app.run(debug=True)

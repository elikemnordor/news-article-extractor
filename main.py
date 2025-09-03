from flask import Flask, request, jsonify
import requests
import trafilatura
import os

app = Flask(__name__)

@app.route('/extract', methods=['GET'])
def extract():
    url = request.args.get('url')

    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        html = requests.get(url).text
        text = trafilatura.extract(html)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

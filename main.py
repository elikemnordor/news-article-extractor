from flask import Flask, request, jsonify
import requests
import trafilatura
import concurrent.futures
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

app = Flask(__name__)

def get_domain_headers(url):
    """Return domain-specific headers for stubborn sites"""
    try:
        domain = url.split('/')[2].lower()
    except IndexError:
        domain = ""
    
    base_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    
    # Domain-specific tweaks for stubborn sites
    if 'modernghana.com' in domain:
        base_headers.update({
            "Referer": "https://www.modernghana.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        })
    elif 'africanfinancials.com' in domain:
        base_headers.update({
            "Referer": "https://africanfinancials.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        })
    elif 'ghanaweb.com' in domain:
        base_headers.update({
            "Referer": "https://www.ghanaweb.com/",
        })
    
    return base_headers

def make_session():
    """Create a requests session with retries and connection pooling"""
    s = requests.Session()
    
    # Default headers - will be overridden per request
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    
    # Retry strategy
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    
    # HTTP adapter with connection pooling
    adapter = HTTPAdapter(
        max_retries=retry, 
        pool_connections=100, 
        pool_maxsize=100
    )
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    return s

# Global session instance
session = make_session()

def fetch_and_extract(url: str):
    """Fetch a single URL and extract text content"""
    try:
        # Get domain-specific headers
        headers = get_domain_headers(url)
        
        # Make request with custom headers
        resp = session.get(
            url, 
            headers=headers, 
            timeout=(5, 25),  # 5s connect, 25s read
            allow_redirects=True
        )
        resp.raise_for_status()
        
        # Extract text content
        text = trafilatura.extract(resp.text)
        
        return {
            "url": url, 
            "text": text, 
            "success": True
        }
        
    except requests.exceptions.HTTPError as e:
        return {
            "url": url, 
            "error": f"{e.response.status_code} {e.response.reason} for url: {url}", 
            "success": False
        }
    except requests.exceptions.Timeout:
        return {
            "url": url, 
            "error": "Request timeout", 
            "success": False
        }
    except requests.exceptions.ConnectionError:
        return {
            "url": url, 
            "error": "Connection error", 
            "success": False
        }
    except Exception as e:
        return {
            "url": url, 
            "error": str(e), 
            "success": False
        }

@app.route("/extract", methods=["GET"])
def extract():
    """Extract text from multiple URLs concurrently"""
    urls = request.args.getlist("url")
    
    if not urls:
        return jsonify({"error": "At least one URL required"}), 400
    
    print(f"[INFO] Processing {len(urls)} URLs")
    
    # Limit concurrent requests to avoid overwhelming the server
    max_workers = min(8, max(2, len(urls)))
    results = []
    
    # Overall deadline to prevent Gunicorn worker timeout
    overall_deadline_seconds = 45
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_url = {
                executor.submit(fetch_and_extract, url): url 
                for url in urls
            }
            
            # Collect results with timeout
            for future in concurrent.futures.as_completed(
                future_to_url, 
                timeout=overall_deadline_seconds
            ):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    results.append({
                        "url": url, 
                        "error": f"Processing error: {str(e)}", 
                        "success": False
                    })
                    
    except concurrent.futures.TimeoutError:
        # Handle any remaining futures that didn't complete
        for future, url in future_to_url.items():
            if not future.done():
                results.append({
                    "url": url, 
                    "error": "Overall request deadline exceeded", 
                    "success": False
                })
    
    print(f"[INFO] Completed {len(results)} results")
    
    return jsonify({"results": results})

@app.route("/health", methods=["GET"])
def health():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy", "service": "text-extractor"})

@app.route("/", methods=["GET"])
def home():
    """Basic info endpoint"""
    return jsonify({
        "service": "Text Extraction API",
        "endpoints": {
            "/extract": "Extract text from URLs (GET with ?url= params)",
            "/health": "Health check"
        },
        "usage": "GET /extract?url=https://example.com&url=https://example2.com"
    })

if __name__ == "__main__":
    app.run(debug=True)

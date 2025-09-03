from flask import Flask, request, jsonify
import requests
import trafilatura
import concurrent.futures
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

app = Flask(__name__)

def make_session():
    """Create a requests session with proper encoding handling"""
    s = requests.Session()
    
    # Simple, reliable headers that work for most sites
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",  # Simplified encoding
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    
    # Conservative retry strategy
    retry = Retry(
        total=1,  # Reduced retries
        connect=1,
        read=0,  # No read retries to avoid timeouts
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    
    return s

# Global session
session = make_session()

def extract_text_fallback(html_content, url):
    """Try multiple extraction methods"""
    
    # Method 1: trafilatura (primary)
    text = trafilatura.extract(html_content)
    if text and len(text.strip()) > 50:  # Reasonable content length
        return text.strip()
    
    # Method 2: trafilatura with different settings
    text = trafilatura.extract(
        html_content, 
        include_comments=False, 
        include_tables=True,
        no_fallback=False
    )
    if text and len(text.strip()) > 50:
        return text.strip()
    
    # Method 3: Basic fallback - extract from common tags
    try:
        from html import unescape
        import re
        
        # Remove script and style tags
        clean_html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        clean_html = re.sub(r'<style[^>]*>.*?</style>', '', clean_html, flags=re.DOTALL | re.IGNORECASE)
        
        # Extract text from common content areas
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*class="[^"]*post[^"]*"[^>]*>(.*?)</div>',
            r'<main[^>]*>(.*?)</main>',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, clean_html, re.DOTALL | re.IGNORECASE)
            if matches:
                # Clean up the matched content
                content = matches[0]
                # Remove HTML tags
                content = re.sub(r'<[^>]+>', ' ', content)
                # Clean up whitespace
                content = re.sub(r'\s+', ' ', content)
                content = unescape(content).strip()
                
                if len(content) > 100:  # Reasonable content
                    return content
    except:
        pass
    
    return None

def fetch_and_extract(url: str):
    """Fetch and extract with better error handling"""
    try:
        # Simple request with proper encoding handling
        resp = session.get(
            url,
            timeout=(5, 20),
            allow_redirects=True,
            stream=False  # Don't stream, get full content
        )
        resp.raise_for_status()
        
        # Ensure proper encoding
        if resp.encoding is None:
            resp.encoding = 'utf-8'
        
        # Get the HTML content
        html_content = resp.text
        
        # Validate we got HTML
        if not html_content or len(html_content.strip()) < 100:
            return {
                "url": url,
                "error": "Empty or too short response",
                "success": False
            }
        
        # Extract text with fallback methods
        text = extract_text_fallback(html_content, url)
        
        if text:
            return {
                "url": url,
                "text": text,
                "success": True
            }
        else:
            return {
                "url": url,
                "error": "Could not extract readable text content",
                "success": False
            }
            
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 'unknown'
        return {
            "url": url,
            "error": f"{status_code} HTTP Error",
            "success": False
        }
    except requests.exceptions.Timeout:
        return {
            "url": url,
            "error": "Request timeout",
            "success": False
        }
    except requests.exceptions.RequestException as e:
        return {
            "url": url,
            "error": f"Request failed: {str(e)[:100]}",
            "success": False
        }
    except Exception as e:
        return {
            "url": url,
            "error": f"Processing error: {str(e)[:100]}",
            "success": False
        }

@app.route("/extract", methods=["GET"])
def extract():
    """Extract text from URLs"""
    urls = request.args.getlist("url")
    
    if not urls:
        return jsonify({"error": "At least one URL required"}), 400
    
    print(f"[INFO] Processing {len(urls)} URLs")
    
    # Process with limited concurrency
    max_workers = min(6, len(urls))
    results = []
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_url = {executor.submit(fetch_and_extract, url): url for url in urls}
            
            # Collect results with timeout
            for future in concurrent.futures.as_completed(future_to_url, timeout=40):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    results.append({
                        "url": url,
                        "error": f"Task failed: {str(e)[:100]}",
                        "success": False
                    })
                    
    except concurrent.futures.TimeoutError:
        # Handle incomplete futures
        for future, url in future_to_url.items():
            if not future.done():
                results.append({
                    "url": url,
                    "error": "Request timed out",
                    "success": False
                })
    
    print(f"[INFO] Completed: {len(results)} results")
    
    # Sort results to match input order
    url_to_result = {r["url"]: r for r in results}
    sorted_results = [url_to_result.get(url, {"url": url, "error": "Missing result", "success": False}) for url in urls]
    
    return jsonify({"results": sorted_results})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

@app.route("/")
def home():
    return jsonify({
        "service": "Text Extraction API",
        "usage": "GET /extract?url=https://example.com"
    })

if __name__ == "__main__":
    app.run(debug=True)

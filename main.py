from fastapi import FastAPI
import trafilatura, requests

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Trafilatura API running"}

@app.post("/extract")
def extract(url: str):
    html = requests.get(url).text
    text = trafilatura.extract(html)
    return {"text": text}

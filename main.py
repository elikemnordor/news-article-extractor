from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"message": "Hello! Your API is running 🎉"}

@app.get("/greet")
def greet(name: str = "friend"):
    return {"message": f"Hello, {name}! 👋 Welcome to the API."}

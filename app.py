from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from rag import search

from llm import generate_answer


app=FastAPI()

BASE_DIR=Path(__file__).resolve().parent


@app.get("/", response_class=FileResponse)
def home():

    return FileResponse(
        BASE_DIR / "index.html"
    )


@app.get("/health")
def health():

    return {
    "status":
    "Mumzworld AI running"
    }



@app.get("/recommend")
@app.post("/recommend")


def recommend(query: str, lang: str = "en"):

    products = search(query)

    answer = generate_answer(
        query,
        products,
        lang=lang
    )

    return {
        "answer": answer,
        "number_of_products": len(products),
        "sources": products
    }
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Reserse")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!doctype html>
    <html lang="cs">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Reserse</title>
      </head>
      <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 16px;">
        <h1>Reserse běží</h1>
        <p>Deploy na Renderu je úspěšný.</p>
        <p>Zdravotní kontrola: <a href="/health">/health</a></p>
      </body>
    </html>
    """

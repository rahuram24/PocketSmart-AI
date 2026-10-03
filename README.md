# PocketSmart AI

PocketSmart AI is a FastAPI + Jinja2 web application for budget-aware recommendations in three domains:

- Home Interior
- Party Planning
- Jewelry

Gemini is used for personalized recommendations. Platform/product links in this student version are mock/simulated links and are not live scraping integrations.

## Run locally

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your Gemini API key.

Then:

```powershell
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Project structure

```text
PocketSmartAI/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── auth.py
│   ├── gemini_utils.py
│   ├── mock_catalog.py
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── login.html
│       ├── register.html
│       ├── dashboard.html
│       ├── planner.html
│       ├── recommendations.html
│       └── history.html
├── static/
│   ├── style.css
│   └── app.js
├── uploads/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Important

Never commit `.env` or your real Gemini API key to GitHub.

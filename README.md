# Pocketwise — Smart Expense Tracking & Personalised Budget Recommendations

A complete, simple local full-stack website based on the supplied project presentation. A teal and white responsive interface uses HTML, CSS and JavaScript with a Python Flask REST API.

## Run on Windows (Python 3.11 or 3.12 recommended)

Extract the ZIP, open its `smart-expense` folder in VS Code, then open a terminal:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:5000**. Click **Create an account**, enter your name, email, password and monthly income. No default account or password is included. The database starts empty.

## Run on macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Open http://127.0.0.1:5000. Stop the server with Ctrl+C.

## Enable receipt scanning

Install the **Tesseract OCR engine** separately; installing `pytesseract` alone does not install the engine.

- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- macOS with Homebrew: `brew install tesseract`
- Windows: install a Tesseract build and add its installation folder (commonly `C:\Program Files\Tesseract-OCR`) to your PATH. Restart the terminal afterward.

Check with `tesseract --version`. Use a clear English JPG/PNG/WebP receipt under 8 MB and 16 megapixels. OCR runs on the server, in memory. Review its results before saving.

## Features

- Registration and login with bcrypt password hashing and expiring JWT bearer tokens.
- Per-user transaction isolation; signing out invalidates existing tokens for that account.
- Add, edit, delete and search expenses; filter by month and category.
- Monthly dashboard with expenses, savings, available money, category donut and daily bars.
- Manual SMS paste, regex extraction and receipt image OCR, followed by review before saving.
- TF-IDF + Multinomial Naive Bayes categorisation, with user overrides.
- Adaptive 50/30/20 allocations, essential-spending rebalance and pacing alerts.
- Monthly income setup and updates; export all account transactions to CSV.
- Responsive desktop and mobile layout, keyboard controls and empty/error states.

## A quick demonstration

1. Create an account with monthly income ₹50,000.
2. Add `Weekly groceries`, ₹2,500, category Groceries, today.
3. Add `House rent`, ₹24,000, category Housing, today.
4. Add `Emergency fund`, ₹5,000, category Savings, today.
5. Needs spending is ₹26,500. The original Needs budget is ₹25,000. The app moves ₹1,500 from unspent Wants to Needs, preserving the ₹10,000 Savings target.
6. Open Smart capture → Paste a bank SMS → Use an example → Extract message. Verify the amount, date and category, then save.
7. Edit/delete transactions and confirm totals change. Export the ledger to CSV.

## Budget rules

Income is the user's current planning baseline for every selected month (this simple version does not keep historical income snapshots). Expenses are Needs + Wants. Savings transfers are tracked separately. Available money = income − expenses − recorded savings.

Original envelopes: Needs 50%, Wants 30%, Savings 20%. Essential overruns can use only unspent Wants. Savings are not reduced automatically. If no available Wants remains, an over-budget warning appears. Pacing projections use spending divided by elapsed days, multiplied by days in the selected month; these projections are shown only for the current month. Negative available money is shown rather than hidden.

Other defaults to Wants, and should be reviewed. This version records outflows and savings allocations, not a double-entry bank ledger or an income/credit/refund importer. All values are in INR.

## Database and configuration

SQLite is the default, at `instance/expense.db`. User details and a relational expense ledger are persisted there. A private signing key is created in `instance/.secret` on first run. Back up both files locally if you need to preserve accounts. Never commit or share this directory.

PostgreSQL is optional. Create an empty database, then set `DATABASE_URL` before running:

```powershell
$env:DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/smart_expense"
$env:SECRET_KEY="your-long-random-secret"
.venv\Scripts\python.exe app.py
```

On Linux/macOS, use `export DATABASE_URL='...'` and `export SECRET_KEY='...'`. `.env.example` describes the keys; it is a reference and is not loaded automatically. SQLAlchemy creates the tables on startup.

## Project structure

```text
smart-expense/
  app.py                  Flask API, authentication and database models
  intelligence.py         ML classifier, extraction and budget algorithms
  requirements.txt        Python dependencies
  templates/index.html    Application screens and dialogs
  static/app.js           Frontend interactions and API calls
  static/style.css        Responsive styling
  static/favicon.svg      App icon
  tests/test_app.py       API, isolation and algorithm tests
  README.md               Setup and project explanation
  .env.example            Optional configuration
```

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests use an isolated temporary database and do not change your real accounts.

## Scope relative to the document

Implemented: web UI, authentication, OCR receipt parsing, manual SMS parsing, TF-IDF classification, relational ledger, budget optimisation and in-app alerts.

The small bundled training corpus demonstrates the pipeline. It is not the 12,000-token benchmark described in the presentation; no 94.8% accuracy, extraction latency or savings-uplift claim is made. Categorisation and parsing require review. Receipt parsing supports common English total labels and dates, not every merchant format. Credits/refunds and multiple totals can be ambiguous.

This deliverable is a local academic project. It does not include an Android SMS receiver, bank webhook, Redis, background OCR queue, push notifications, production rate limiting, email verification or an audited encryption-at-rest layer. Passwords are hashed; transaction fields are not encrypted at rest. Use synthetic data while demonstrating it. A production deployment would also require HTTPS, a production WSGI server, hardened authentication/rate limiting, migrations, monitoring and a privacy review. Flask's bundled development server is provided for local use only.

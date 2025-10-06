MailPrioritisor - backend
-------------------------

Setup (Windows PowerShell):
1. cd backend
2. python -m venv .venv
3. .\.venv\Scripts\Activate.ps1
4. pip install -r requirements.txt
5. Place credentials.json in this folder (OAuth client from Google Cloud).
6. Run: python gmail_test.py  # obtains token.json via browser
7. Run: python fetch_unread.py

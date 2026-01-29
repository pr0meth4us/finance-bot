import os
from pathlib import Path
from dotenv import load_dotenv
from app import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / '.env'

load_dotenv(ENV_PATH, override=True)

app = create_app()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
from openai import OpenAI
# Import from project root with proper path setup
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from local_secrets import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

resp = client.responses.create(
    model="gpt-4.1-mini",
    input="Reply with exactly: OK"
)

print(resp.output_text)


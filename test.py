import requests
import os

headers = {
    "Authorization": f"Bearer {os.getenv('STRATZ_API_TOKEN')}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

query = """
{
  player(steamAccountId: 70388657) {
    soloCompetitiveRank
  }
}
"""

response = requests.post(
    "https://api.stratz.com/graphql",
    json={"query": query},
    headers=headers,
)

try:
    print(response.json())
except Exception:
    print("Response content:", response.text)
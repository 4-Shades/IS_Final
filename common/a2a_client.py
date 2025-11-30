import httpx
import json

async def call_agent(url, payload):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=60.0)
            response.raise_for_status()
            
            # Try to parse JSON
            try:
                return response.json()
            except json.JSONDecodeError:
                # If response is not JSON (e.g. plain string), return it as is
                # This prevents "Expecting value: line 1 column 1" crashes
                print(f"Warning: Agent at {url} returned non-JSON: {response.text[:100]}...")
                return response.text
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error calling {url}: {e}")
            return {}
        except Exception as e:
            print(f"Error calling {url}: {e}")
            return {}
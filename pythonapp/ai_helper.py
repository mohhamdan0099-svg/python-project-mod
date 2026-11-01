# ai_helper.py - the only file that talks to the AI (this version uses Google Gemini).
# The key is NOT written here: the library reads it from the GEMINI_API_KEY environment variable.
import json
 
from google import genai
 
# If you get a "model not found" or quota error, try 'gemini-2.5-flash-lite'
# and check the model names in the Gemini docs.
USE_DEMO = False
MODEL = 'gemini-3.6-flash'
 
 
def ask_ai(prompt):
    """Send one question to the AI and return its answer as text."""
    client = genai.Client()          # reads GEMINI_API_KEY from the environment
    response = client.models.generate_content(model=MODEL, contents=prompt)
    return (response.text or '').strip()
 
 
def write_description(name, category, notes):
    """Provider feature: turn a name and rough notes into a clean description."""
    prompt = (
        f'Write a friendly, professional description of at most 40 words for a service '
        f'called "{name}" in the category "{category}". '
        f'The provider\'s rough notes: {notes}. '
        'Write in the same language as the notes (English if there are no notes). '
        'Return only the description text.'
    )
    return ask_ai(prompt)
 
 
def parse_ids(text):
    """Turn an answer like '[12, 5]' into the Python list [12, 5]. Anything else gives []."""
    start = text.find('[')
    end = text.rfind(']')
    try:
        ids = json.loads(text[start:end + 1])
    except ValueError:
        return []
    if not isinstance(ids, list):
        return []
    return [i for i in ids if isinstance(i, int)]
 
 
def smart_search(need, services_text):
    """Client feature: the AI chooses service ids that fit what the client wrote."""
    prompt = (
        'You help clients find services on a booking website in the West Bank. '
        'Here are the services, one per line: '
        'id | name | category | profession | city | price in NIS | minutes\n'
        f'{services_text}\n\n'
        f'The client wrote (English or Arabic): "{need}"\n'
        'Choose the services that best fit the need. '
        'Respect the city and the budget if the client mentions them. '
        'Answer ONLY with a JSON list of at most 6 service ids, best first, for example [12, 5]. '
        'If nothing fits, answer [].'
    )
    return parse_ids(ask_ai(prompt))
 

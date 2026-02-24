import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a

load_dotenv()

from .agent import root_agent  # noqa: E402

app = to_a2a(root_agent, host="0.0.0.0", port=8002)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)

"""Release Manager Agent - front-line of the two-hop Delegation chain
(Flow 2). Exchanges the user's token at the STS, then delegates to Deploy
Agent, passing the exchanged (not raw) token - Deploy Agent re-exchanges it
in turn, producing a nested act chain (chain-of-custody)."""
import os

import requests
from google.adk.agents import LlmAgent
from ops_agent import sts
from ops_agent.harness import build_app
from ops_agent.openai_model import OpenAIModel

INSTRUCTION = (
    "You are the Release Manager Agent. When asked about a deploy, use the "
    "ask_deploy_agent tool to delegate to the Deploy Agent and relay its answer, "
    "including the delegation chain it reports."
)


def ask_deploy_agent(query: str, token: str) -> dict:
    """Delegate a deploy-related request to the Deploy Agent, passing along
    the caller's exchanged authorization token."""
    resp = requests.post(
        os.environ["DEPLOY_AGENT_URL"], json={"query": query, "token": token}, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def build_agent(token: str, mode: str):
    sa_token = sts.read_sa_token(os.environ.get("SA_TOKEN_PATH", sts.DEFAULT_SA_TOKEN_PATH))
    delegated_token = sts.exchange(os.environ["STS_URL"], token, sa_token)

    def ask_deploy_agent_tool(query: str) -> dict:
        """Ask the Deploy Agent to check or perform a deploy-related action."""
        return ask_deploy_agent(query, delegated_token)

    agent = LlmAgent(
        model=OpenAIModel(
            model=os.environ.get("MODEL", "gpt-4o-mini"),
            api_base=os.environ["LLM_BASE_URL"],
            api_key=os.environ.get("LLM_API_KEY", "unused"),
        ),
        name="release_manager_agent",
        instruction=INSTRUCTION,
        tools=[ask_deploy_agent_tool],
    )
    return agent, delegated_token, {}


app = build_app(build_agent)

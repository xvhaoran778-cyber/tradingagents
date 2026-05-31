from llm.client import LLMClient
from config import DEEP_MODEL


class BaseAgent:
    name: str = "base"

    def __init__(self, llm: LLMClient, model: str = None):
        self.llm = llm
        self.model = model or DEEP_MODEL

    @property
    def system_prompt(self) -> str:
        raise NotImplementedError

    def build_messages(self, state: "AgentState", **kwargs) -> list[dict]:
        system = {"role": "system", "content": self.system_prompt}
        context = self._build_context(state, **kwargs)
        return [system, {"role": "user", "content": context}]

    def _build_context(self, state: "AgentState", **kwargs) -> str:
        raise NotImplementedError

    def analyze(self, state: "AgentState", **kwargs) -> str:
        messages = self.build_messages(state, **kwargs)
        return self.llm.chat(messages, model=self.model)

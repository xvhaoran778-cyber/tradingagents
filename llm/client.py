import json
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEP_MODEL, QUICK_MODEL

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, APITimeoutError)),
)


class LLMClient:
    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)

    @_RETRY
    def chat(self, messages, model=None, temperature=0.7, stream=False):
        model = model or DEEP_MODEL
        kwargs = dict(model=model, messages=messages, temperature=temperature, stream=stream)
        response = self.client.chat.completions.create(**kwargs)
        if stream:
            return response
        return response.choices[0].message.content

    @_RETRY
    def chat_json(self, messages, model=None, temperature=0.3):
        response = self.client.chat.completions.create(
            model=model or DEEP_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = response.choices[0].message.content
        return json.loads(content)

    @_RETRY
    def chat_quick(self, messages, temperature=0.5):
        return self.chat(messages, model=QUICK_MODEL, temperature=temperature)

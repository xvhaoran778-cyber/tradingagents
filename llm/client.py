import json
import re
import sys
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEP_MODEL, QUICK_MODEL

_RETRY = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=6),
    retry=retry_if_exception_type((APIError, RateLimitError, APITimeoutError)),
)

_DEBUG = True


def _debug(msg):
    if _DEBUG:
        print(f"[LLM] {msg}", file=sys.stderr, flush=True)


class LLMClient:
    def __init__(self, timeout=120):
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY 未设置，请在 .env 文件中配置")
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=timeout)

    @_RETRY
    def chat(self, messages, model=None, temperature=0.7, stream=False):
        model = model or DEEP_MODEL
        _debug(f"chat() model={model} msgs={len(messages)}")
        kwargs = dict(model=model, messages=messages, temperature=temperature, stream=stream)
        response = self.client.chat.completions.create(**kwargs)
        if stream:
            return response
        content = response.choices[0].message.content
        _debug(f"chat() OK len={len(content) if content else 0}")
        return content

    def chat_json(self, messages, model=None, temperature=0.3):
        model = model or DEEP_MODEL
        _debug(f"chat_json() model={model} msgs={len(messages)}")

        # 1. response_format
        try:
            _debug("attempt 1: response_format")
            resp = self.client.chat.completions.create(
                model=model, messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            content = resp.choices[0].message.content
            _debug(f"attempt 1 raw length={len(content) if content else 0}")
            _debug(f"attempt 1 raw start={content[:200] if content else 'EMPTY'}")
            if content:
                return json.loads(content)
        except Exception as e:
            _debug(f"attempt 1 failed: {e}")

        # 2. chat + extract
        try:
            _debug("attempt 2: chat + extract")
            messages2 = messages + [{"role": "user", "content": "请只输出JSON，不要其他文字。"}]
            content = self.chat(messages2, model=model, temperature=temperature)
            _debug(f"attempt 2 raw start={content[:200] if content else 'EMPTY'}")
            result = _extract_json(content)
            if result is not None:
                return result
            _debug("attempt 2 extract failed")
        except Exception as e:
            _debug(f"attempt 2 failed: {e}")

        # 3. force system prompt
        try:
            _debug("attempt 3: force system prompt")
            schema = ('{"rating": "Buy/Overweight/Hold/Underweight/Sell", '
                      '"rating_cn": "强烈买入/增持/持有/减持/卖出", '
                      '"executive_summary": "决策摘要", '
                      '"investment_thesis": "详细投资论点", '
                      '"risk_warning": "风险提示", '
                      '"price_target": "目标价", '
                      '"time_horizon": "持有周期"}')
            forced = [{"role": "system", "content": f"你只输出JSON，不要任何其他文字。格式: {schema}"}] + messages[1:]
            content = self.chat(forced, model=model, temperature=temperature)
            _debug(f"attempt 3 raw start={content[:200] if content else 'EMPTY'}")
            result = _extract_json(content)
            if result is not None:
                return result
            _debug("attempt 3 extract failed")
        except Exception as e:
            _debug(f"attempt 3 failed: {e}")

        _debug("ALL attempts failed")
        return None

    @_RETRY
    def chat_quick(self, messages, temperature=0.5):
        return self.chat(messages, model=QUICK_MODEL, temperature=temperature)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    for prefix in ("```json", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end+1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

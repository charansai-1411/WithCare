import asyncio
import json

from google import genai
from google.genai import types

from app.config import settings
from app.utils.exceptions import GeminiServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: genai.Client | None = None

# Every Gemini call is bounded: a hard per-call timeout (so a stalled Vertex request can't
# hang a chat forever) and a couple of retries on transient errors (429/503/500/deadline),
# which Vertex returns intermittently under load.
_CALL_TIMEOUT_S = 60
_RETRIES = 2


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_location,
            # Bound the underlying HTTP call too (ms), so a timed-out thread also unwinds.
            http_options=types.HttpOptions(timeout=_CALL_TIMEOUT_S * 1000),
        )
        logger.info(f"Gemini client initialized (project={settings.gcp_project_id}, model={settings.gemini_model})")
    return _client


def _is_transient(e: Exception) -> bool:
    """True for errors worth retrying — rate limits and transient server/deadline errors."""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if code in (429, 500, 503):
        return True
    s = str(e).lower()
    return any(k in s for k in (
        "429", "resource_exhausted", "resourceexhausted", "rate limit",
        "503", "unavailable", "500", "internal error", "deadline", "temporarily",
    ))


async def _acall(fn, *, timeout: float = _CALL_TIMEOUT_S, retries: int = _RETRIES):
    """Run a blocking Gemini SDK call OFF the event loop (so it never freezes other requests),
    bounded by `timeout`, with exponential-backoff retries on transient errors."""
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
        except asyncio.TimeoutError as e:
            last = e
            logger.warning(f"Gemini call timed out after {timeout}s (attempt {attempt + 1}/{retries + 1})")
        except Exception as e:
            last = e
            if attempt < retries and _is_transient(e):
                delay = 0.8 * (2 ** attempt)
                logger.warning(f"Gemini transient error (attempt {attempt + 1}), retrying in {delay:.1f}s: {e}")
                await asyncio.sleep(delay)
                continue
            raise
        if attempt < retries:  # timed out but attempts remain
            await asyncio.sleep(0.8 * (2 ** attempt))
    raise GeminiServiceError(f"Gemini call failed after {retries + 1} attempts: {last}")


async def generate_structured(
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
) -> dict:
    """
    Calls Gemini with a JSON response schema and returns a parsed dict.
    Uses response_mime_type=application/json to force structured output.
    """
    client = get_gemini_client()

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )

    try:
        response = await _acall(_call)
        raw = (response.text or "").strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        raise GeminiServiceError(f"Invalid JSON from Gemini: {e}")
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.error(f"Gemini generate_structured failed: {e}")
        raise GeminiServiceError(str(e))


async def generate_with_search(system_prompt: str, user_prompt: str) -> str:
    """
    Grounded generation using Google Search (Vertex). Returns the model's text.
    Note: JSON response_schema can't be combined with the search tool, so callers that
    want structured output should instruct the model to emit JSON in the prompt and parse it.
    """
    client = get_gemini_client()
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.3,
        max_output_tokens=4096,
        tools=[types.Tool(google_search=types.GoogleSearch())],
    )
    # Gemini 2.5 spends output budget on "thinking", which truncated the answer.
    # Disable it so the full grounded response fits (ignored by models w/o thinking).
    try:
        config.thinking_config = types.ThinkingConfig(thinking_budget=0)
    except Exception:
        pass

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model, contents=user_prompt, config=config,
        )

    try:
        response = await _acall(_call)
        return (response.text or "").strip()
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.error(f"Gemini grounded search failed: {e}")
        raise GeminiServiceError(str(e))


def _extract_json(raw: str):
    """Pull a JSON value out of a model reply (strips ``` fences / prose). Returns (value, error)."""
    if not raw or not raw.strip():
        return None, "empty response"
    import re
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    # Prefer the outermost array or object.
    m = re.search(r"(\[.*\]|\{.*\})", cleaned, flags=re.DOTALL)
    candidate = m.group(0) if m else cleaned
    try:
        return json.loads(candidate), ""
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


async def generate_json_self_correcting(
    system_prompt: str,
    user_prompt: str,
    validate=None,          # optional callable(value) -> raises on invalid
    retries: int = 1,       # correction attempts after the first try
    grounded: bool = False, # use Google Search grounding
):
    """
    Self-correcting structured generation: call Gemini, parse+validate the JSON, and if it's
    malformed (or fails validation) re-prompt the model WITH the error log so it repairs the
    structure — before the caller renders it. Returns the parsed value, or None if it never
    produced valid output.
    """
    gen = generate_with_search if grounded else generate_text
    prompt, last_err, raw = user_prompt, "", ""
    for attempt in range(retries + 1):
        raw = await gen(system_prompt, prompt)
        value, err = _extract_json(raw)
        if value is not None and validate is not None:
            try:
                validate(value)
            except Exception as ve:
                value, err = None, f"validation failed: {ve}"
        if value is not None:
            if attempt:
                logger.info(f"self-correction succeeded on attempt {attempt + 1}")
            return value
        last_err = err
        logger.warning(f"self-correcting JSON attempt {attempt + 1} failed — {err}")
        prompt = (
            f"{user_prompt}\n\n--- YOUR PREVIOUS REPLY COULD NOT BE PARSED ---\n"
            f"Error: {err}\nWhat you returned:\n{raw[:1500]}\n\n"
            "Return ONLY valid JSON that fixes this exact error. No prose, no markdown, no code fences."
        )
    logger.error(f"self-correcting JSON gave up after {retries + 1} tries: {last_err}")
    return None


def build_tools(declarations: list[dict]) -> list:
    """Turn [{name, description, parameters(json-schema)}] into google-genai Tool objects."""
    fns = [
        types.FunctionDeclaration(
            name=d["name"],
            description=d["description"],
            parameters_json_schema=d["parameters"],
        )
        for d in declarations
    ]
    return [types.Tool(function_declarations=fns)]


async def generate_with_tools(system_instruction: str, contents: list, tools: list, temperature: float = 0.3):
    """One function-calling round to Gemini. Returns the raw response (caller drives the loop).
    Runs off the event loop with a timeout + transient-error retries."""
    client = get_gemini_client()

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=temperature,
                max_output_tokens=2048,
            ),
        )

    return await _acall(_call)


async def transcribe_audio(data: bytes, mime_type: str = "audio/webm", language_hint: str = "") -> str:
    """Speech-to-text via Gemini (multimodal) — reuses the Vertex client, so no separate
    Speech-to-Text API is needed. Handles English + Indian languages and code-switching."""
    client = get_gemini_client()
    lang = f" The speaker is most likely speaking {language_hint}." if language_hint else ""
    instruction = (
        "You transcribe speech to text for a healthcare-navigation assistant used in India. "
        "Transcribe the following audio VERBATIM." + lang +
        " The speaker may use English or an Indian language (Hindi, Telugu, Tamil, Kannada, "
        "Malayalam, Marathi, Bengali, Gujarati, Punjabi, Urdu) and may mix languages "
        "(code-switching) — transcribe exactly what is said, in the script of the language "
        "spoken. Output ONLY the transcript text: no quotes, labels, timestamps, or commentary. "
        "If there is no intelligible speech, output nothing."
    )

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=[
                types.Part(text=instruction),
                types.Part.from_bytes(data=data, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=1024,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

    try:
        resp = await _acall(_call, timeout=45)
        return (resp.text or "").strip()
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.error(f"Gemini transcription failed: {e}")
        raise GeminiServiceError(str(e))


async def generate_text(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Simple text generation — used for explanations and summaries."""
    client = get_gemini_client()

    def _call():
        return client.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                # Gemini 2.5 "thinking" tokens count against max_output_tokens; with thinking on
                # and a small cap the visible answer gets truncated (a 7-day plan came back as just
                # the intro sentence). Disable thinking and give the answer real room.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                max_output_tokens=4096,
            ),
        )

    try:
        response = await _acall(_call)
        return (response.text or "").strip()
    except GeminiServiceError:
        raise
    except Exception as e:
        logger.error(f"Gemini generate_text failed: {e}")
        raise GeminiServiceError(str(e))

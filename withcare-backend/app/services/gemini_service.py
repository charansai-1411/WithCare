import json

from google import genai
from google.genai import types

from app.config import settings
from app.utils.exceptions import GeminiServiceError
from app.utils.logger import get_logger

logger = get_logger(__name__)

_client: genai.Client | None = None


def get_gemini_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(
            vertexai=True,
            project=settings.gcp_project_id,
            location=settings.gemini_location,
        )
        logger.info(f"Gemini client initialized (project={settings.gcp_project_id}, model={settings.gemini_model})")
    return _client


async def generate_structured(
    system_prompt: str,
    user_prompt: str,
    response_schema: dict,
) -> dict:
    """
    Calls Gemini with a JSON response schema and returns a parsed dict.
    Uses response_mime_type=application/json to force structured output.
    """
    try:
        client = get_gemini_client()

        response = client.models.generate_content(
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

        raw = response.text.strip()
        result = json.loads(raw)
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        raise GeminiServiceError(f"Invalid JSON from Gemini: {e}")
    except Exception as e:
        logger.error(f"Gemini generate_structured failed: {e}")
        raise GeminiServiceError(str(e))


async def generate_with_search(system_prompt: str, user_prompt: str) -> str:
    """
    Grounded generation using Google Search (Vertex). Returns the model's text.
    Note: JSON response_schema can't be combined with the search tool, so callers that
    want structured output should instruct the model to emit JSON in the prompt and parse it.
    """
    try:
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
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=config,
        )
        return (response.text or "").strip()
    except Exception as e:
        logger.error(f"Gemini grounded search failed: {e}")
        raise GeminiServiceError(str(e))


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


def generate_with_tools(system_instruction: str, contents: list, tools: list, temperature: float = 0.3):
    """One function-calling round to Gemini. Returns the raw response (caller drives the loop)."""
    client = get_gemini_client()
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


async def generate_text(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Simple text generation — used for explanations and summaries."""
    try:
        client = get_gemini_client()

        response = client.models.generate_content(
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
        return (response.text or "").strip()

    except Exception as e:
        logger.error(f"Gemini generate_text failed: {e}")
        raise GeminiServiceError(str(e))

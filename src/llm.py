import os
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()


def get_model(model_name: str | None = None) -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
    api_key = os.getenv("LLM_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "LLM_API_KEY not found. Copy .env.example to .env and add your key."
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name or "claude-3-5-sonnet-20241022",
            anthropic_api_key=api_key,
            max_tokens=1024,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            api_key=api_key,
        )

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-2.5-pro",
            google_api_key=api_key,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER '{provider}'. Supported values: 'anthropic', 'openai', 'google'."
    )

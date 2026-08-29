__all__ = []

try:
    from .langchain import ECPLangChainAdapter as ECPLangChainAdapter

    __all__.append("ECPLangChainAdapter")
except Exception:
    # Optional dependency.
    pass

try:
    from .llama_index import ECPLlamaIndexAdapter as ECPLlamaIndexAdapter

    __all__.append("ECPLlamaIndexAdapter")
except Exception:
    # Optional dependency.
    pass

try:
    from .crewai import ECPCrewAIAdapter as ECPCrewAIAdapter

    __all__.append("ECPCrewAIAdapter")
except Exception:
    # Optional dependency.
    pass

try:
    from .pydantic_ai import ECPPydanticAIAdapter as ECPPydanticAIAdapter

    __all__.append("ECPPydanticAIAdapter")
except Exception:
    # Optional dependency.
    pass

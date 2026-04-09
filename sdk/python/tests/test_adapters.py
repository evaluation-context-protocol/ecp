import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SDK_SRC = Path(__file__).resolve().parents[1] / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))


class AdapterNormalizationTests(unittest.TestCase):
    def _load_langchain_adapter(self):
        callbacks_mod = types.ModuleType("langchain_core.callbacks")
        outputs_mod = types.ModuleType("langchain_core.outputs")
        callbacks_mod.BaseCallbackHandler = object
        outputs_mod.LLMResult = object
        with mock.patch.dict(
            sys.modules,
            {
                "langchain_core": types.ModuleType("langchain_core"),
                "langchain_core.callbacks": callbacks_mod,
                "langchain_core.outputs": outputs_mod,
            },
        ):
            module = importlib.import_module("ecp.adaptors.langchain")
            module = importlib.reload(module)
        return module.ECPLangChainAdapter

    def test_langchain_tool_call_string_arguments_normalized(self):
        adapter_cls = self._load_langchain_adapter()
        adapter = adapter_cls(runnable=SimpleNamespace(invoke=lambda *_args, **_kwargs: "ok"))
        normalized = adapter._normalize_tool_calls(
            [{"name": "calculator", "arguments": "{\"expression\": \"2+2\"}"}]
        )
        self.assertEqual(normalized[0]["name"], "calculator")
        self.assertEqual(normalized[0]["arguments"]["expression"], "2+2")

    def test_crewai_tool_call_string_arguments_normalized(self):
        from ecp.adaptors.crewai import ECPCrewAIAdapter

        adapter = ECPCrewAIAdapter(crew=SimpleNamespace(kickoff=lambda **_kwargs: "ok"))
        normalized = adapter._normalize_tool_calls(
            [{"name": "calculator", "arguments": "{\"expression\": \"2+2\"}"}]
        )
        self.assertEqual(normalized[0]["arguments"]["expression"], "2+2")

    def test_llama_index_function_payload_normalized(self):
        from ecp.adaptors.llama_index import ECPLlamaIndexAdapter

        adapter = ECPLlamaIndexAdapter(workflow=SimpleNamespace(run=lambda **_kwargs: None))
        normalized = adapter._normalize_tool_calls(
            [
                {
                    "function": {
                        "name": "calculator",
                        "arguments": "{\"expression\": \"2+2\"}",
                    }
                }
            ]
        )
        self.assertEqual(normalized[0]["name"], "calculator")
        self.assertEqual(normalized[0]["arguments"]["expression"], "2+2")

    def test_pydantic_ai_tool_calls_captured(self):
        from ecp.adaptors.pydantic_ai import ECPPydanticAIAdapter

        class _ToolCallPart:
            part_kind = "tool-call"
            tool_name = "calculator"

            def args_as_dict(self):
                return {"expression": "2+2"}

        class _ResponseMsg:
            kind = "response"
            parts = [_ToolCallPart()]

        class _RunResult:
            data = "4"
            output = "4"

            def new_messages(self):
                return [_ResponseMsg()]

            def usage(self):
                return SimpleNamespace(input_tokens=1, output_tokens=1, requests=1)

        fake_agent = SimpleNamespace(run_sync=lambda *_args, **_kwargs: _RunResult())
        adapter = ECPPydanticAIAdapter(fake_agent)
        result = adapter.step("2+2")
        self.assertEqual(result.tool_calls[0]["name"], "calculator")
        self.assertEqual(result.tool_calls[0]["arguments"]["expression"], "2+2")


if __name__ == "__main__":
    unittest.main()

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../sdk/python/src')))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from ecp import serve
from ecp.adaptors.langchain import ECPLangChainAdapter

# 1. Define a Parser that hides thoughts from the final output
class ThoughtSplitter(BaseOutputParser):
    def parse(self, text: str):
        # If the model followed instructions, it splits here
        if "FINAL ANSWER:" in text:
            return text.split("FINAL ANSWER:")[-1].strip()
        return text

# 2. Force the model to use the format
model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0) # Temp 0 for consistency

prompt = ChatPromptTemplate.from_template(
    """
    Solve this math problem: {question}
    
    FORMAT INSTRUCTIONS:
    You MUST output your response in two parts.
    Part 1: THOUGHT: (Your step-by-step logic)
    Part 2: FINAL ANSWER: (The number only)
    
    Example:
    THOUGHT: 1+1 is 2.
    FINAL ANSWER: 2
    """
)

# 3. The Chain: Prompt -> Model -> Splitter
# The Adapter sees the RAW output (Thought + Final)
# The User sees the PARSED output (Final only)
chain = prompt | model | ThoughtSplitter()

ecp_agent = ECPLangChainAdapter(chain, name="LogicBot")

if __name__ == "__main__":
    serve(ecp_agent)
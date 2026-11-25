from supportx.llm import LLMService

llm = LLMService()

print("LLM mode:", llm.mode)

response = llm.generate(
    "A customer says they were charged twice. "
    "Write a short, helpful customer support response."
)

print("\nGroq response:")
print(response)

class ModelAdapter:
    def __init__(self,invoke): self._invoke=invoke
    def run(self,prompt):
        if not isinstance(prompt,str) or not prompt.strip(): raise ValueError("non-empty prompt required")
        return self._invoke(prompt)

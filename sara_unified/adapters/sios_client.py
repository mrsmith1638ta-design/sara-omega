class SIOSClient:
    def __init__(self,transport): self.transport=transport
    def authorize(self,payload): return self.transport(payload)

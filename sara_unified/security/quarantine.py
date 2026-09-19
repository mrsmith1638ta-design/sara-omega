class QuarantineRegistry:
    def __init__(self): self._items={}
    def quarantine(self, subject, reason): self._items[subject]=reason
    def release(self, subject): self._items.pop(subject,None)
    def is_quarantined(self, subject): return subject in self._items
    def reason(self, subject): return self._items.get(subject)

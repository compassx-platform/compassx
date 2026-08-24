# Building Custom Agent Tools

Extend CompassX with custom analytical tools, database connectors, and specialized ML algorithms.

---

## Tool Definition Example

```python
from compassx.tools import BaseTool

class SentimentAnalyzerTool(BaseTool):
    name = "sentiment_analyzer"
    description = "Analyzes customer feedback sentiment"

    def run(self, text: str) -> dict:
        return {"sentiment": "positive", "confidence": 0.94}
```

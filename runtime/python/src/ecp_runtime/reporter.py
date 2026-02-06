import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from jinja2 import Template

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>ECP Evaluation Report</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f4f4f9; }
        .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        h1 { border-bottom: 2px solid #ddd; padding-bottom: 10px; }
        .meta { color: #666; font-size: 0.9em; }
        pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>ECP Evaluation Report</h1>
    <div class="meta">Generated: {{ timestamp }}</div>
    
    {% for scenario in results %}
    <div class="card">
        <h2>Scenario: {{ scenario.name }}</h2>
        {% for step in scenario.steps %}
        <div style="border-top: 1px solid #eee; margin-top: 10px; padding-top: 10px;">
            <p><strong>Input:</strong> {{ step.input }}</p>
            <p><strong>Output:</strong> {{ step.output }}</p>
            
            <h4>Graders:</h4>
            <ul>
            {% for check in step.checks %}
                <li>
                    <span class="{{ 'pass' if check.passed else 'fail' }}">
                        {{ '✅ PASS' if check.passed else '❌ FAIL' }}
                    </span>
                    {{ check.type }} 
                    {% if check.reasoning %}
                    <br><small>Reason: {{ check.reasoning }}</small>
                    {% endif %}
                </li>
            {% endfor %}
            </ul>
        </div>
        {% endfor %}
    </div>
    {% endfor %}
</body>
</html>
"""

class HTMLReporter:
    def __init__(self):
        self.results = []

    def add_scenario(self, name: str, steps: List[Dict[str, Any]]):
        self.results.append({"name": name, "steps": steps})

    def save(self, filepath: str):
        template = Template(HTML_TEMPLATE)
        html_content = template.render(
            results=self.results,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        Path(filepath).write_text(html_content, encoding="utf-8")
        return filepath
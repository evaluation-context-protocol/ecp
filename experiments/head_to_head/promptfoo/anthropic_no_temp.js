/**
 * A minimal Promptfoo provider for the Anthropic Messages API that sends no
 * `temperature`.
 *
 * Why this exists: Promptfoo's built-in `anthropic:messages:*` provider always sends a
 * temperature (default 0) unless extended thinking is enabled, and claude-haiku-5-5
 * rejects it with HTTP 400 "`temperature` is deprecated for this model". Enabling
 * thinking would change what is being graded, so the comparison uses this instead.
 * DeepEval needed an equivalent custom model class for the same reason.
 */
const MODEL = process.env.GRADER_MODEL || 'claude-haiku-5-5';

class AnthropicNoTemperature {
  id() {
    return `anthropic-no-temperature:${MODEL}`;
  }

  async callApi(prompt) {
    // llm-rubric hands the grader its prompt as a JSON chat array; Anthropic wants
    // the system text separate from the user/assistant turns.
    let system = '';
    let messages = [{ role: 'user', content: String(prompt) }];
    try {
      const parsed = JSON.parse(prompt);
      if (Array.isArray(parsed)) {
        system = parsed.filter((m) => m.role === 'system').map((m) => m.content).join('\n');
        messages = parsed
          .filter((m) => m.role !== 'system')
          .map((m) => ({ role: m.role, content: m.content }));
      }
    } catch (_) {
      /* a plain string prompt */
    }

    const body = { model: MODEL, max_tokens: 1024, messages };
    if (system) body.system = system;

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(body),
    });
    const json = await res.json();
    if (!res.ok) {
      return { error: `HTTP ${res.status}: ${JSON.stringify(json).slice(0, 300)}` };
    }
    const text = (json.content || []).filter((b) => b.type === 'text').map((b) => b.text).join('');
    return { output: text };
  }
}

module.exports = AnthropicNoTemperature;

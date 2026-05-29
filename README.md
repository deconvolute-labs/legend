# Legend

![Python](https://img.shields.io/badge/python-3.13+-blue?style=flat-square&logo=python&logoColor=white)
![PyPI](https://img.shields.io/badge/pypi-legend_pii-blue?style=flat-square&logo=pypi&logoColor=white)
![License](https://img.shields.io/badge/license-Apache%202.0-green?style=flat-square)
![Status](https://img.shields.io/badge/status-active-brightgreen?style=flat-square)

**PII pseudonymization for the full agentic loop.**

---

Agent pipelines expose PII at every step: in user prompts, tool call arguments, tool results, and final responses. Legend intercepts at all four points, replacing PII with realistic pseudonyms before it reaches external APIs or leaves your infrastructure, and restoring the original values exactly in the final response.

---

## Design

The pseudonymization strategy is grounded in recent research showing that realistic substitutes preserve utility significantly better than suppression or redaction across multi-turn interactions. Legend extends the single-boundary pseudonymization approach of LOPSIDED (Serenari & Lee, 2025) to the full four-boundary agentic loop, addressing the leakage surface that existing tools leave uncovered.

---

## Getting Started

### Requirements

- Python 3.13+
- No external API keys. Legend runs entirely on your infrastructure.

### Install

```bash
pip install legend
legend download-models
```

The `download-models` command fetches the spaCy model weights to `~/.legend/models/`. Run this once before first use. If you skip it, Legend downloads the model automatically on first run.

For custom model locations (containerized or edge deployments), set `LEGEND_MODEL_PATH` before running:

```bash
LEGEND_MODEL_PATH=/mnt/storage/legend 
legend download-models
```

### Use

```python
import asyncio
from legend import DetectionPipeline, ReplacementEngine, PseudonymContext

pipeline = DetectionPipeline(entities=["PERSON", "EMAIL_ADDRESS", "US_SSN"])
engine = ReplacementEngine()

async def run():
    async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:

        # Boundary A: user prompt entering the agent
        prompt = await ctx.sanitize_prompt(
            "Process a refund for John Smith (john.smith@acme.com), SSN 123-45-6789."
        )
        # "Process a refund for Michael Torres (fake3847@example.com), SSN 987-65-4320."

        # Boundary B: tool call arguments leaving toward an external API
        args = await ctx.sanitize_tool_args({"email": "john.smith@acme.com", "amount": 150})
        # {"email": "fake3847@example.com", "amount": 150}

        # Boundary C: tool results entering the agent context
        result = await ctx.sanitize_tool_result(tool_response)

        # Boundary D: real values restored in the final response
        response = await ctx.revert(agent_response)

asyncio.run(run())
```

`DetectionPipeline` and `ReplacementEngine` are initialized once and reused across sessions. A fresh session-scoped entity map is created for each `PseudonymContext` block and destroyed on exit.

---

## The Four Boundaries

Agent pipelines expose PII at four distinct points. Legend intercepts all of them.

**A — User prompt in.** PII in the user's message is replaced before it enters the agent's context window.

**B — Tool call arguments out.** PII that the agent constructs into tool call arguments is replaced before it reaches an external API, database, or service.

**C — Tool result in.** PII returned by a tool (fetched from a database, retrieved from an external system) is replaced before it enters the agent's context.

**D — Response out.** Pseudonyms are reverted to their original values in the final response before the user sees it.

Most tools protect only the prompt. Boundary B and Boundary C are where agent-specific leakage happens and where Legend is different.

---

## Properties

**Reversible.** Real values are restored exactly at Boundary D. The agent's response reads naturally, with original names, addresses, and identifiers intact.

**Realistic substitutes.** A name becomes a plausible name. An IBAN becomes a valid-format IBAN with the correct country code and check digit. Agents reason correctly over pseudonymized data because the substitutes are semantically coherent.

**Session-scoped.** The entity map lives only for the duration of a `PseudonymContext` block. No state persists between sessions. No database required.

**On-premise.** Detection runs via YARA rules and a local spaCy model. Nothing leaves your infrastructure during processing.

**Framework-agnostic.** Works with LangGraph, LangChain, CrewAI, or any agent framework. `PseudonymContext` wraps your existing agent calls with no framework-specific integration required.

---

## Custom Rules

Legend ships with detection rules covering the full [Presidio entity list](https://microsoft.github.io/presidio/supported_entities/). For domain-specific PII formats (internal account IDs, regional document numbers, custom identifiers), generate additional YARA rules with [yaramint](https://github.com/deconvolute-labs/yaramint) and pass the rules directory to `DetectionPipeline`.

---

## Roadmap

- **Framework adapters.** One-line integration for LangChain, LangGraph, and CrewAI via `wrap_langchain_tools()` and equivalents. No tool-level boilerplate.
- **Transparent proxy.** An OpenAI-compatible HTTP proxy that intercepts MCP tool calls at the protocol level. Works with any agent framework, zero code changes required.
- **OpenTelemetry integration.** Optional `legend[otel]` extra that routes pseudonymized observability events into any OTel-compatible backend. Each session maps to a trace, each boundary to a child span.

---

## References

Xiao, Yunze, Wenkai Li, Xiaoyuan Wu, Ningshan Ma, Yueqi Song, and Weihao Xuan. *Say Something Else: Rethinking Contextual Privacy as Information Sufficiency.* arXiv:2604.06409. Preprint, arXiv, April 7, 2026. <https://doi.org/10.48550/arXiv.2604.06409>.

Serenari, Jayden, and Stephen Lee. *Semantically-Aware LLM Agent to Enhance Privacy in Conversational AI Services.* arXiv:2510.27016. Preprint, arXiv, October 30, 2025. <https://doi.org/10.48550/arXiv.2510.27016>.

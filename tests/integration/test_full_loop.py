from typing import Any, cast

import pytest

from legend import DetectionPipeline, PseudonymContext, ReplacementEngine

TEST_CASES = [
    {
        "input": "Call John Smith at john.smith@acme.com or 555-867-5309.",
        "entities": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
        "pii": ["John Smith", "john.smith@acme.com", "555-867-5309"],
    },
    {
        "input": "SSN 123-45-6789 belongs to Jane Doe.",
        "entities": ["US_SSN", "PERSON"],
        "pii": ["123-45-6789", "Jane Doe"],
    },
]


pipeline = DetectionPipeline(
    entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]
)
engine = ReplacementEngine()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TEST_CASES)
async def test_boundary_a_removes_pii(case: dict[str, Any]) -> None:
    async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:
        sanitized = await ctx.sanitize_prompt(case["input"])
        for pii_value in case["pii"]:
            assert pii_value not in sanitized


@pytest.mark.asyncio
@pytest.mark.parametrize("case", TEST_CASES)
async def test_boundary_d_restores_pii(case: dict[str, Any]) -> None:
    async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:
        sanitized = await ctx.sanitize_prompt(case["input"])
        restored = await ctx.revert(sanitized)
        for pii_value in case["pii"]:
            assert pii_value.lower() in restored.lower()


@pytest.mark.asyncio
async def test_sanitize_prompt_return_spans_false_returns_str() -> None:
    case = TEST_CASES[0]
    input_text = cast(str, case["input"])
    async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:
        result = await ctx.sanitize_prompt(input_text)
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_sanitize_prompt_return_spans_true_returns_tuple_with_spans() -> None:
    case = TEST_CASES[0]
    input_text = cast(str, case["input"])
    pii_values = cast(list[str], case["pii"])
    async with PseudonymContext(pipeline=pipeline, engine=engine) as ctx:
        result = await ctx.sanitize_prompt(input_text, return_spans=True)
        assert isinstance(result, tuple)
        sanitized, spans = result
        assert isinstance(sanitized, str)
        assert len(spans) > 0
        for pii_value in pii_values:
            assert pii_value not in sanitized
        for span in spans:
            assert input_text[span.start : span.end] in pii_values

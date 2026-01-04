"""
Test runner for AI-driven end-to-end testing
Allows AI to test the entire pipeline without human interaction
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from src.core.events import InMemoryEventObserver, EventType
from src.core.pipeline import VoicePipeline


@dataclass
class TestResult:
    """Result from running a test scenario"""

    success: bool
    scenario_name: str
    transcript: str | None = None
    response_text: str | None = None
    total_latency_ms: float | None = None
    latency_breakdown: dict[str, float] | None = None
    events: list[Any] | None = None
    errors: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for easy inspection"""
        return {
            "success": self.success,
            "scenario_name": self.scenario_name,
            "transcript": self.transcript,
            "response_text": self.response_text,
            "total_latency_ms": self.total_latency_ms,
            "latency_breakdown": self.latency_breakdown,
            "event_count": len(self.events) if self.events else 0,
            "errors": self.errors or [],
        }

    def print_summary(self) -> None:
        """Print human-readable summary"""
        status = "✓ PASS" if self.success else "✗ FAIL"
        print(f"\n{status}: {self.scenario_name}")

        if self.transcript:
            print(f"  Transcript: {self.transcript}")

        if self.response_text:
            print(f"  Response: {self.response_text[:100]}...")

        if self.total_latency_ms:
            print(f"  Total Latency: {self.total_latency_ms:.1f}ms")

        if self.latency_breakdown:
            print("  Breakdown:")
            for stage, latency in self.latency_breakdown.items():
                print(f"    {stage}: {latency:.1f}ms")

        if self.errors:
            print("  Errors:")
            for error in self.errors:
                print(f"    - {error}")


class TestRunner:
    """
    Test runner for AI-driven end-to-end testing

    This allows AI to:
    1. Run full pipeline with mock components
    2. Verify behavior via event logs
    3. Check latency requirements
    4. Validate error handling
    """

    def __init__(self):
        self.results: list[TestResult] = []

    async def run_text_scenario(
        self,
        pipeline: VoicePipeline,
        scenario_name: str,
        input_text: str,
        expected_response_contains: str | None = None,
        max_latency_ms: float | None = None,
    ) -> TestResult:
        """
        Run a text-based test scenario

        Args:
            pipeline: VoicePipeline instance with mock providers
            scenario_name: Name of the test
            input_text: Text query to process
            expected_response_contains: String that should appear in response
            max_latency_ms: Maximum allowed latency

        Returns:
            TestResult with success/failure and diagnostics
        """
        observer = pipeline.get_observer()
        observer.clear()

        errors = []

        try:
            # Run the pipeline
            await pipeline.process_text(input_text)

            # Extract results from observer
            events = observer.get_events()
            latency_breakdown = observer.get_latency_breakdown()

            total_latency = latency_breakdown.get("pipeline_total")

            # Get response text from TTS events
            tts_events = [e for e in events if e.event_type == EventType.TTS_START]
            response_text = " ".join(e.data.get("text", "") for e in tts_events)

            # Validation
            success = True

            # Check if response contains expected text
            if expected_response_contains:
                if expected_response_contains.lower() not in response_text.lower():
                    errors.append(
                        f"Response missing expected text: '{expected_response_contains}'"
                    )
                    success = False

            # Check latency requirement
            if max_latency_ms and total_latency:
                if total_latency > max_latency_ms:
                    errors.append(
                        f"Latency exceeded: {total_latency:.1f}ms > {max_latency_ms}ms"
                    )
                    success = False

            # Check for errors in event log
            error_events = [
                e
                for e in events
                if e.event_type
                in [EventType.PIPELINE_ERROR, EventType.LLM_ERROR, EventType.TTS_ERROR]
            ]
            if error_events:
                for event in error_events:
                    errors.append(f"Pipeline error: {event.data.get('error')}")
                success = False

            result = TestResult(
                success=success,
                scenario_name=scenario_name,
                transcript=input_text,
                response_text=response_text,
                total_latency_ms=total_latency,
                latency_breakdown=latency_breakdown,
                events=events,
                errors=errors if errors else None,
            )

            self.results.append(result)
            return result

        except Exception as e:
            result = TestResult(
                success=False,
                scenario_name=scenario_name,
                transcript=input_text,
                errors=[f"Exception: {type(e).__name__}: {str(e)}"],
            )
            self.results.append(result)
            return result

    async def run_multiple_scenarios(
        self, pipeline: VoicePipeline, scenarios: list[dict[str, Any]]
    ) -> list[TestResult]:
        """
        Run multiple test scenarios

        Args:
            pipeline: VoicePipeline with mock providers
            scenarios: List of scenario configs

        Returns:
            List of TestResults
        """
        results = []

        for scenario in scenarios:
            result = await self.run_text_scenario(pipeline, **scenario)
            results.append(result)

        return results

    def print_summary(self) -> None:
        """Print summary of all test results"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed

        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        print("=" * 60)

        for result in self.results:
            result.print_summary()

        print("\n" + "=" * 60)

    def all_passed(self) -> bool:
        """Check if all tests passed"""
        return all(r.success for r in self.results)

"""Performance testing script for GitHub PR Rules Analyzer."""

import argparse
import asyncio
import secrets
import statistics
import time
from dataclasses import dataclass
from typing import Any

import aiofiles
import aiohttp


@dataclass
class TestResult:
    """Test result data class."""

    endpoint: str
    method: str
    status_code: int
    response_time: float
    response_size: int
    error: str = None


class PerformanceTester:
    """Performance testing class."""

    def __init__(self, base_url: str, max_concurrent: int = 10) -> None:
        """Initialize the PerformanceTester.

        Args:
        ----
            base_url: The base URL for the API endpoints
            max_concurrent: Maximum number of concurrent requests

        """
        self.base_url = base_url.rstrip("/")
        self.max_concurrent = max_concurrent
        self.results: list[TestResult] = []

    async def test_endpoint(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> TestResult:
        """Test a single endpoint."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            if method.upper() == "GET":
                async with session.get(url) as response:
                    response_time = time.time() - start_time
                    response_size = len(await response.read())
                    return TestResult(endpoint, method, response.status, response_time, response_size)
            elif method.upper() == "POST":
                async with session.post(url, json=data) as response:
                    response_time = time.time() - start_time
                    response_size = len(await response.read())
                    return TestResult(endpoint, method, response.status, response_time, response_size)
            else:
                return TestResult(endpoint, method, 0, 0, 0, f"Unsupported method: {method}")
        except aiohttp.ClientError as e:
            return TestResult(endpoint, method, 0, 0, 0, f"Client error: {e!s}")
        except TimeoutError as e:
            return TestResult(endpoint, method, 0, 0, 0, f"Timeout error: {e!s}")
        except aiohttp.ClientResponseError as e:
            return TestResult(endpoint, method, e.status, 0, 0, f"Response error: {e!s}")
        except aiohttp.ClientConnectorError as e:
            return TestResult(endpoint, method, 0, 0, 0, f"Connection error: {e!s}")

    async def run_concurrent_test(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
        requests_count: int = 100,
    ) -> list[TestResult]:
        """Run concurrent requests to an endpoint."""
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for _ in range(requests_count):
                task = self.test_endpoint(session, endpoint, method, data)
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            self.results.extend(results)
            return results

    async def run_stress_test(self, endpoints: list[dict], total_requests: int = 1000) -> list[TestResult]:
        """Run stress test across multiple endpoints."""
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            remaining_requests = total_requests

            while remaining_requests > 0:
                # Randomly select an endpoint
                endpoint_config = secrets.choice(endpoints)
                endpoint = endpoint_config["endpoint"]
                method = endpoint_config.get("method", "GET")
                data = endpoint_config.get("data")

                task = self.test_endpoint(session, endpoint, method, data)
                tasks.append(task)
                remaining_requests -= 1

            results = await asyncio.gather(*tasks)
            self.results.extend(results)
            return results

    def analyze_results(self) -> dict[str, Any]:
        """Analyze test results."""
        if not self.results:
            return {}

        # Group results by endpoint
        endpoint_results = {}
        for result in self.results:
            if result.endpoint not in endpoint_results:
                endpoint_results[result.endpoint] = []
            endpoint_results[result.endpoint].append(result)

        analysis = {}

        for endpoint, results in endpoint_results.items():
            # Filter out errors
            successful_results = [r for r in results if r.status_code == 200 and r.error is None]
            failed_results = [r for r in results if r.status_code != 200 or r.error is not None]

            if successful_results:
                response_times = [r.response_time for r in successful_results]
                analysis[endpoint] = {
                    "total_requests": len(results),
                    "successful_requests": len(successful_results),
                    "failed_requests": len(failed_results),
                    "success_rate": len(successful_results) / len(results) * 100,
                    "avg_response_time": statistics.mean(response_times),
                    "min_response_time": min(response_times),
                    "max_response_time": max(response_times),
                    "median_response_time": statistics.median(response_times),
                    "p95_response_time": statistics.quantiles(response_times, n=20)[18],  # 95th percentile
                    "p99_response_time": statistics.quantiles(response_times, n=100)[98],  # 99th percentile
                    "avg_response_size": statistics.mean([r.response_size for r in successful_results]),
                    "requests_per_second": len(successful_results) / sum(response_times),
                }
            else:
                analysis[endpoint] = {
                    "total_requests": len(results),
                    "successful_requests": 0,
                    "failed_requests": len(failed_results),
                    "success_rate": 0,
                    "avg_response_time": 0,
                    "min_response_time": 0,
                    "max_response_time": 0,
                    "median_response_time": 0,
                    "p95_response_time": 0,
                    "p99_response_time": 0,
                    "avg_response_size": 0,
                    "requests_per_second": 0,
                }

        return analysis

    def generate_report(self, analysis: dict[str, Any]) -> str:
        """Generate performance report."""
        report = []
        report.append("GitHub PR Rules Analyzer - Performance Test Report")
        report.append("=" * 60)
        report.append(f"Total Requests: {len(self.results)}")
        report.append(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        for endpoint, metrics in analysis.items():
            report.append(f"Endpoint: {endpoint}")
            report.append(f"  Method: {metrics.get('method', 'GET')}")
            report.append(f"  Total Requests: {metrics['total_requests']}")
            report.append(f"  Successful Requests: {metrics['successful_requests']}")
            report.append(f"  Failed Requests: {metrics['failed_requests']}")
            report.append(f"  Success Rate: {metrics['success_rate']:.2f}%")
            report.append(f"  Avg Response Time: {metrics['avg_response_time']:.3f}s")
            report.append(f"  Min Response Time: {metrics['min_response_time']:.3f}s")
            report.append(f"  Max Response Time: {metrics['max_response_time']:.3f}s")
            report.append(f"  Median Response Time: {metrics['median_response_time']:.3f}s")
            report.append(f"  95th Percentile: {metrics['p95_response_time']:.3f}s")
            report.append(f"  99th Percentile: {metrics['p99_response_time']:.3f}s")
            report.append(f"  Avg Response Size: {metrics['avg_response_size']:.2f} bytes")
            report.append(f"  Requests/sec: {metrics['requests_per_second']:.2f}")
            report.append("")

        # Overall statistics
        all_response_times = [r.response_time for r in self.results if r.status_code == 200 and r.error is None]
        if all_response_times:
            report.append("Overall Statistics:")
            report.append(f"  Total Successful Requests: {len(all_response_times)}")
            report.append(f"  Overall Avg Response Time: {statistics.mean(all_response_times):.3f}s")
            report.append(f"  Overall Success Rate: {len(all_response_times) / len(self.results) * 100:.2f}%")

        return "\n".join(report)


async def main() -> None:
    """Run main function."""
    parser = argparse.ArgumentParser(description="Performance test GitHub PR Rules Analyzer")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the application")
    parser.add_argument("--concurrent", type=int, default=10, help="Maximum concurrent requests")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests per endpoint")
    parser.add_argument("--stress", action="store_true", help="Run stress test")
    parser.add_argument("--output", help="Output file for results")

    args = parser.parse_args()

    # Define test endpoints
    endpoints = [
        {"endpoint": "/api/v1/health", "method": "GET"},
        {"endpoint": "/api/v1/dashboard", "method": "GET"},
        {"endpoint": "/api/v1/repositories", "method": "GET"},
        {"endpoint": "/api/v1/rules", "method": "GET"},
        {"endpoint": "/api/v1/rules/categories", "method": "GET"},
        {"endpoint": "/api/v1/rules/severities", "method": "GET"},
        {"endpoint": "/api/v1/rules/search", "method": "GET", "data": {"query": "test"}},
        {"endpoint": "/api/v1/rules/extract", "method": "POST", "data": [1]},
    ]

    tester = PerformanceTester(args.url, args.concurrent)

    if args.stress:
        await tester.run_stress_test(endpoints, args.requests)
    else:
        for endpoint_config in endpoints:
            await tester.run_concurrent_test(
                endpoint_config["endpoint"],
                endpoint_config.get("method", "GET"),
                endpoint_config.get("data"),
                args.requests,
            )

    # Analyze results
    analysis = tester.analyze_results()

    # Generate report
    report = tester.generate_report(analysis)

    # Save results if output file specified
    if args.output:
        async with aiofiles.open(args.output, "w") as f:
            await f.write(report)


if __name__ == "__main__":
    asyncio.run(main())

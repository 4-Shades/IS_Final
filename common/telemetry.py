"""Opt-in OpenTelemetry metrics, pushed over OTLP (e.g. to Grafana Cloud)."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import metrics

logger = logging.getLogger(__name__)
_provider_installed = False


def instrument_app(app: FastAPI, service_name: str) -> None:
    # Push, not scrape: ECS tasks scale to zero nightly, leaving nothing stable to scrape.
    # The exporter reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS itself.
    global _provider_installed
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    if not _provider_installed:
        resource = Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME") or f"travel-{service_name}",
            "service.namespace": "travel-planner",
        })
        reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
        _provider_installed = True
        logger.info("otel_metrics_enabled service=%s", service_name)

    FastAPIInstrumentor.instrument_app(app, meter_provider=metrics.get_meter_provider())

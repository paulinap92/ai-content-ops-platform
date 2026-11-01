from __future__ import annotations

from typing import Any

from canarias_site.models.design_db import (
    CalendarEvent,
    ClimateObservation,
    LiveSnapshot,
    NewsItem,
    SeismicEvent,
    StatisticalSnapshot,
    VolcanicReport,
)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def live_snapshot_to_payload(
    row: LiveSnapshot,
) -> dict[str, Any]:
    return dict(row.payload or {})


def news_item_to_payload(
    row: NewsItem,
) -> dict[str, Any]:
    return dict(row.payload or {})


def calendar_event_to_payload(
    row: CalendarEvent,
) -> dict[str, Any]:
    return dict(row.payload or {})


def statistical_snapshot_to_payload(
    row: StatisticalSnapshot,
) -> dict[str, Any]:
    return dict(row.payload or {})


def climate_observation_to_payload(
    row: ClimateObservation,
) -> dict[str, Any]:
    payload = dict(row.payload or {})
    payload["observed_at"] = _iso(row.observed_at)
    payload["point_id"] = row.point_id
    payload["latitude"] = row.latitude
    payload["longitude"] = row.longitude
    if row.source is not None:
        payload["source"] = row.source
    return payload


def seismic_event_to_payload(
    row: SeismicEvent,
) -> dict[str, Any]:
    payload = dict(row.payload or {})
    payload.update(
        {
            "event_id": row.event_id,
            "occurred_at": _iso(row.occurred_at),
            "latitude": row.latitude,
            "longitude": row.longitude,
            "depth_km": row.depth_km,
            "magnitude": row.magnitude,
            "magnitude_type": row.magnitude_type,
            "location": row.location,
            "source": row.source,
            "source_url": row.source_url,
        }
    )
    return payload


def volcanic_report_to_payload(
    row: VolcanicReport,
) -> dict[str, Any]:
    payload = dict(row.payload or {})
    payload.update(
        {
            "report_id": row.report_id,
            "period": row.period,
            "title": row.title,
            "summary": row.summary,
            "earthquakes_total": row.earthquakes_total,
            "max_magnitude": row.max_magnitude,
            "significant_deformation_detected":
                row.significant_deformation_detected,
            "source": row.source,
            "source_url": row.source_url,
            "first_seen_at": _iso(row.first_seen_at),
            "last_seen_at": _iso(row.last_seen_at),
        }
    )
    return payload


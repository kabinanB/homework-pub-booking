"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolError, ToolRegistry, ToolResult, _RegisteredTool

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    # TODO 1a: load venues.json. Raise ToolError(SA_TOOL_DEPENDENCY_MISSING)
    #          if the file is absent.
    from starter.edinburgh_research.integrity import record_tool_call

    venues_file = _SAMPLE_DATA / "venues.json"
    if not venues_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING")

    venues = json.loads(venues_file.read_text(encoding="utf-8"))

    # Filter by all criteria
    results = [
        v
        for v in venues
        if v["open_now"]
        and near.lower() in v["area"].lower()
        and v["seats_available_evening"] >= party_size
        and (v["hire_fee_gbp"] + v["min_spend_gbp"]) <= budget_max_gbp
    ]

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }

    summary = f"venue_search({near!r}, party={party_size}): {len(results)} result(s)"

    record_tool_call(
        "venue_search",
        {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp},
        output,
    )

    return ToolResult(output=output, summary=summary, success=True)


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    from starter.edinburgh_research.integrity import record_tool_call

    weather_file = _SAMPLE_DATA / "weather.json"
    if not weather_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING")

    weather_data = json.loads(weather_file.read_text(encoding="utf-8"))

    city_lower = city.lower()
    if city_lower not in weather_data:
        output = {
            "error": "SA_TOOL_INVALID_INPUT",
            "city": city,
            "date": date,
            "message": f"City {city!r} not found in weather data",
        }
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        return ToolResult(
            output=output,
            summary=f"get_weather({city!r}, {date}): error - city not found",
            success=False,
        )

    if date not in weather_data[city_lower]:
        output = {
            "error": "SA_TOOL_INVALID_INPUT",
            "city": city,
            "date": date,
            "message": f"Date {date!r} not found for city {city!r}",
        }
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        return ToolResult(
            output=output,
            summary=f"get_weather({city!r}, {date}): error - date not found",
            success=False,
        )

    weather_info = weather_data[city_lower][date]
    output = {
        "city": city,
        "date": date,
        **weather_info,
    }

    condition = weather_info.get("condition", "unknown")
    temp = weather_info.get("temperature_c", "N/A")
    summary = f"get_weather({city!r}, {date}): {condition}, {temp}C"

    record_tool_call("get_weather", {"city": city, "date": date}, output)

    return ToolResult(output=output, summary=summary, success=True)


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    from starter.edinburgh_research.integrity import record_tool_call

    # Load required data files
    catering_file = _SAMPLE_DATA / "catering.json"
    venues_file = _SAMPLE_DATA / "venues.json"

    if not catering_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING")
    if not venues_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING")

    catering_data = json.loads(catering_file.read_text(encoding="utf-8"))
    venues = json.loads(venues_file.read_text(encoding="utf-8"))

    # Find the venue
    venue = next((v for v in venues if v["id"] == venue_id), None)
    if not venue:
        output = {
            "error": "SA_TOOL_INVALID_INPUT",
            "venue_id": venue_id,
            "message": f"Venue {venue_id!r} not found",
        }
        record_tool_call(
            "calculate_cost",
            {
                "venue_id": venue_id,
                "party_size": party_size,
                "duration_hours": duration_hours,
                "catering_tier": catering_tier,
            },
            output,
        )
        return ToolResult(
            output=output,
            summary=f"calculate_cost({venue_id}, {party_size}): error - venue not found",
            success=False,
        )

    # Check catering tier exists
    base_rates = catering_data.get("base_rates_gbp_per_head", {})
    if catering_tier not in base_rates:
        output = {
            "error": "SA_TOOL_INVALID_INPUT",
            "catering_tier": catering_tier,
            "message": f"Catering tier {catering_tier!r} not found",
        }
        record_tool_call(
            "calculate_cost",
            {
                "venue_id": venue_id,
                "party_size": party_size,
                "duration_hours": duration_hours,
                "catering_tier": catering_tier,
            },
            output,
        )
        return ToolResult(
            output=output,
            summary=f"calculate_cost({venue_id}, {party_size}): error - invalid catering tier",
            success=False,
        )

    # Perform calculations
    base_per_head = base_rates[catering_tier]
    venue_mult = catering_data.get("venue_modifiers", {}).get(venue_id, 1.0)
    service_charge_percent = catering_data.get("service_charge_percent", 10)

    # Subtotal: base_per_head * venue_mult * party_size * max(1, duration_hours)
    subtotal = int(base_per_head * venue_mult * party_size * max(1, duration_hours))

    # Service charge
    service = int(subtotal * service_charge_percent / 100)

    # Total includes hire fee and min spend from venue
    total = subtotal + service + venue["hire_fee_gbp"] + venue["min_spend_gbp"]

    # Calculate deposit based on policy thresholds
    deposit_required = 0
    if total < 300:
        # no_deposit_required
        deposit_required = 0
    elif total <= 1000:
        # deposit_20_percent
        deposit_required = int(total * 0.20)
    else:
        # deposit_30_percent
        deposit_required = int(total * 0.30)

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit_required,
    }

    summary = (
        f"calculate_cost({venue_id}, {party_size}): total £{total}, deposit £{deposit_required}"
    )

    record_tool_call(
        "calculate_cost",
        {
            "venue_id": venue_id,
            "party_size": party_size,
            "duration_hours": duration_hours,
            "catering_tier": catering_tier,
        },
        output,
    )

    return ToolResult(output=output, summary=summary, success=True)


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets). Tag every key fact with data-testid="<n>" so the integrity check can parse it.

    Write a formatted HTML flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    from starter.edinburgh_research.integrity import record_tool_call

    # Create workspace directory if it doesn't exist
    workspace_dir = session.workspace_dir
    workspace_dir.mkdir(parents=True, exist_ok=True)

    flyer_path = workspace_dir / "flyer.html"

    # Extract event details with defaults
    venue_name = event_details.get("venue_name", "Venue")
    venue_address = event_details.get("venue_address", "Address not available")
    date = event_details.get("date", "Date TBD")
    time = event_details.get("time", "Time TBD")
    party_size = event_details.get("party_size", "N/A")
    condition = event_details.get("condition", "Unknown")
    temperature_c = event_details.get("temperature_c", "N/A")
    total_gbp = event_details.get("total_gbp", "N/A")
    deposit_required_gbp = event_details.get("deposit_required_gbp", "N/A")

    # Generate HTML with inline CSS and data-testid attributes
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Event Flyer</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .flyer {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        .section {{
            margin: 20px 0;
        }}
        .section-title {{
            font-weight: bold;
            color: #007bff;
            margin-top: 15px;
            margin-bottom: 10px;
        }}
        .fact {{
            margin: 8px 0;
            padding: 5px 0;
        }}
        .label {{
            font-weight: bold;
            color: #555;
        }}
    </style>
</head>
<body>
    <div class="flyer">
        <h1 data-testid="title">Event Flyer</h1>
        <div class="section">
            <div class="section-title">Event Details</div>
            <div class="fact">
                <span class="label">Venue:</span> <span data-testid="venue_name">{venue_name}</span>
            </div>
            <div class="fact">
                <span class="label">Address:</span> <span data-testid="venue_address">{venue_address}</span>
            </div>
            <div class="fact">
                <span class="label">Date:</span> <span data-testid="date">{date}</span>
            </div>
            <div class="fact">
                <span class="label">Time:</span> <span data-testid="time">{time}</span>
            </div>
            <div class="fact">
                <span class="label">Party Size:</span> <span data-testid="party_size">{party_size}</span> people
            </div>
        </div>
        <div class="section">
            <div class="section-title">Weather Forecast</div>
            <div class="fact">
                <span class="label">Condition:</span> <span data-testid="condition">{condition}</span>
            </div>
            <div class="fact">
                <span class="label">Temperature:</span> <span data-testid="temperature_c">{temperature_c}</span>°C
            </div>
        </div>
        <div class="section">
            <div class="section-title">Cost Breakdown</div>
            <div class="fact">
                <span class="label">Total Cost:</span> £<span data-testid="total_gbp">{total_gbp}</span>
            </div>
            <div class="fact">
                <span class="label">Deposit Required:</span> £<span data-testid="deposit_required_gbp">{deposit_required_gbp}</span>
            </div>
        </div>
    </div>
</body>
</html>"""

    # Write to file
    bytes_written = flyer_path.write_text(html_content, encoding="utf-8")

    output = {
        "path": str(
            flyer_path.relative_to(workspace_dir.parent)
            if workspace_dir.parent in flyer_path.parents
            else flyer_path
        ),
        "bytes_written": bytes_written,
    }

    summary = f"generate_flyer: wrote {flyer_path.name} ({bytes_written} chars)"

    record_tool_call("generate_flyer", {"event_details": event_details}, output)

    return ToolResult(output=output, summary=summary, success=True)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]

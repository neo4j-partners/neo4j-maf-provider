"""Sample demos for Neo4j MAF Provider capabilities."""

from samples.agent_memory import demo_agent_memory
from samples.aircraft_flight_delays import demo_aircraft_flight_delays
from samples.aircraft_maintenance_search import demo_aircraft_maintenance_search
from samples.component_health import demo_component_health
from samples.context_provider_basic import demo_context_provider_basic
from samples.context_provider_graph_enriched import demo_context_provider_graph_enriched
from samples.context_provider_vector import demo_context_provider_vector
from samples.semantic_search import demo_semantic_search

__all__ = [
    "demo_agent_memory",
    "demo_aircraft_flight_delays",
    "demo_aircraft_maintenance_search",
    "demo_component_health",
    "demo_context_provider_basic",
    "demo_context_provider_graph_enriched",
    "demo_context_provider_vector",
    "demo_semantic_search",
]

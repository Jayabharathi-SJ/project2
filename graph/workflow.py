from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    cfo_recommendation_node,
    financial_analysis_node,
    legal_validation_node,
    research_agent_node,
    validate_input_node,
)
from graph.state import CFOState


def route_after_input_validation(state: CFOState) -> str:
    if state.get("validation_passed") is True:
        return "research_agent"

    return "end"


def route_after_legal_validation(state: CFOState) -> str:
    legal_validation = state.get("legal_validation", {})

    if legal_validation.get("passed") is True:
        return "financial_analysis"

    return "end"


def build_cfo_graph(checkpointer=None):
    workflow = StateGraph(CFOState)

    workflow.add_node(
        "validate_input",
        validate_input_node,
    )

    workflow.add_node(
        "research_agent",
        research_agent_node,
    )

    workflow.add_node(
        "legal_validation",
        legal_validation_node,
    )

    workflow.add_node(
        "financial_analysis",
        financial_analysis_node,
    )

    workflow.add_node(
        "cfo_recommendation",
        cfo_recommendation_node,
    )

    workflow.add_edge(
        START,
        "validate_input",
    )

    workflow.add_conditional_edges(
        "validate_input",
        route_after_input_validation,
        {
            "research_agent": "research_agent",
            "end": END,
        },
    )

    workflow.add_edge(
        "research_agent",
        "legal_validation",
    )

    workflow.add_conditional_edges(
        "legal_validation",
        route_after_legal_validation,
        {
            "financial_analysis": "financial_analysis",
            "end": END,
        },
    )

    workflow.add_edge(
        "financial_analysis",
        "cfo_recommendation",
    )

    workflow.add_edge(
        "cfo_recommendation",
        END,
    )

    return workflow.compile(
        checkpointer=checkpointer,
    )
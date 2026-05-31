from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from .state import ResearchState
from .agents.planner import planner_node
from .agents.researcher import researcher_node
from .agents.critic import critic_node
from .agents.synthesizer import synthesizer_node
from .disagreement import disagreement_node


def route_to_researchers(state: ResearchState):
    # One Send per claim → parallel researchers, decided at runtime.
    return [Send("researcher", {"drug": state["drug"], "claim": c}) for c in state["claims"]]


def build_graph():
    g = StateGraph(ResearchState)
    for name, fn in [("planner", planner_node), ("researcher", researcher_node),
                     ("critic", critic_node), ("disagreement", disagreement_node),
                     ("synthesizer", synthesizer_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "planner")
    g.add_conditional_edges("planner", route_to_researchers, ["researcher"])
    g.add_edge("researcher", "critic")        # critic waits for BOTH researchers (fan-in)
    g.add_edge("critic", "disagreement")
    g.add_edge("disagreement", "synthesizer")
    g.add_edge("synthesizer", END)
    return g.compile()

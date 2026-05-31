
import time
from dataclasses import dataclass

import streamlit as st


st.set_page_config(
    page_title="IND Pre-Review AI",
    page_icon="🧪",
    layout="wide",
)


st.markdown(
    """
    <style>
    .main {
        background-color: #f8fafc;
    }

    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1280px;
    }

    h1, h2, h3 {
        letter-spacing: -0.03em;
    }

    .hero-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 28px;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
    }

    .soft-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 16px;
    }

    .muted {
        color: #64748b;
        font-size: 0.95rem;
    }

    .small-muted {
        color: #64748b;
        font-size: 0.82rem;
    }

    .risk-low {
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
    }

    .risk-medium {
        background: #fffbeb;
        color: #b45309;
        border: 1px solid #fde68a;
    }

    .risk-high {
        background: #fff1f2;
        color: #be123c;
        border: 1px solid #fecdd3;
    }

    .risk-medhigh {
        background: #fff7ed;
        color: #c2410c;
        border: 1px solid #fed7aa;
    }

    .risk-pending {
        background: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
    }

    .risk-badge {
        display: inline-block;
        border-radius: 999px;
        padding: 5px 11px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-left: 6px;
        white-space: nowrap;
    }

    .step-pill {
        display: inline-block;
        border-radius: 999px;
        border: 1px solid #cbd5e1;
        background: #ffffff;
        color: #475569;
        padding: 8px 14px;
        font-size: 0.88rem;
        margin-right: 8px;
        margin-bottom: 8px;
    }

    .step-active {
        background: #0f172a;
        color: #ffffff;
        border-color: #0f172a;
    }

    .report-header {
        background: #0f172a;
        color: white;
        border-radius: 24px;
        padding: 24px;
        margin-bottom: 18px;
    }

    .progress-track {
        width: 100%;
        height: 9px;
        background: #334155;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 18px;
    }

    .progress-fill {
        height: 100%;
        width: 74%;
        background: #ffffff;
        border-radius: 999px;
    }

    .file-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 12px 14px;
        margin-bottom: 10px;
        background: #ffffff;
    }

    .agent-subgroup {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 10px 12px;
        margin-top: 8px;
        font-size: 0.87rem;
    }

    .warning-box {
        background: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
        border-radius: 18px;
        padding: 14px 16px;
        font-size: 0.9rem;
        margin-top: 12px;
    }

    div[data-testid="stFileUploader"] section {
        border-radius: 22px;
        border: 1px dashed #cbd5e1;
        background: #ffffff;
    }

    div.stButton > button {
        border-radius: 14px;
        font-weight: 700;
        height: 2.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@dataclass
class AgentFinding:
    name: str
    risk: str
    finding: str
    subgroups: list[str] | None = None


AGENT_FINDINGS = [
    AgentFinding(
        name="Regulatory Compliance Agent",
        risk="Medium",
        finding=(
            "IND package appears directionally complete, but FDA forms and the "
            "investigator brochure risk summary need review."
        ),
    ),
    AgentFinding(
        name="Safety / Efficacy Evaluation",
        risk="High",
        finding=(
            "Integrated review suggests possible liver-safety monitoring gaps "
            "across clinical, CMC, and nonclinical evidence."
        ),
        subgroups=[
            "Clinical Protocol: study design, endpoints, population",
            "CMC: manufacturing, stability, controls",
            "Nonclinical: toxicology, pharmacology",
        ],
    ),
    AgentFinding(
        name="Validation Agent",
        risk="High",
        finding=(
            "Potential inconsistency found between nonclinical toxicology findings "
            "and the investigator brochure summary."
        ),
    ),
    AgentFinding(
        name="FDA Reviewer / Skeptic Agent",
        risk="Medium-High",
        finding=(
            "FDA may request stronger dose justification, safety stopping rules, "
            "and additional CMC stability support."
        ),
    ),
]


REPORT = {
    "overall_risk": "Medium-High",
    "score": 74,
    "concerns": [
        "Liver safety signal is not fully addressed in the clinical monitoring plan.",
        "CMC stability data may be insufficient for the proposed study duration.",
        "Investigator brochure may understate nonclinical toxicity findings.",
    ],
    "questions": [
        "Provide rationale for dose escalation and stopping criteria.",
        "Explain how the protocol mitigates liver toxicity observed in nonclinical studies.",
        "Submit additional stability data or justify current storage assumptions.",
    ],
    "actions": [
        "Add explicit liver enzyme stopping rules.",
        "Increase early-stage safety monitoring frequency.",
        "Reconcile nonclinical findings across protocol and investigator brochure.",
    ],
}


def risk_class(risk: str) -> str:
    if risk == "Low":
        return "risk-low"
    if risk == "Medium":
        return "risk-medium"
    if risk == "High":
        return "risk-high"
    if risk == "Medium-High":
        return "risk-medhigh"
    return "risk-pending"


def risk_badge(risk: str) -> str:
    return f'<span class="risk-badge {risk_class(risk)}">{risk}</span>'


def render_step_pills(active_step: int) -> None:
    steps = [
        (1, "Upload IND"),
        (2, "Agent Review"),
        (3, "Risk Report"),
    ]

    html = ""
    for number, title in steps:
        active_class = " step-active" if active_step >= number else ""
        html += f'<span class="step-pill{active_class}">{number}. {title}</span>'

    st.markdown(html, unsafe_allow_html=True)


def render_agent_card(agent: AgentFinding, visible: bool) -> None:
    risk = agent.risk if visible else "Pending"
    finding = agent.finding if visible else "Waiting for review..."

    subgroup_html = ""
    if agent.subgroups and visible:
        for subgroup in agent.subgroups:
            subgroup_html += f'<div class="agent-subgroup">• {subgroup}</div>'

    st.markdown(
        f"""
        <div class="soft-card">
            <div style="display:flex; justify-content:space-between; gap:14px;">
                <div>
                    <h4 style="margin:0 0 6px 0;">{agent.name}</h4>
                    <div class="muted">{finding}</div>
                    {subgroup_html}
                </div>
                <div>{risk_badge(risk)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_list(title: str, items: list[str]) -> None:
    body = "".join([f"<li>{item}</li>" for item in items])
    st.markdown(
        f"""
        <div class="soft-card">
            <h4 style="margin-top:0;">{title}</h4>
            <ul class="muted" style="margin-bottom:0; line-height:1.65;">
                {body}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


if "review_complete" not in st.session_state:
    st.session_state.review_complete = False

if "review_running" not in st.session_state:
    st.session_state.review_running = False


top_left, top_right = st.columns([0.72, 0.28], vertical_alignment="center")

with top_left:
    st.markdown(
        """
        <div>
            <div class="small-muted">🧪 IND Pre-Review AI</div>
            <h1 style="margin:0.15rem 0 0.25rem 0;">Regulatory Risk Analysis Workspace</h1>
            <div class="muted">
                Upload IND documents, run independent specialist agents, and generate an initial FDA-facing risk screen.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_right:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reset", use_container_width=True):
            st.session_state.review_complete = False
            st.session_state.review_running = False
            st.rerun()

    with c2:
        report_md = (
            "# IND Risk Analysis Report\n\n"
            f"Overall Risk: {REPORT['overall_risk']}\n"
            f"Risk Score: {REPORT['score']}/100\n\n"
            "## Top FDA Concerns\n"
            + "\n".join(f"- {x}" for x in REPORT["concerns"])
            + "\n\n## Likely FDA Questions\n"
            + "\n".join(f"- {x}" for x in REPORT["questions"])
            + "\n\n## Recommended Next Actions\n"
            + "\n".join(f"- {x}" for x in REPORT["actions"])
        )
        st.download_button(
            label="Export Report",
            data=report_md,
            file_name="ind_risk_analysis_report.md",
            mime="text/markdown",
            use_container_width=True,
            disabled=not st.session_state.review_complete,
        )

st.divider()

step_placeholder = st.empty()

left, right = st.columns([0.43, 0.57], gap="large")

with left:
    st.markdown('<div class="hero-card">', unsafe_allow_html=True)
    st.subheader("Upload IND Documents")
    st.markdown(
        '<div class="muted">Add protocol, investigator brochure, CMC, toxicology, and supporting documents.</div>',
        unsafe_allow_html=True,
    )

    uploaded_files = st.file_uploader(
        "Upload files",
        type=["pdf", "doc", "docx", "txt", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    st.markdown("#### Drug Metadata")
    drug_col1, drug_col2 = st.columns(2)
    with drug_col1:
        st.text_input("Drug name", value="Pulmora")
    with drug_col2:
        st.text_input("Sponsor", value="NovaBio Therapeutics")
    st.text_input("Indication", value="Severe asthma")

    run_disabled = len(uploaded_files) == 0 or st.session_state.review_running
    if st.button("▶ Run IND Pre-Review", type="primary", use_container_width=True, disabled=run_disabled):
        st.session_state.review_running = True
        st.session_state.review_complete = False

        with st.spinner("Lead Orchestrator is assigning independent review tasks..."):
            time.sleep(0.6)

        progress = st.progress(0)
        status = st.empty()

        stages = [
            "Regulatory Compliance Agent reviewing FDA completeness...",
            "Safety / Efficacy Evaluation reviewing Clinical, CMC, and Nonclinical evidence...",
            "Validation Agent checking consistency, precedent, and compliance...",
            "FDA Reviewer / Skeptic Agent generating likely FDA questions...",
            "Lead Orchestrator summarizing findings and generating report...",
        ]

        for i, stage in enumerate(stages, start=1):
            status.markdown(f"**{stage}**")
            progress.progress(i / len(stages))
            time.sleep(0.35)

        st.session_state.review_running = False
        st.session_state.review_complete = True
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="hero-card" style="margin-top:18px;">', unsafe_allow_html=True)
    st.subheader("Uploaded Package")

    if not uploaded_files:
        st.markdown(
            """
            <div class="soft-card">
                <div class="muted">No files uploaded yet. Use sample IND files for your live demo.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        for file in uploaded_files:
            size_kb = max(1, round(file.size / 1024))
            st.markdown(
                f"""
                <div class="file-row">
                    <div>
                        <strong>📄 {file.name}</strong>
                        <div class="small-muted">{size_kb} KB</div>
                    </div>
                    <div style="color:#059669; font-weight:700;">✓</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="hero-card">', unsafe_allow_html=True)
    st.subheader("Independent Agent Review")
    st.markdown(
        """
        <div class="muted">
            Agents work separately. The Lead Orchestrator collects all outputs and produces the final risk report.
        </div>
        """,
        unsafe_allow_html=True,
    )

    visible_agents = st.session_state.review_complete or st.session_state.review_running

    for agent in AGENT_FINDINGS:
        render_agent_card(agent, visible=visible_agents)

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="hero-card" style="margin-top:18px;">', unsafe_allow_html=True)
    st.subheader("Risk Analysis Report")
    st.markdown(
        """
        <div class="muted">
            Generated by the Lead Orchestrator after collecting independent specialist outputs.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.review_complete:
        st.markdown(
            """
            <div class="soft-card" style="text-align:center; padding:34px;">
                <div style="font-size:2rem;">⚠️</div>
                <div class="muted" style="margin-top:8px;">Run the review to generate the report.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="report-header">
                <div style="color:#cbd5e1; font-size:0.9rem;">Overall IND Risk</div>
                <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:8px;">
                    <div style="font-size:2rem; font-weight:800;">{REPORT["overall_risk"]}</div>
                    <div style="font-size:2rem; font-weight:800;">{REPORT["score"]}<span style="font-size:1rem; color:#94a3b8;">/100</span></div>
                </div>
                <div class="progress-track">
                    <div class="progress-fill"></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        render_list("Top FDA Concerns", REPORT["concerns"])
        render_list("Likely FDA Questions", REPORT["questions"])
        render_list("Recommended Next Actions", REPORT["actions"])

        st.markdown(
            """
            <div class="warning-box">
                This prototype provides an initial regulatory risk screen. It does not replace FDA interaction,
                regulatory counsel, or formal submission review.
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


if st.session_state.review_complete:
    current_step = 3
elif st.session_state.review_running:
    current_step = 2
elif len(uploaded_files) > 0:
    current_step = 1
else:
    current_step = 0

with step_placeholder.container():
    render_step_pills(current_step)

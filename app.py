import streamlit as st

from supportx.controller import SupportXController


st.set_page_config(page_title="SupportX", page_icon="S", layout="wide")
st.title("SupportX")
st.caption("AI-Powered Multi-Agent Customer Support Triage and Resolution System")

@st.cache_resource
def get_controller() -> SupportXController:
    return SupportXController()


controller = get_controller()
with st.sidebar:
    st.header("Support desk")
    customer_id = st.text_input("Customer ID", value="CUST-001")
    message = st.text_area("Customer message", height=140, placeholder="Describe the issue...")
    submitted = st.button("Submit ticket", type="primary", use_container_width=True)

if submitted:
    try:
        ticket = controller.process(customer_id, message)
        st.success(f"Ticket {ticket.ticket_id} processed")
        left, right = st.columns(2)
        with left:
            st.metric("Detected category", ticket.detected_category)
            st.metric("Confidence", f"{ticket.confidence_score:.0%}")
            st.write("**Assigned specialist:**", ticket.assigned_specialist or "Human support")
            st.write("**Reviewer:**", ticket.reviewer_status)
        with right:
            st.write("**Escalation:**", ticket.escalation_status)
            if ticket.escalation_reason:
                st.warning(ticket.escalation_reason)
            st.write("**Response**")
            st.info(ticket.final_response)
        with st.expander("Execution trace", expanded=True):
            st.write(" -> ".join(ticket.execution_trace))
            st.write("Tools:", ", ".join(ticket.tool_calls))
        if ticket.retrieved_knowledge:
            with st.expander("Retrieved knowledge sources"):
                for source in ticket.retrieved_knowledge:
                    st.write(f"**{source['source']}** ({source['score']:.3f})")
                    st.write(source["text"])
    except Exception as exc:
        st.error(f"Ticket processing failed: {exc}")

st.divider()
st.header("Admin dashboard")
metrics = controller.dashboard()
columns = st.columns(6)
for column, label, key in zip(columns, ["Total", "Billing", "Technical", "Account", "Resolved", "Escalated"], ["total", "billing", "technical", "account", "resolved", "escalated"]):
    column.metric(label, metrics[key])
if metrics["recent"]:
    st.subheader("Recent ticket history")
    st.dataframe([{key: item[key] for key in ("ticket_id", "customer_id", "detected_category", "reviewer_status", "escalation_status")} for item in metrics["recent"]], use_container_width=True)
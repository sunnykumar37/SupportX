# SupportX

SupportX is an academic CSE476 project by Sunny Kumar and Anshuman Hota at Lovely Professional University. It demonstrates a router-to-specialists architecture for AI-assisted customer support triage and resolution.

## Architecture

The Streamlit interface sends a ticket to the routing controller. The classifier normalizes and classifies it as Billing, Technical, Account, or Other. Billing, technical, and account specialists use their own tools. Every specialist response goes through the reviewer. Low-confidence, unresolved, or repeatedly rejected tickets enter the escalation queue. See [architecture.md](architecture.md).

## Agents and tools

| Agent | Invoked tools |
| --- | --- |
| Classifier | `normalize_ticket_text`, `classify_ticket` |
| Billing Specialist | `lookup_invoice`, `check_refund_policy` |
| Technical Specialist | `retrieve_knowledge`, `run_troubleshooting_check` |
| Account Specialist | `check_account_status`, `validate_account_recovery_request` |
| Reviewer | `check_reply_tone`, `check_reply_completeness` |
| Escalation Router | `check_escalation_threshold`, `create_escalation_record` |

## RAG and memory

The technical specialist loads Markdown documents, splits them into chunks, embeds them with Sentence Transformers, and stores them in an ephemeral ChromaDB collection when those dependencies are available. A deterministic token-similarity fallback keeps demo mode and tests runnable offline. Answers are produced only from passages above the retrieval threshold; otherwise the ticket escalates. Conversation history is stored in `storage/tickets.json` and retrieved by customer ID.

Semantic Kernel and Groq settings are configurable through `.env`; the default deterministic demo mode does not pretend an LLM was called. The core specialist answers remain tool-grounded.

## Installation

```powershell
cd D:\SupportX
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For a network-free demonstration, keep `SUPPORTX_DEMO_MODE=true`. To configure Groq, set `GROQ_API_KEY` in `.env`; never commit that file.

## Run

```powershell
streamlit run app.py
```

Open the displayed local URL. Try customer `CUST-001` with `I was charged twice`, or `The application shows a blank screen error`.

## Test

```powershell
pytest -q
```

The tests cover billing, grounded technical retrieval, account access, low-confidence escalation, unresolved technical escalation, follow-up memory, reviewer rejection, and tool invocation.

## Notebook

Open `notebooks/supportx_demo.ipynb` in Jupyter or VS Code and run its cells. It uses the same controller as the application, so the displayed trace is real execution output rather than a fabricated transcript.

## Data and logs

Sample invoices, accounts, and knowledge-base documents live under `data/`. Runtime tickets are persisted in `storage/tickets.json`. The append-only event stream is `storage/execution.jsonl`; it records ticket receipt, agent activation, tool results, classification, RAG, review, escalation, and final response events.
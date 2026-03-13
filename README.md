# ⚖️ Legal Duelist

Legal Duelist is a multi-agent legal argument simulator powered by Large Language Models (LLMs) and LangGraph. It automates the process of legal research, evidence analysis, and adversarial argumentation to help users explore legal scenarios from both sides of a dispute.

## 🚀 Features

- **Multi-Agent Simulation**: Uses specialized agents for Plaintiff, Defense, and a Judge to simulate a realistic legal duel.
- **Automated Legal Research**: 
  - Fetches real-world precedents from the **CourtListener API**.
  - Performs semantic search over a local **FAISS knowledge base** containing statutes and laws.
- **Evidence Analysis**: Automatically parses and analyzes provided evidence to strengthen legal arguments.
- **Flexible LLM Support**: Supports Anthropic (Claude), OpenAI (GPT-4), and Google (Gemini) models.
- **Modern UI**: Interactive web interface built with **Streamlit** for easy use.
- **CLI Mode**: A rich terminal interface for quick simulations and debugging.

## 🛠️ Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/cheng-wang-ai/Legal-Duelist.git
cd Legal_Duelist
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory (or copy from `.env.example`):
```bash
cp .env.example .env
```
Edit `.env` and provide your API keys:
- `LLM_PROVIDER`: `anthropic`, `openai`, or `google`
- `LLM_API_KEY`: Your corresponding API key
- `COURT_LISTENER_TOKEN`: Your CourtListener API token (available for free at [CourtListener](https://www.courtlistener.com/))

## 🖥️ Usage

### Run the Web Interface
The Streamlit app provides the most comprehensive experience with interactive tools and visualizations.
```bash
streamlit run app.py
```

### Run the CLI Interface
For a direct terminal-based experience:
```bash
python main.py
```

## 📂 Project Structure

- `app.py`: Main entry point for the Streamlit web application.
- `main.py`: Main entry point for the CLI interface.
- `src/`: Core logic and agent definitions.
  - `graph.py`: LangGraph state machine orchestration.
  - `researcher.py`: Legal research pipeline (API + Vector DB).
  - `court_listener.py`: Client for real-world case law retrieval.
  - `database.py`: FAISS vector store for statutory knowledge.
  - `llm.py`: Model factory for different providers.
  - `prompts.py`: System prompts for legal agents.
- `knowledge_base.json`: Local repository of statutes and legal rules.

## ⚖️ Disclaimer
Legal Duelist is for educational and simulation purposes only. It does not provide professional legal advice. Always consult with a qualified attorney for real legal matters.

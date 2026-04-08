# PurpleMerit War Room Simulation

This system simulates a cross-functional "war room" during a product launch. Four specialized agents (PM, Data Analyst, Marketing, and Risk Critic) analyze mock metrics and user feedback to decide if the launch should Proceed, Pause, or Roll Back.

## Multi-Agent Architecture
1. **PM Agent**: Coordinator and final decision synthesiser.
2. **Data Analyst Agent**: Focuses on quantitative trends (latency, error rate).
3. **Marketing/Comms Agent**: Assesses customer perception and brand risk.
4. **Risk/Critic Agent**: Challenges assumptions and highlights outlier risks.

## Features
- **Metric Aggregator Tool**: Calculates trends (Last 3 days vs Previous) and identifies latency anomalies.
- **Feedback Sentiment Tool**: Categorizes user comments and extracts top negative issues.
- **Structured Output**: Produces a final JSON including decision, rationale, risk register, and action plan.

## Setup Instructions

1.  **Clone the repository**:
    ```bash
    git clone <repository-link>
    cd purple_merit_war_room
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set Environment Variables**:
    Create a `.env` file in the root directory.

    **Option A: OpenAI (Paid)**
    ```bash
    LLM_API_KEY=your_openai_key
    LLM_MODEL=gpt-4o
    ```

    **Option B: Groq (Free Tier)**
    1. Get a free key at [console.groq.com](https://console.groq.com/)
    2. Add to `.env`:
    ```bash
    LLM_API_KEY=your_groq_key
    LLM_BASE_URL=https://api.groq.com/openai/v1
    LLM_MODEL=llama-3.3-70b-versatile
    ```

    **Option C: Ollama (Local/Free)**
    1. Download [Ollama](https://ollama.com/)
    2. Run `ollama run llama3`
    3. Add to `.env`:
    ```bash
    LLM_API_KEY=ollama
    LLM_BASE_URL=http://localhost:11434/v1
    LLM_MODEL=llama3
    ```

4.  **Run the simulation**:
    ```bash
    python main.py
    ```

## Example Output
The system generates a `launch_decision.json` file. 

```json
{
  "decision": "Pause",
  "rationale": "Latency has spiked by 300% and error rates are climbing. While conversion is holding, user sentiment is rapidly deteriorating...",
  "risk_register": [
    {
      "risk": "High churn from premium users due to checkout failures",
      "mitigation": "Increase support staffing and provide automated refunds for failed sessions"
    }
  ],
  ...
}
```

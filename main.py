import os
import json
import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- Data Models ---

class RiskEntry(BaseModel):
    risk: str
    mitigation: str

class ActionItem(BaseModel):
    action: str
    owner: str
    timeline: str = Field(..., description="e.g., 24h, 48h")

class ConfidenceDriver(BaseModel):
    driver: str
    impact: str

class WarRoomDecision(BaseModel):
    decision: str = Field(..., description="MUST BE EXACTLY ONE OF: Proceed, Pause, or Roll Back")
    rationale: str
    risk_register: List[RiskEntry]
    action_plan: List[ActionItem]
    communication_plan: str
    confidence_score: float = Field(..., ge=0, le=1)
    confidence_drivers: List[ConfidenceDriver]

# --- Tools ---

class Tools:
    @staticmethod
    def analyze_metrics(file_path: str) -> str:
        try:
            df = pd.read_csv(file_path)
            # Calculate trends (last 3 days vs previous)
            last_3 = df.tail(3).mean(numeric_only=True)
            prev = df.iloc[:-3].mean(numeric_only=True)
            
            diff = ((last_3 - prev) / prev * 100).round(2)
            
            summary = "Metric Trends (Last 3 days vs Previous Period):\n"
            for col in diff.index:
                summary += f"- {col}: {last_3[col]:.4f} ({'+' if diff[col]>0 else ''}{diff[col]}%)\n"
            
            # Anomaly detection using Z-score
            summary += "\nAnomaly Detection (Z-Score > 2):\n"
            found_anomaly = False
            for col in df.select_dtypes(include=[np.number]).columns:
                mean = df[col].mean()
                std = df[col].std()
                if std == 0: continue
                
                latest_val = df[col].iloc[-1]
                z_score = (latest_val - mean) / std
                
                if abs(z_score) > 2:
                    summary += f"- ALERT: {col} has a significant deviation (Z-score: {z_score:.2f}, Latest: {latest_val})\n"
                    found_anomaly = True
            
            if not found_anomaly:
                summary += "- No significant statistical anomalies detected in the latest data point.\n"
            
            return summary
        except Exception as e:
            return f"Error analyzing metrics: {e}"

    @staticmethod
    def analyze_feedback(file_path: str) -> str:
        try:
            with open(file_path, 'r') as f:
                feedback = json.load(f)
            
            sentiments = [f['sentiment'] for f in feedback]
            pos = sentiments.count('positive')
            neg = sentiments.count('negative')
            neu = sentiments.count('neutral')
            
            total = len(feedback)
            summary = f"Sentiment Analysis (Total={total}): Positive={pos} ({(pos/total)*100:.1f}%), Negative={neg} ({(neg/total)*100:.1f}%), Neutral={neu}\n"
            summary += "Key Issues Extracted (Top Negative Sentiment):\n"
            
            # Simple keyword extraction for issues
            issues = []
            keywords = ['slow', 'lag', 'latency', 'crash', 'fail', 'error', '500', 'loading', 'payment', 'checkout', 'broken']
            for entry in feedback:
                if entry['sentiment'] == 'negative':
                    comment_lower = entry['comment'].lower()
                    for kw in keywords:
                        if kw in comment_lower:
                            issues.append(entry['comment'])
                            break
            
            for issue in issues[:10]: # Top 10 issues
                summary += f"- {issue}\n"
                
            return summary
        except Exception as e:
            return f"Error analyzing feedback: {e}"

# --- Agents ---

class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str, client: OpenAI, model: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.client = client
        self.model = model

    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{self.name}] {message}")

    def chat(self, prompt: str, context: str = "") -> str:
        full_prompt = f"Context Data:\n{context}\n\nQuestion/Instruction: {prompt}" if context else prompt
        self.log("Thinking...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            self.log(f"Error during API call: {e}")
            return f"Error: {e}"

class WarRoomOrchestrator:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY") or "ollama"
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = os.getenv("LLM_MODEL", "llama3.2")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        # Correct path construction
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.metrics_path = os.path.join(base_dir, "data", "metrics.csv")
        self.feedback_path = os.path.join(base_dir, "data", "feedback.json")
        self.notes_path = os.path.join(base_dir, "data", "release_notes.md")
        
        with open(self.notes_path, 'r') as f:
            self.release_notes = f.read()

        # Agents
        self.pm = BaseAgent(
            "PM Agent", "Product Manager",
            "You are the PM for PurpleMerit. Your goal is to balance user value vs technical risk. "
            "You decide if we Proceed, Pause, or Roll Back. Focus on overall product health.",
            self.client, self.model
        )
        self.analyst = BaseAgent(
            "Data Analyst Agent", "Data Analyst",
            "You are a Data Analyst. Focus on quantitative metrics, trends, and anomalies. "
            "Provide evidence-based summaries of system health.",
            self.client, self.model
        )
        self.marketing = BaseAgent(
            "Marketing Agent", "Marketing/Comms",
            "You are a Marketing and Communications expert. Focus on customer perception, "
            "brand trust, and how we communicate technical issues to the public.",
            self.client, self.model
        )
        self.risk = BaseAgent(
            "Risk/Critic Agent", "Risk/Critic",
            "You are a Risk Analyst. Your job is to be the 'devil's advocate'. "
            "Challenge assumptions, highlight worst-case scenarios, and demand mitigation for every issue.",
            self.client, self.model
        )

    def extract_json(self, text: str) -> Dict[str, Any]:
        """Robustly extracts JSON from LLM response."""
        try:
            # Try to find JSON block
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(text)
        except Exception:
            return {}

    def run(self):
        print(f"--- War Room Session Started ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ---")
        print(f"[System] Using Model: {self.model} via {self.base_url}")
        
        # Step 1: Tool Execution
        print("[System] Executing Analysis Tools...")
        metric_summary = Tools.analyze_metrics(self.metrics_path)
        feedback_summary = Tools.analyze_feedback(self.feedback_path)
        
        initial_context = f"Release Notes:\n{self.release_notes}\n\nMetric Analysis:\n{metric_summary}\n\nFeedback Analysis:\n{feedback_summary}"
        
        # Step 2: Multi-agent interaction (Dialogue Phase)
        print("\n--- Dialogue Phase ---")
        
        # Analyst starts
        analyst_view = self.analyst.chat("Evaluate the system health based on the latest metrics and anomalies.", initial_context)
        print(f"\n[Analyst]: {analyst_view}\n")
        
        # Marketing reacts to Analyst and Feedback
        mkt_context = f"{initial_context}\n\nAnalyst's Assessment: {analyst_view}"
        mkt_view = self.marketing.chat("Based on the technical data and user feedback, what is the risk to our brand?", mkt_context)
        print(f"\n[Marketing]: {mkt_view}\n")
        
        # Risk Critic challenges both
        risk_context = f"{mkt_context}\n\nMarketing's Assessment: {mkt_view}"
        risk_view = self.risk.chat("Challenge the current assessments. Are we underestimating the fallout? What if these trends continue for another 48 hours?", risk_context)
        print(f"\n[Risk Critic]: {risk_view}\n")
        
        # Step 3: PM Synthesis and Structured Decision
        print("\n--- Synthesis & Decision Phase ---")
        synthesis_prompt = (
            "Review all input and the cross-functional dialogue. Make a final decision. "
            "The 'decision' field MUST BE EXACTLY ONE OF: 'Proceed', 'Pause', or 'Roll Back'. "
            "You must output ONLY valid JSON matching the following structure:\n"
            "{\n"
            "  \"decision\": \"Proceed / Pause / Roll Back\",\n"
            "  \"rationale\": \"summary of why\",\n"
            "  \"risk_register\": [{\"risk\": \"...\", \"mitigation\": \"...\"}],\n"
            "  \"action_plan\": [{\"action\": \"...\", \"owner\": \"...\", \"timeline\": \"24h/48h\"}],\n"
            "  \"communication_plan\": \"internal/external guidance\",\n"
            "  \"confidence_score\": 0.5,\n"
            "  \"confidence_drivers\": [{\"driver\": \"...\", \"impact\": \"...\"}]\n"
            "}"
        )
        
        dialogue_history = f"Analyst: {analyst_view}\n\nMarketing: {mkt_view}\n\nRisk: {risk_view}"
        
        final_pm_context = f"{initial_context}\n\nDialogue History:\n{dialogue_history}"
        pm_output = self.pm.chat(synthesis_prompt, final_pm_context)
        
        decision_data = self.extract_json(pm_output)
        
        if not decision_data:
            print("[System] Failed to parse JSON from PM. Retrying once with stricter instructions...")
            pm_output = self.pm.chat("Your previous response was not valid JSON. Please provide ONLY the JSON object and nothing else.", final_pm_context)
            decision_data = self.extract_json(pm_output)

        if decision_data:
            try:
                # Ensure confidence_score is float
                if "confidence_score" in decision_data:
                    decision_data["confidence_score"] = float(decision_data["confidence_score"])
                
                decision = WarRoomDecision(**decision_data)
                print("\n--- FINAL STRUCTURED DECISION ---")
                print(json.dumps(decision.model_dump(), indent=2))
                
                # Save output
                output_file = "launch_decision.json"
                with open(output_file, "w") as f:
                    json.dump(decision.model_dump(), f, indent=2)
                print(f"\n[System] Decision successfully saved to {output_file}")
            except Exception as e:
                print(f"[System] Validation error: {e}")
                print(f"Raw PM Output: {pm_output}")
        else:
            print("[System] Error: PM failed to provide a structured decision.")

if __name__ == "__main__":
    try:
        orchestrator = WarRoomOrchestrator()
        orchestrator.run()
    except KeyboardInterrupt:
        print("\n[System] War Room session terminated by user.")
    except Exception as e:
        print(f"\n[System] Critical Error: {e}")

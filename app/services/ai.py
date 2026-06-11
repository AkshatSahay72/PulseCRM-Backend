from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings
import json
import logging

logger = logging.getLogger("uvicorn.error")

class AIService:
    def __init__(self):
        try:
            self.llm = ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name="llama-3.1-8b-instant",
                temperature=0.4
            )
        except Exception as e:
            logger.error(f"Groq initialization error: {e}")
            self.llm = None

    def generate_personalized_message(self, customer_name: str, recent_orders: list, campaign_topic: str) -> str:
        if recent_orders:
            orders_summary = "\n".join([
                f"- Order {o.id}: ${o.amount:.2f} ({o.status}) - {o.created_at.strftime('%Y-%m-%d')}"
                for o in recent_orders
            ])
        else:
            orders_summary = "No purchase history."

        fallback = f"Hi {customer_name}! Check out our offer: {campaign_topic}."

        if not self.llm:
            return fallback

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are a helpful copywriter. Write a personalized, brief marketing message.\n"
                    "Do not make up orders. Keep it under 100 words.\n"
                    "Goal: {campaign_topic}"
                )),
                ("user", (
                    "Name: {customer_name}\n"
                    "Orders:\n{orders_summary}\n\n"
                    "Message:"
                ))
            ])

            chain = prompt | self.llm
            response = chain.invoke({
                "customer_name": customer_name,
                "campaign_topic": campaign_topic,
                "orders_summary": orders_summary
            })
            return response.content.strip()
        except Exception as e:
            logger.error(f"Message generation error: {e}")
            return fallback

    def generate_segment_from_prompt(self, user_prompt: str) -> dict:
        if not self.llm:
            raise ValueError("LLM client not configured")

        system_prompt = (
            "Translate the user query into segment rules as JSON.\n"
            "Supported fields:\n"
            "- 'min_spending' (float)\n"
            "- 'max_spending' (float)\n"
            "- 'min_orders' (int)\n\n"
            "Response format:\n"
            "{{\n"
            "  \"name\": \"Segment Name\",\n"
            "  \"description\": \"Description\",\n"
            "  \"rules\": {{\n"
            "    \"min_spending\": float or null,\n"
            "    \"max_spending\": float or null,\n"
            "    \"min_orders\": int or null\n"
            "  }}\n"
            "}}\n"
            "Output only raw JSON."
        )

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{user_prompt}")
            ])

            chain = prompt | self.llm
            response = chain.invoke({"user_prompt": user_prompt})
            
            raw = response.content.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
                
            data = json.loads(raw)
            raw_rules = data.get("rules", {})
            
            valid_keys = ["min_spending", "max_spending", "min_orders"]
            rules = {k: v for k, v in raw_rules.items() if k in valid_keys and v is not None}
            
            return {
                "name": data.get("name", "Custom Segment"),
                "description": data.get("description", ""),
                "rules": rules
            }
        except Exception as e:
            logger.error(f"Segment generation error: {e}")
            raise ValueError(f"Could not parse query: {e}")

    def generate_copilot_recommendation(self, business_goal: str) -> dict:
        if not self.llm:
            raise ValueError("LLM client not configured")

        system_prompt = (
            "You are a growth marketing agent. The user will provide a business goal.\n"
            "Analyze the goal and recommend a complete marketing strategy.\n"
            "Identify the target audience segment, segment rules, subject line, message copy, and recommended channel.\n\n"
            "Supported segment rules fields:\n"
            "- 'min_spending' (float)\n"
            "- 'max_spending' (float)\n"
            "- 'min_orders' (int)\n\n"
            "Supported channels: 'email', 'sms', 'whatsapp'\n\n"
            "Response format MUST be a single raw JSON block:\n"
            "{{\n"
            "  \"segment_name\": \"Segment Name\",\n"
            "  \"segment_rules\": {{\n"
            "    \"min_spending\": float or null,\n"
            "    \"max_spending\": float or null,\n"
            "    \"min_orders\": int or null\n"
            "  }},\n"
            "  \"campaign_name\": \"Suggested Campaign Title\",\n"
            "  \"subject\": \"Email subject line (use only if email, else null)\",\n"
            "  \"message_template\": \"Personalized message copy. Use {first_name} for first name interpolation. Keep it brief and relevant to the goal.\",\n"
            "  \"channel\": \"email\" or \"sms\" or \"whatsapp\",\n"
            "  \"reasoning\": \"Brief explanation of why this target segment and copywriting angle fits the business goal.\"\n"
            "}}\n"
            "Do not include any formatting text, other content or markdown codeblocks. Return only raw JSON."
        )

        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("user", "{business_goal}")
            ])

            chain = prompt | self.llm
            response = chain.invoke({"business_goal": business_goal})
            
            raw = response.content.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw = "\n".join(lines).strip()
                
            data = json.loads(raw)
            
            # Clean segment rules
            raw_rules = data.get("segment_rules", {})
            valid_keys = ["min_spending", "max_spending", "min_orders"]
            rules = {k: v for k, v in raw_rules.items() if k in valid_keys and v is not None}
            
            return {
                "segment_name": data.get("segment_name", "Target Audience"),
                "segment_rules": rules,
                "campaign_name": data.get("campaign_name", "Recommended Campaign"),
                "subject": data.get("subject", "Exclusive Offer"),
                "message_template": data.get("message_template", "Hi {first_name}! Check out our offer."),
                "channel": data.get("channel", "email"),
                "reasoning": data.get("reasoning", "Recommended based on your goal.")
            }
        except Exception as e:
            logger.error(f"Copilot strategy generation error: {e}")
            raise ValueError(f"Could not parse query: {e}")

ai_service = AIService()

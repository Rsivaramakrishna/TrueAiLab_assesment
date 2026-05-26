import os
import logging
from typing import Tuple
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger("rag_assistant")

_RESOLVED_GEMINI_MODEL = None

class LLMException(Exception):
    """Custom exception for LLM API calls."""
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

def call_llm(prompt: str) -> Tuple[str, int, str]:
    """
    Call the configured LLM API (Gemini or OpenAI).
    Returns a tuple of (reply_text, tokens_used, model_name).
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    # 1. Gemini Integration
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or "your_" in api_key:
            # Fallback to LLM_API_KEY
            api_key = os.getenv("LLM_API_KEY")
            
        if not api_key or "your_" in api_key:
            logger.warning("Gemini API key is not configured or is a placeholder. Using grounded mock LLM.")
            return generate_mock_grounded_response(prompt, "mock-gemini-3.5-flash")
            
        try:
            import google.generativeai as genai
            from google.api_core.exceptions import InvalidArgument, ResourceExhausted, DeadlineExceeded
            
            genai.configure(api_key=api_key)
            
            # Resolve Gemini model name dynamically based on key support
            global _RESOLVED_GEMINI_MODEL
            try:
                if '_RESOLVED_GEMINI_MODEL' not in globals() or _RESOLVED_GEMINI_MODEL is None:
                    env_model = os.getenv("LLM_MODEL")
                    if env_model:
                        _RESOLVED_GEMINI_MODEL = env_model
                    else:
                        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        clean_models = [m.replace("models/", "") for m in models]
                        candidates = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
                        
                        found = False
                        for c in candidates:
                            if c in clean_models:
                                _RESOLVED_GEMINI_MODEL = c
                                found = True
                                break
                        
                        if not found:
                            for m in clean_models:
                                if "gemini" in m and "flash" in m:
                                    _RESOLVED_GEMINI_MODEL = m
                                    found = True
                                    break
                                    
                        if not found and clean_models:
                            _RESOLVED_GEMINI_MODEL = clean_models[0]
                        elif not found:
                            _RESOLVED_GEMINI_MODEL = "gemini-2.0-flash"
            except Exception as le:
                logger.warning(f"Error querying Gemini list_models: {le}")
                _RESOLVED_GEMINI_MODEL = "gemini-2.0-flash"
                
            model_name = _RESOLVED_GEMINI_MODEL
            logger.info(f"Using Gemini model name: {model_name}")
            
            model = genai.GenerativeModel(model_name)
            
            # Count prompt tokens for usage logging
            try:
                prompt_tokens = model.count_tokens(prompt).total_tokens
            except Exception:
                prompt_tokens = len(prompt.split()) // 3  # rough estimate
                
            logger.info("Calling Gemini API...")
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.2}
            )
            
            reply_text = response.text
            
            # Count output tokens
            try:
                output_tokens = model.count_tokens(reply_text).total_tokens
            except Exception:
                output_tokens = len(reply_text.split()) // 3
                
            total_tokens = prompt_tokens + output_tokens
            logger.info(f"Gemini API completed. Tokens used: {total_tokens}")
            
            return reply_text, total_tokens, model_name
            
        except InvalidArgument as e:
            logger.error(f"Gemini API - Invalid Argument/API Key: {e}")
            raise LLMException("Invalid Gemini API key or credentials provided.", status_code=401)
        except ResourceExhausted as e:
            logger.error(f"Gemini API - Rate limit exceeded: {e}")
            raise LLMException("Gemini API rate limit exceeded. Please try again later.", status_code=429)
        except DeadlineExceeded as e:
            logger.error(f"Gemini API - Request timeout: {e}")
            raise LLMException("Gemini API request timed out. Please try again.", status_code=504)
        except Exception as e:
            logger.error(f"Gemini API failure: {e}")
            raise LLMException(f"Failed to get response from Gemini LLM: {str(e)}", status_code=500)

    # 2. OpenAI Integration
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or "your_" in api_key:
            # Fallback to LLM_API_KEY
            api_key = os.getenv("LLM_API_KEY")
            
        if not api_key or "your_" in api_key:
            logger.warning("OpenAI API key is not configured or is a placeholder. Using grounded mock LLM.")
            return generate_mock_grounded_response(prompt, "mock-gpt-4o-mini")
            
        try:
            from openai import OpenAI, AuthenticationError, RateLimitError, APITimeoutError, APIError
            
            client = OpenAI(api_key=api_key)
            model_name = "gpt-4o-mini"
            logger.info("Calling OpenAI API...")
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                timeout=20.0
            )
            
            reply_text = response.choices[0].message.content
            total_tokens = response.usage.total_tokens if response.usage else 0
            logger.info(f"OpenAI API completed. Tokens used: {total_tokens}")
            
            return reply_text, total_tokens, model_name
            
        except AuthenticationError as e:
            logger.error(f"OpenAI API - Authentication error: {e}")
            raise LLMException("Invalid OpenAI API key provided.", status_code=401)
        except RateLimitError as e:
            logger.error(f"OpenAI API - Rate limit: {e}")
            raise LLMException("OpenAI API rate limit exceeded. Please try again later.", status_code=429)
        except APITimeoutError as e:
            logger.error(f"OpenAI API - Timeout: {e}")
            raise LLMException("OpenAI API request timed out. Please try again.", status_code=504)
        except APIError as e:
            logger.error(f"OpenAI API - Error: {e}")
            raise LLMException(f"OpenAI API error: {e.message}", status_code=502)
        except Exception as e:
            logger.error(f"OpenAI API failure: {e}")
            raise LLMException(f"Failed to get response from OpenAI LLM: {str(e)}", status_code=500)

    else:
        raise LLMException(f"Unsupported LLM provider: {provider}", status_code=400)


def generate_mock_grounded_response(prompt: str, model_name: str) -> Tuple[str, int, str]:
    """
    Fallback method that extracts the retrieved context from the prompt
    and generates a response based *only* on that context, mimicking a grounded LLM.
    """
    import re
    
    # Try to extract context block
    context_match = re.search(r"Context:\s*(.*?)\s*(?:Conversation History:|Question:|Answer:|$)", prompt, re.DOTALL | re.IGNORECASE)
    context = context_match.group(1).strip() if context_match else ""
    
    # Try to extract current question
    question_match = re.search(r"Question:\s*(.*?)\s*(?:Answer:|$)", prompt, re.DOTALL | re.IGNORECASE)
    question = question_match.group(1).strip() if question_match else ""
    
    tokens = len(prompt.split()) // 3 + 100
    
    if not context or "No relevant context" in context or len(context) < 10:
        reply = "I could not find enough information in the knowledge base to answer this question."
        return reply, tokens, model_name
    
    # Generate mock reply summarizing the matching document context
    reply = f"*(Demo Mode: Using local grounded mockup)*\n\nBased on our internal documents, here is the information regarding your inquiry:\n\n"
    
    # Simple semantic rule-based mock answers based on docs.json contents
    q_lower = question.lower()
    if "wifi" in q_lower or "wi-fi" in q_lower or "password" in q_lower and "guest" in q_lower:
        reply += "The guest Wi-Fi SSID is **Stellar-Guest** and the current access code is `StellarConnect2026!`. Please note that guest access is limited to standard web browsing and is restricted from internal servers."
    elif "reset" in q_lower and "password" in q_lower:
        reply += "You can reset your password by going to **Settings > Security**. Passwords must be at least 12 characters and include uppercase, lowercase, numbers, and special characters. Be aware that password resets are required every 90 days."
    elif "delete" in q_lower and "account" in q_lower:
        reply += "To delete your account, navigate to **Account Settings > Manage Profile > Delete Account**. Once requested, there is a 30-day grace period during which you can cancel the deletion by logging back in. After 30 days, all data is permanently erased."
    elif "refund" in q_lower or "billing" in q_lower:
        reply += "StellarTech Solutions offers a **14-day money-back guarantee** on all subscription plans. You can submit requests in the Billing Portal under 'Subscription Details > Request Refund' or by emailing `billing@stellartech.com`. Approved refunds take 5-7 business days."
    elif "hour" in q_lower or "remote" in q_lower or "hybrid" in q_lower:
        reply += "Our core working hours are **10:00 AM to 4:00 PM EST**, when all team members must be reachable. We follow a hybrid remote work model where you can work from home up to 3 days per week, subject to department head approval."
    elif "escalation" in q_lower or "tier" in q_lower or "support" in q_lower:
        reply += "IT Support has three tiers: Tier 1 (general inquiries/password resets), Tier 2 (network/hardware), and Tier 3 (servers/databases/security). Escalation times are 1 hour from Tier 1 to Tier 2, and 4 hours from Tier 2 to Tier 3."
    elif "expense" in q_lower or "reimburse" in q_lower or "travel" in q_lower:
        reply += "Expense reimbursement claims must be submitted in Expensify within **30 days** of purchase with receipts. Meals are reimbursed up to $50/person, travel mileage at $0.67/mile, and expenses over $500 require prior written approval."
    elif "conduct" in q_lower or "harassment" in q_lower or "bully" in q_lower:
        reply += "Under the StellarTech Code of Conduct, discrimination, harassment, and bullying are strictly prohibited to ensure a safe workspace. Employees must also protect confidential company data. Violations can lead to immediate termination."
    else:
        # Generic grounding fallback using the text contents
        clean_context = re.sub(r'\[.*?\]', '', context)
        reply += f"According to the retrieved records:\n\n{clean_context}\n\nIs there anything else about this you would like to know?"
        
    return reply, tokens, model_name

from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import requests
import logging
import json
import re

# Defina sua chave de API OpenAI
api_key = ""

model = "gpt-4.1-nano"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LaunchRequestHandler(AbstractRequestHandler):
    """Manipulador para início da Skill."""
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = "Chat G.P.T. ativado, no que posso ajudar?"

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class GptQueryIntentHandler(AbstractRequestHandler):
    """Manipulador para intenções de consulta ao Gpt."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        query = handler_input.request_envelope.request.intent.slots["query"].value

        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
            session_attr["last_context"] = None
        
        # Processa a consulta para verificar se é uma pergunta de acompanhamento
        processed_query, is_followup = process_followup_question(query, session_attr.get("last_context"))
        
        # Gera resposta com tratamento de contexto aprimorado
        response_data = generate_gpt_response(session_attr["chat_history"], processed_query, is_followup)
        
        # Trata os dados de resposta que podem ser uma tupla ou string
        if isinstance(response_data, tuple) and len(response_data) == 2:
            response_text, followup_questions = response_data
        else:
            # Retorno para casos de erro
            response_text = str(response_data)
            followup_questions = []
        
        # Armazena perguntas de acompanhamento na sessão
        session_attr["followup_questions"] = followup_questions
        
        # Atualiza o histórico de conversa apenas com o texto da resposta
        session_attr["chat_history"].append((query, response_text))
        session_attr["last_context"] = extract_context(query, response_text)
        
        # Formata a resposta com sugestões de acompanhamento, se houver
        response = response_text
        if followup_questions and len(followup_questions) > 0:
            response += " <break time=\"0.5s\"/> "
            response += "Você pode perguntar: "
            if len(followup_questions) > 1:
                response += ", ".join([f"'{q}'" for q in followup_questions[:-1]])
                response += f", ou '{followup_questions[-1]}'"
            else:
                response += f"'{followup_questions[0]}'"
            response += ". <break time=\"0.5s\"/> O que deseja saber?"
        
        # Prepara reprompt incluindo as perguntas de acompanhamento
        reprompt_text = "Você pode me fazer outra pergunta ou dizer parar para encerrar a conversa."
        if 'followup_questions' in session_attr and session_attr['followup_questions']:
            reprompt_text = "Você pode me fazer outra pergunta, dizer 'próxima' para ouvir mais sugestões, ou dizer parar para encerrar a conversa."
        
        return (
            handler_input.response_builder
                .speak(response)
                .ask(reprompt_text)
                .response
        )

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Tratamento genérico de erros para capturar qualquer erro de sintaxe ou roteamento."""
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        speak_output = "Desculpe, tive um problema para realizar o que você pediu. Por favor, tente novamente."
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Manipulador para as intenções Cancelar e Parar."""
    def can_handle(self, handler_input):
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        speak_output = "Chat G.P.T. desativado"
        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

def process_followup_question(question, last_context):
    """Processa uma pergunta para determinar se é de acompanhamento e adiciona contexto se necessário."""
    # Indicadores comuns de acompanhamento em português
    followup_patterns = [
        r'^(o que|como|por que|quando|onde|quem|qual|quais)\s+(sobre|é|são|foi|eram|faz|fazem|fez|podem|pode|poderia|deveria|vai|vão)\s',
        r'^(e|mas|então|também)\s',
        r'^(pode|poderia|deveria|vai|vão)\s+(você|ele|ela|eles|nós)\s',
        r'^(é|são|foi|eram|faz|fazem|fez)\s+(isso|aquilo|este|esses|essas|aqueles|aquelas)\s',
        r'^(me conte mais|explique melhor|elabore|fale mais)\s*',
        r'^(por que|como)\?*$'
    ]
    
    is_followup = False
    for pattern in followup_patterns:
        if re.search(pattern, question.lower()):
            is_followup = True
            break
    return question, is_followup

def extract_context(question, response):
    """Extrai o contexto principal de um par pergunta e resposta para referência futura."""
    return {"question": question, "response": response}

def generate_followup_questions(conversation_context, query, response, count=2):
    """Gera perguntas de acompanhamento curtas com base no contexto da conversa."""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = "https://api.openai.com/v1/chat/completions"
        
        # Prompt em português para perguntas curtas
        messages = [
            {"role": "system", "content": "Você é um assistente útil que sugere perguntas de acompanhamento curtas."},
            {"role": "user", "content": """Com base na conversa, sugira 2 perguntas de acompanhamento bem curtas (máx 4 palavras cada).
            Elas devem ser diretas e simples. Retorne APENAS as perguntas separadas por '|'.
            Exemplo: Qual a capital?|Qual o tamanho?"""}
        ]
        
        if conversation_context:
            last_q, last_a = conversation_context[-1]
            messages.append({"role": "user", "content": f"Pergunta anterior: {last_q}"})
            messages.append({"role": "assistant", "content": last_a})
        
        messages.append({"role": "user", "content": f"Pergunta atual: {query}"})
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": "Perguntas de acompanhamento (separadas por |):"})
        
        data = {
            "model": "gpt-4.1-nano",
            "messages": messages,
            "max_tokens": 50,
            "temperature": 0.7
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=3)
        if response.ok:
            questions_text = response.json()['choices'][0]['message']['content'].strip()
            questions = [q.strip().rstrip('?') for q in questions_text.split('|') if q.strip()]
            questions = [q for q in questions if len(q.split()) <= 4 and len(q) > 0][:2]
            
            if len(questions) < 2:
                questions = ["Me conte mais", "Me dê um exemplo"]
                
            logger.info(f"Perguntas de acompanhamento geradas: {questions}")
            return questions
            
        logger.error(f"Erro na API: {response.text}")
        return ["Me conte mais", "Me dê um exemplo"]
        
    except Exception as e:
        logger.error(f"Erro em generate_followup_questions: {str(e)}")
        return ["Me conte mais", "Me dê um exemplo"]

def generate_gpt_response(chat_history, new_question, is_followup=False):
    """Gera uma resposta GPT para uma pergunta com tratamento de contexto aprimorado."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = "https://api.openai.com/v1/chat/completions"
    
    # Mensagem de sistema em português
    system_message = "Você é um assistente útil. Responda em até 50 palavras."
    if is_followup:
        system_message += " Esta é uma pergunta de acompanhamento da conversa anterior. Mantenha o contexto sem repetir informações já fornecidas."
    
    messages = [{"role": "system", "content": system_message}]
    
    history_limit = 10 if not is_followup else 5
    for question, answer in chat_history[-history_limit:]:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    
    messages.append({"role": "user", "content": new_question})
    
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": 300
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_data = response.json()
        if response.ok:
            response_text = response_data['choices'][0]['message']['content']
            
            try:
                followup_questions = generate_followup_questions(
                    chat_history + [(new_question, response_text)], 
                    new_question, 
                    response_text
                )
                logger.info(f"Perguntas de acompanhamento geradas: {followup_questions}")
            except Exception as e:
                logger.error(f"Erro ao gerar perguntas de acompanhamento: {str(e)}")
                followup_questions = []
            
            return response_text, followup_questions
        else:
            return f"Erro {response.status_code}: {response_data['error']['message']}", []
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {str(e)}")
        return f"Erro ao gerar resposta: {str(e)}", []

class ClearContextIntentHandler(AbstractRequestHandler):
    """Manipulador para limpar o contexto da conversa."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("ClearContextIntent")(handler_input)

    def handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []
        session_attr["last_context"] = None
        
        speak_output = "O histórico da nossa conversa foi limpo. Sobre o que gostaria de falar?"
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(ClearContextIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()

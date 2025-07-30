> **ATENÇÃO:**  
> Este repositório é um **fork modificado** do projeto original [alexa-gpt](https://github.com/k4l1sh/alexa-gpt).  
> As instruções, exemplos e códigos foram adaptados para funcionar em **português do Brasil**.

# Alexa GPT

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Potencialize sua Alexa fazendo com que ela responda como o ChatGPT.

Este repositório contém um tutorial sobre como criar uma skill simples para Alexa que utiliza a API da OpenAI para gerar respostas usando o modelo ChatGPT.

<div align="center">
  <img src="images/test.png" />
</div>

## Pré-requisitos

- Uma [conta de desenvolvedor Amazon](https://developer.amazon.com/)
- Uma [chave de API da OpenAI](https://platform.openai.com/api-keys)

## Tutorial passo a passo

### 1. <span name=item-1></span>
Acesse sua conta de desenvolvedor Amazon e navegue até o [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).

### 2.
Clique em "Create Skill" e nomeie a skill como "Chat". Escolha o idioma principal conforme sua preferência.

![nomeie sua skill](images/name_your_skill.png)

### 3.
Escolha "Other" e "Custom" para o modelo.

![tipo de experiência](images/type_of_experience.png)

![escolha um modelo](images/choose_a_model.png)

### 4.
Selecione "Alexa-hosted (Python)" para os recursos de backend.

![serviços de hospedagem](images/hosting_services.png)

### 5.
Agora você tem duas opções:
- Clique em "Import Skill", cole o link deste repositório (https://github.com/k4l1sh/alexa-gpt.git) e clique em "Import".
![template](images/import_git_skill.png)

Ou, se preferir criar a skill manualmente:
- Selecione "Start from Scratch" e clique em "Create Skill"

![template](images/select_template.png)

### 6.
Na seção "Build", navegue até a aba "JSON Editor".

### 7.
Se você importou a skill diretamente deste repositório, basta alterar o "invocationName" para "chat" ou outro termo de ativação de sua escolha e avance para o [passo 12](#12).

Caso tenha optado por criar a skill manualmente, substitua o conteúdo JSON existente pelo [JSON fornecido](json_editor.json):

```json
{
    "interactionModel": {
        "languageModel": {
            "invocationName": "chat",
            "intents": [
                {
                    "name": "GptQueryIntent",
                    "slots": [
                        {
                            "name": "query",
                            "type": "AMAZON.Person"
                        }
                    ],
                    "samples": [
                        "{query}"
                    ]
                },
                {
                    "name": "AMAZON.CancelIntent",
                    "samples": []
                },
                {
                    "name": "AMAZON.HelpIntent",
                    "samples": []
                },
                {
                    "name": "AMAZON.StopIntent",
                    "samples": []
                },
                {
                    "name": "AMAZON.NavigateHomeIntent",
                    "samples": []
                }
            ],
            "types": []
        }
    }
}
```

![json_editor](images/intents_json_editor.png)

### 8.
Salve o modelo e clique em "Build Model".

### 9.
Vá para a seção "Code" e adicione "openai" ao arquivo requirements.txt. Seu requirements.txt deve ficar assim:

```txt
ask-sdk-core==1.11.0
boto3==1.9.216
requests>=2.20.0
openai
```

### 10.
Crie uma chave de API da OpenAI na [página de chaves de API](https://platform.openai.com/api-keys) clicando em "+ Create new secret key".

### 11.
Substitua seu arquivo lambda_functions.py pelo [lambda_function.py fornecido](lambda/lambda_function.py).

```python
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import requests
import logging
import json

# Defina sua chave de API da OpenAI
api_key = "SUA_API_KEY"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class LaunchRequestHandler(AbstractRequestHandler):
    """Manipulador para início da Skill."""
    def can_handle(self, handler_input):
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = "Modo Chat G.P.T. ativado"

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class GptQueryIntentHandler(AbstractRequestHandler):
    """Manipulador para intenção de consulta ao Gpt."""
    def can_handle(self, handler_input):
        return ask_utils.is_intent_name("GptQueryIntent")(handler_input)

    def handle(self, handler_input):
        query = handler_input.request_envelope.request.intent.slots["query"].value

        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
        response = generate_gpt_response(session_attr["chat_history"], query)
        session_attr["chat_history"].append((query, response))

        return (
                handler_input.response_builder
                    .speak(response)
                    .ask("Tem mais alguma pergunta?")
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
        speak_output = "Saindo do modo Chat G.P.T."

        return (
            handler_input.response_builder
                .speak(speak_output)
                .response
        )

def generate_gpt_response(chat_history, new_question):
    """Gera uma resposta GPT para uma nova pergunta"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    url = "https://api.openai.com/v1/chat/completions"
    messages = [{"role": "system", "content": "Você é um assistente útil. Responda em até 50 palavras."}]
    for question, answer in chat_history[-10:]:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": new_question})
    
    data = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "max_tokens": 300,
        "temperature": 0.5
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response_data = response.json()
        if response.ok:
            return response_data['choices'][0]['message']['content']
        else:
            return f"Erro {response.status_code}: {response_data['error']['message']}"
    except Exception as e:
        return f"Erro ao gerar resposta: {str(e)}"

sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GptQueryIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
```

### 12.
Coloque sua chave de API da OpenAI que você obteve na sua [conta OpenAI](https://platform.openai.com/api-keys)

![openai_api_key](images/api_key.png)

### 13.
Salve e faça o deploy. Vá para a seção "Test" e habilite "Skill testing" em "Development".

![development_enabled](images/development_enabled.png)

### 14.
Agora você está pronto para usar sua Alexa em modo ChatGPT. Você deve ver resultados como este:

![test](images/test.png)

> **Observação:**  
> Executar esta skill pode gerar custos tanto pelo uso do AWS Lambda quanto pela API da OpenAI. Certifique-se de entender a estrutura de preços e monitorar seu uso para evitar cobranças inesperadas.

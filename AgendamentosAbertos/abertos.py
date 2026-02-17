import os
import json
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Configurações da API
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Headers padrão para as requisições IXC
HEADERS = {
    "Authorization": f"Basic {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "ixcsoft": "listar"
}

# Lista de IDs de assuntos que devem ser monitorados
ASSUNTOS_ALVO = [
    544, 167, 546, 166, 543, 169, 545, 196, 170,
    547, 172, 258, 259, 192, 168, 252, 171, 393, 176
]

# Lista de IDs de responsáveis técnicos que devem ser monitorados
RESPONSAVEIS_ALVO = [
    345, 359, 337, 367, 307, 386, 389, 390, 423, 422,
    421, 416, 415, 414, 404, 424, 425, 306, 379, 343,
    304, 143, 268, 246, 348, 349
]

# Arquivo para persistir o estado dos alertas
ESTADO_ARQUIVO = "alerts_state.json"

# Intervalo de execução em minutos (pode ser alterado conforme necessidade)
INTERVALO_MINUTOS = 30

def carregar_estado():
    if os.path.exists(ESTADO_ARQUIVO):
        with open(ESTADO_ARQUIVO, "r") as f:
            return json.load(f)
    return {}

def salvar_estado(estado):
    with open(ESTADO_ARQUIVO, "w") as f:
        json.dump(estado, f, indent=2, default=str)

def buscar_chamados_abertos():
    chamados = []
    page = 1
    url = "https://assinante.nmultifibra.com.br/webservice/v1/su_oss_chamado"
    while True:
        payload = {
            "qtype": "status",
            "query": "A",
            "oper": "=",
            "page": str(page),
            "rp": "9999"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Erro ao buscar chamados (página {page}): {e}")
            break

        if "registros" in data and data["registros"]:
            chamados.extend(data["registros"])
            if len(data["registros"]) < 9999:
                break
            page += 1
        else:
            break
    return chamados

def obter_id_responsavel_por_ticket(id_ticket):
    if not id_ticket:
        return None
    url = "https://assinante.nmultifibra.com.br/webservice/v1/su_ticket"
    payload = {
        "qtype": "id",
        "query": str(id_ticket),
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if "registros" in data and data["registros"]:
            return data["registros"][0].get("id_responsavel_tecnico")
    except Exception as e:
        print(f"Erro ao buscar ticket {id_ticket}: {e}")
    return None

def obter_nome_responsavel(id_responsavel):
    if not id_responsavel:
        return "Não informado"
    url = "https://assinante.nmultifibra.com.br/webservice/v1/funcionarios"
    payload = {
        "qtype": "id",
        "query": str(id_responsavel),
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if "registros" in data and data["registros"]:
            return data["registros"][0].get("funcionario", "Desconhecido")
    except Exception as e:
        print(f"Erro ao buscar funcionário {id_responsavel}: {e}")
    return "Não encontrado"

def obter_assunto_por_id(id_assunto):
    url = "https://assinante.nmultifibra.com.br/webservice/v1/su_oss_assunto"
    payload = {
        "qtype": "id",
        "query": str(id_assunto),
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        if "registros" in data and data["registros"]:
            return data["registros"][0].get("assunto", str(id_assunto))
    except Exception as e:
        print(f"Erro ao buscar assunto {id_assunto}: {e}")
    return str(id_assunto)

def enviar_alerta_telegram(mensagem, max_retries=5):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 429:
                retry_after = response.json().get('parameters', {}).get('retry_after', 5)
                print(f"Rate limit: aguardando {retry_after}s...")
                time.sleep(retry_after)
                continue
            response.raise_for_status()
            print("Alerta enviado com sucesso.")
            return True
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response and e.response.status_code == 429:
                try:
                    retry_after = e.response.json().get('parameters', {}).get('retry_after', 5)
                except:
                    retry_after = 5
                print(f"Rate limit: aguardando {retry_after}s...")
                time.sleep(retry_after)
            else:
                print(f"Erro ao enviar mensagem Telegram: {e}")
                return False
    print("Falha ao enviar mensagem após múltiplas tentativas.")
    return False

def main():
    print(f"Iniciando monitoria - {datetime.now()}")
    estado = carregar_estado()
    agora = datetime.now()
    chamados = buscar_chamados_abertos()
    print(f"Total de chamados com status A: {len(chamados)}")

    ids_abertos = set()
    total_assunto_filtrado = 0
    total_tempo_filtrado = 0
    total_ja_alertado = 0
    total_responsavel_filtrado = 0
    alertas_enviados = 0

    for chamado in chamados:
        id_os = chamado["id"]
        id_assunto = int(chamado["id_assunto"])

        if id_assunto not in ASSUNTOS_ALVO:
            continue
        total_assunto_filtrado += 1
        ids_abertos.add(id_os)

        data_abertura_str = chamado["data_abertura"]
        try:
            data_abertura = datetime.strptime(data_abertura_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"Erro ao converter data {data_abertura_str} do chamado {id_os}: {e}")
            continue

        minutos_abertura = (agora - data_abertura).total_seconds() / 60.0
        if minutos_abertura < 30:
            continue
        total_tempo_filtrado += 1

        info_estado = estado.get(id_os)
        if info_estado:
            ultimo_alerta = datetime.fromisoformat(info_estado["last_alert"])
            minutos_ultimo = (agora - ultimo_alerta).total_seconds() / 60.0
            if minutos_ultimo < 30:
                total_ja_alertado += 1
                continue

        id_ticket = chamado.get("id_ticket")
        if not id_ticket:
            print(f"Chamado {id_os} sem id_ticket, ignorado.")
            continue

        id_responsavel = obter_id_responsavel_por_ticket(id_ticket)
        if not id_responsavel:
            print(f"Chamado {id_os}: não foi possível obter responsável.")
            continue

        if int(id_responsavel) not in RESPONSAVEIS_ALVO:
            total_responsavel_filtrado += 1
            continue

        nome_responsavel = obter_nome_responsavel(id_responsavel)
        assunto_desc = obter_assunto_por_id(id_assunto)

        mensagem = (
            f"⏱️ ORDEM DE SERVIÇO S/ AGENDAMENTO\n\n"
            f"ID Cliente: {chamado['id_cliente']}\n"
            f"ID O.S.: {id_os}\n"
            f"Assunto: {assunto_desc}\n"
            f"Abertura: {data_abertura_str}\n"
            f"Agendamento: SEM AGENDAMENTO ❌\n"
            f"Responsável: {nome_responsavel}"
        )

        if enviar_alerta_telegram(mensagem):
            alertas_enviados += 1
            estado[id_os] = {
                "last_alert": agora.isoformat(),
                "subject_id": id_assunto,
                "client_id": chamado["id_cliente"],
                "open_date": data_abertura_str,
                "responsavel_id": id_responsavel
            }

        time.sleep(1)

    # Remove chamados finalizados do estado
    for id_os in list(estado.keys()):
        if id_os not in ids_abertos:
            del estado[id_os]
    salvar_estado(estado)

    print("\n--- RELATÓRIO DE FILTRAGEM ---")
    print(f"Chamados com assunto alvo: {total_assunto_filtrado}")
    print(f"Chamados com >=30 min abertura: {total_tempo_filtrado}")
    print(f"Chamados já alertados <30 min: {total_ja_alertado}")
    print(f"Chamados com responsável fora da lista: {total_responsavel_filtrado}")
    print(f"Alertas enviados agora: {alertas_enviados}")
    print("Monitoria finalizada.\n")

if __name__ == "__main__":
    # Loop infinito com agendamento interno
    while True:
        main()
        print(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima execução...")
        time.sleep(INTERVALO_MINUTOS * 60)  # Converte minutos para segundos
import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURAÇÕES ====================
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
AUTH_TOKEN = os.getenv('AUTH_TOKEN')

HEADERS = {
    "Authorization": f"Basic {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "ixcsoft": "listar"
}

ASSUNTOS_ALVO = [
    544, 167, 546, 166, 543, 169, 545, 196, 170,
    547, 172, 258, 259, 192, 168, 252, 171, 393,
    176, 380
]

# IDs da terceirizada (Suporte Aprimorar)
RESPONSAVEIS_ALVO = [283] # Meu ID: 236

# IDs dos encarregados (preencher com os IDs corretos)
# Vinicius Arruda Felix = 152
ENCARREGADOS_IDS = [152]  # Adicione os demais IDs conforme necessário

BASE_URL = "https://assinante.nmultifibra.com.br/webservice/v1"
INTERVALO_MINUTOS = 15
ARQUIVO_ULTIMA_EXEC = "ultima_execucao.txt"

# ==================== FUNÇÕES AUXILIARES ====================
def carregar_ultima_execucao():
    try:
        with open(ARQUIVO_ULTIMA_EXEC, 'r') as f:
            return datetime.fromisoformat(f.read().strip())
    except:
        return datetime(2000, 1, 1)

def salvar_ultima_execucao(timestamp):
    with open(ARQUIVO_ULTIMA_EXEC, 'w') as f:
        f.write(timestamp.isoformat())

def api_request(endpoint, payload):
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.post(url, headers=HEADERS, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        """ print(f"[ERRO] Requisição para {endpoint} falhou: {e}") """
        if 'response' in locals():
            """ print("Resposta:", response.text[:500]) """
        return None

def get_oss_por_data_abertura(data_inicio):
    todas_os = []
    page = 1
    rp = 5000
    while True:
        """ print(f"Buscando página {page} de OS com data_abertura >= {data_inicio}...") """
        payload = {
            "qtype": "data_abertura",
            "query": data_inicio,
            "oper": ">=",
            "page": str(page),
            "rp": str(rp)
        }
        data = api_request("su_oss_chamado", payload)
        if not data:
            break

        registros = data.get('registros', [])
        todas_os.extend(registros)
        total = int(data.get('total', 0))
        """ print(f"Página {page}: {len(registros)} registros, total informado: {total}") """

        if len(registros) < rp or page * rp >= total:
            """ print("Última página atingida.") """
            break
        page += 1

    """ print(f"Total de OS coletadas: {len(todas_os)}") """
    return todas_os

def get_mensagens_os(id_chamado):
    todas_msgs = []
    page = 1
    while True:
        payload = {
            "qtype": "id_chamado",
            "query": str(id_chamado),
            "oper": "=",
            "page": str(page),
            "rp": "1000"
        }
        data = api_request("su_oss_chamado_mensagem", payload)
        if not data:
            break

        registros = data.get('registros', [])
        todas_msgs.extend(registros)

        total = int(data.get('total', 0))
        if len(registros) < 1000 or page * 1000 >= total:
            break
        page += 1

    todas_msgs.sort(key=lambda x: x['data'])
    return todas_msgs

def obter_nome_assunto(id_assunto, cache):
    if id_assunto in cache:
        return cache[id_assunto]

    payload = {
        "qtype": "id",
        "query": str(id_assunto),
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    data = api_request("su_oss_assunto", payload)
    if data and data.get('registros'):
        nome = data['registros'][0].get('assunto', f'Desconhecido ({id_assunto})')
    else:
        nome = f'Desconhecido ({id_assunto})'

    cache[id_assunto] = nome
    return nome

def analisar_os(os_data, cache_assuntos, ultima_execucao):
    id_os = os_data['id']
    id_cliente = os_data['id_cliente']
    id_assunto = int(os_data['id_assunto'])
    assunto_nome = obter_nome_assunto(id_assunto, cache_assuntos)

    tecnico_atual = None
    if os_data.get('id_tecnico'):
        try:
            tecnico_atual = int(os_data['id_tecnico'])
        except:
            pass
    tecnico_definido_por = None
    status_atual = None
    encaminhada_por_encarregado = False
    reagendada = False  # Indica que a OS está em fluxo de pós-reagendamento
    violacoes = []

    mensagens = get_mensagens_os(id_os)
    hoje = datetime.now().date()

    for msg in mensagens:
        try:
            data_msg = datetime.strptime(msg['data'], "%Y-%m-%d %H:%M:%S")
        except:
            continue

        if data_msg <= ultima_execucao:
            continue

        id_operador = int(msg.get('id_operador', 0))
        is_terceirizada = id_operador in RESPONSAVEIS_ALVO
        is_encarregado = id_operador in ENCARREGADOS_IDS
        id_evento = int(msg.get('id_evento', 0))
        status_msg = msg.get('status', '')
        id_tecnico_msg = msg.get('id_tecnico')
        if id_tecnico_msg:
            try:
                id_tecnico_msg = int(id_tecnico_msg)
            except:
                id_tecnico_msg = None

        status_anterior = status_atual

        # Se a OS está em reagendamento (status RAG ou evento 11), ativa a flag
        if status_msg == 'RAG' or id_evento == 11:
            reagendada = True

        # Se já foi encaminhada por encarregado, qualquer ação da terceirizada é violação
        if encaminhada_por_encarregado and is_terceirizada:
            if id_evento in (4, 5):
                if id_evento == 4:
                    desc = f"Alterou técnico (encaminhamento) após encarregado"
                else:
                    desc = f"Agendou após encarregado"
                violacoes.append((
                    "apos_encarregado",
                    desc,
                    data_msg,
                    msg.get('historico', '')
                ))
        else:
            # Regras aplicáveis quando não há bloqueio por encarregado
            if is_terceirizada:
                # 1) Agendamento para o mesmo dia (sempre verificar)
                if id_evento == 5:
                    data_agenda_final = msg.get('data_final')
                    if data_agenda_final and data_agenda_final != '0000-00-00 00:00:00':
                        try:
                            data_agenda = datetime.strptime(data_agenda_final, "%Y-%m-%d %H:%M:%S").date()
                            data_acao = data_msg.date()
                            if data_agenda == data_acao:
                                violacoes.append((
                                    "mesmo_dia",
                                    f"Agendou para o mesmo dia",
                                    data_msg,
                                    msg.get('historico', '')
                                ))
                        except:
                            pass

                # 2) Regras que só se aplicam se NÃO estiver em modo reagendamento
                if not reagendada:
                    # Alteração de técnico (evento 4)
                    if id_evento == 4 and id_tecnico_msg is not None:
                        if (tecnico_atual is not None and
                            tecnico_definido_por not in RESPONSAVEIS_ALVO and
                            id_tecnico_msg != tecnico_atual):
                            violacoes.append((
                                "alteracao_tecnico",
                                f"Técnico alterado de {tecnico_atual} para {id_tecnico_msg}",
                                data_msg,
                                msg.get('historico', '')
                            ))

                    # Troca de status EN -> AG (evento 5)
                    if id_evento == 5 and status_anterior == 'EN':
                        violacoes.append((
                            "en_para_ag",
                            "Status alterado de EN para AG",
                            data_msg,
                            msg.get('historico', '')
                        ))

        # ----- Atualização do estado global (independente do operador) -----
        # Atualiza técnico
        if id_evento == 4 and id_tecnico_msg is not None:
            tecnico_atual = id_tecnico_msg
            tecnico_definido_por = id_operador

        # Atualiza status
        if status_msg:
            status_atual = status_msg

        # Verifica se este evento é um encaminhamento feito por um encarregado
        if is_encarregado and id_evento == 4:
            encaminhada_por_encarregado = True

    return violacoes, assunto_nome, id_cliente

def enviar_telegram(mensagem):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        """ print(f"[ERRO] Falha ao enviar mensagem Telegram: {e}") """

def executar_monitoramento(ultima_execucao):
    print(f"[{datetime.now()}] Iniciando ciclo de monitoramento...")
    print(f"Última execução: {ultima_execucao}")
    try:
        hoje = datetime.now()
        data_inicio = hoje.strftime("%Y-%m-01")

        cache_assuntos = {}

        todas_os = get_oss_por_data_abertura(data_inicio)
        if not todas_os:
            """ print("Nenhuma OS encontrada com abertura a partir de", data_inicio) """
            return

        oss_alvo = [
            os for os in todas_os
            if os.get('status') in ['AG', 'EN']
            and int(os.get('id_assunto', 0)) in ASSUNTOS_ALVO
        ]
        """ print(f"OS com status AG/EN e assuntos alvo: {len(oss_alvo)}") """

        for os_data in oss_alvo:
            violacoes, assunto_nome, id_cliente = analisar_os(os_data, cache_assuntos, ultima_execucao)
            if violacoes:
                msg = f"🛑 TERCEIRIZADA MEXEU NA O.S\n\n"
                msg += f"• ID Cliente: {id_cliente}\n"
                msg += f"• ID O.S: {os_data['id']}\n"
                msg += f"• Assunto: {assunto_nome}\n"

                for tipo, desc, data_hora, hist in violacoes:
                    data_str = data_hora.strftime("%d/%m/%Y - %H:%M")
                    if tipo == "mesmo_dia":
                        msg += f"• Horário de Alteração: {data_str} (Agendou para o mesmo dia)\n"
                    elif tipo == "alteracao_tecnico":
                        msg += f"• Horário de Alteração: {data_str} (Alterou técnico)\n"
                    elif tipo == "en_para_ag":
                        msg += f"• Horário de Alteração: {data_str} (Trocou EN para AG)\n"
                    elif tipo == "apos_encarregado":
                        msg += f"• Horário de Alteração: {data_str} (Ação após encaminhamento do encarregado)\n"

                enviar_telegram(msg)
                """ print(f"Alerta enviado para OS {os_data['id']}") """
    except Exception as e:
        """ print(f"[ERRO] Falha no ciclo de monitoramento: {e}") """

def main():
    """ print(f"Monitoramento iniciado. Intervalo: {INTERVALO_MINUTOS} minutos.") """
    while True:
        ultima_exec = carregar_ultima_execucao()
        executar_monitoramento(ultima_exec)
        agora = datetime.now()
        salvar_ultima_execucao(agora)
        """ print(f"Aguardando {INTERVALO_MINUTOS} minutos até a próxima execução...") """
        time.sleep(INTERVALO_MINUTOS * 60)

if __name__ == "__main__":
    main()
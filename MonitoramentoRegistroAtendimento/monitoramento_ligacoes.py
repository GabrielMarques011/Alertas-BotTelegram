import requests
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
import re
import time

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
IXC_TOKEN_API = os.getenv('IXC_TOKEN_API')
IXC_HOST_API = os.getenv('IXC_HOST_API')
ESCALLO_HOST = os.getenv('ESCALLO_HOST')
ESCALLO_TOKEN = os.getenv('ESCALLO_TOKEN')

# Configurações WhatsApp
WHATSAPP_SERVICE_URL = os.getenv('WHATSAPP_SERVICE_URL', 'http://localhost:7575')
WHATSAPP_GROUP_COMERCIAL = os.getenv('WHATSAPP_GROUP_ID_COMERCIAL')
WHATSAPP_GROUP_DEMANDAS = os.getenv('WHATSAPP_GROUP_ID_DEMANDAS')

# Configurar logging - APENAS CONSOLE
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)

# Lista de atendentes para filtrar
ATENDENTES_FILTRO = [
    "4002", "4004", "4006", "4008", "4009", "4021", "4025", "4027",
    "4028", "4029", "4030", "4031", "4032", "4033", "1204", "1210", 
    "1208", "1205", "1201"
]

# Mapeamento de ramal para ID do responsável no IXC
RAMAL_RESPONSAVEL_MAP = {
    "4002": "359",  # Pedro Henrique
    "4004": "345",  # João Miyake
    "4006": "307",  # Gabriel Rosa
    "4008": "386",  # Gabriel Lima (Estagiário)
    "4009": "389",  # Marcos Piazzi (Estagiário)
    "4021": "367",  # Rodrigo Akira
    "4025": "337",  # Alison da Silva
    "4027": "390",  # Pedro Guedes (Estagiário)
    "4028": "414",  # Ryan Silva (Estagiário)
    "4029": "415",  # Samuel Mendes (Estagiário)
    "4030": "422",  # Pedro Boni
    "4031": "423",  # Rafael Guedes
    "4032": "421",  # Ricardo Corrêa
    "4033": "416",  # João Silva (Estagiário)

    "1204": "268",  # Tamires Cavalcante
    "1210": "379",  # Rodrigo Boani
    "1208": "343",  # Rennan Taioqui
    "1205": "266",  # Miguel Roveda
    "1201": "304"   # Gustavo Leonidas
}

# Mapeamento de ramal para nome completo
RAMAL_NOME_MAP = {
    "4002": "Pedro Henrique",
    "4004": "João Miyake",
    "4006": "Gabriel Rosa",
    "4008": "Gabriel Brambila (Estagiário)",
    "4009": "Marcos Moraes (Estagiário)",
    "4021": "Rodrigo Akira",
    "4025": "Alison da Silva",
    "4027": "Pedro Chaves (Estagiário)",
    "4028": "Ryan da Silva (Estagiário)",
    "4029": "Samuel Mendes (Estagiário)",
    "4030": "Pedro Boni",
    "4031": "Rafael Guedes",
    "4032": "Ricardo Correa",
    "4033": "João Silva (Estagiario)",

    "1204": "Tamires Cavalcante",
    "1210": "Rodrigo Boani",
    "1208": "Rennan Taioqui",
    "1205": "Miguel Roveda",
    "1201": "Gustavo Leonidas"
}

# IDs de assunto dos atendimentos automáticos do Escallo
ATENDIMENTOS_AUTOMATICOS_IDS = [324, 533, 679, 323, 322, 321, 329, 326, 435, 532, 325, 436, 327, 534, 328, 346, 347, 348, 531]

# Arquivo para controlar última execução
LAST_EXECUTION_FILE = "ultima_execucao.txt"

def obter_ultima_data_hora():
    """Obtém a última data/hora de execução do arquivo"""
    try:
        if os.path.exists(LAST_EXECUTION_FILE):
            with open(LAST_EXECUTION_FILE, 'r', encoding='utf-8') as f:
                data_str = f.read().strip()
                if data_str:
                    return datetime.strptime(data_str, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logging.error(f"Erro ao ler última execução: {e}")
    
    # Se não existe ou erro, retorna início do dia atual
    hoje = datetime.now().strftime('%Y-%m-%d')
    return datetime.strptime(f"{hoje} 00:00:00", '%Y-%m-%d %H:%M:%S')

def salvar_ultima_data_hora():
    """Salva a data/hora atual como última execução"""
    try:
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(LAST_EXECUTION_FILE, 'w', encoding='utf-8') as f:
            f.write(data_atual)
        logging.info(f"Última execução salva: {data_atual}")
    except Exception as e:
        logging.error(f"Erro ao salvar última execução: {e}")

def validar_telefone(numero):
    """Valida se o telefone é válido para consulta"""
    if not numero:
        return False
    
    # Remover espaços e caracteres especiais
    numero_limpo = ''.join(filter(str.isdigit, str(numero)))
    
    # Ignorar números como "0anonymous"
    if numero_limpo == "0" or "anonymous" in str(numero).lower():
        return False
    
    # Verificar se tem pelo menos 10 dígitos (com DDD)
    if len(numero_limpo) < 10:
        return False
    
    return True

def formatar_telefone_para_ixc(numero):
    """Formata o telefone para o padrão do IXC"""
    numero_limpo = ''.join(filter(str.isdigit, str(numero)))
    
    if numero_limpo.startswith('0'):
        numero_limpo = numero_limpo[1:]
    
    if len(numero_limpo) == 11:
        ddd = numero_limpo[:2]
        parte1 = numero_limpo[2:7]
        parte2 = numero_limpo[7:]
        return f"({ddd}) {parte1}-{parte2}"
    elif len(numero_limpo) == 10:
        ddd = numero_limpo[:2]
        parte1 = numero_limpo[2:6]
        parte2 = numero_limpo[6:]
        return f"({ddd}) {parte1}-{parte2}"
    else:
        return numero_limpo

def extrair_ramal(destino):
    """Extraí o ramal da string de destino"""
    try:
        padroes = [
            r'\((\d{4})\)',
            r'ramal@(\d{4})',
            r'(\d{4}) Suporte',
            r'Suporte.*\((\d{4})\)'
        ]
        
        for padrao in padroes:
            match = re.search(padrao, str(destino))
            if match:
                return match.group(1)
    except:
        pass
    return None

def obter_ligacoes_desde_ultima_execucao():
    """Obtém as ligações desde a última execução"""
    ultima_execucao = obter_ultima_data_hora()
    data_hoje = datetime.now().strftime('%Y-%m-%d')
    
    # Se a última execução foi ontem, começar do início do dia atual
    if ultima_execucao.strftime('%Y-%m-%d') != data_hoje:
        ultima_execucao = datetime.strptime(f"{data_hoje} 00:00:00", '%Y-%m-%d %H:%M:%S')
    
    # Formatar datas para a API
    data_inicial = ultima_execucao.strftime('%Y-%m-%d')
    horario_inicial = ultima_execucao.strftime('%H:%M:%S')
    
    url = f"http://{ESCALLO_HOST}/escallo/api/v1/recurso/relatorio/rel001/?registros=2000&pagina=0"
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Partner {ESCALLO_TOKEN}'
    }
    
    data = {
        "dataInicial": data_inicial,
        "dataFinal": data_hoje,  # Sempre até hoje
        "horarioInicial": horario_inicial,
        "horarioFinal": "23:59:59"
    }
    
    try:
        logging.info(f"Buscando ligações desde: {data_inicial} {horario_inicial}")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Erro ao obter ligações do Escallo: {e}")
        return None

def get_ixc_headers():
    """Retorna os headers para a API do IXC"""
    return {
        "Authorization": f"Basic {IXC_TOKEN_API}",
        "Content-Type": "application/json",
        "ixcsoft": "listar"
    }

def buscar_cliente_por_atendimentos_automaticos(telefone):
    """Busca cliente pelos atendimentos automáticos do dia (primeira opção)"""
    hoje = datetime.now().strftime('%Y-%m-%d')
    telefone_limpo = ''.join(filter(str.isdigit, str(telefone)))
    if telefone_limpo.startswith('0'):
        telefone_limpo = telefone_limpo[1:]
    
    clientes_encontrados = []
    
    for id_assunto in ATENDIMENTOS_AUTOMATICOS_IDS:
        url = f"{IXC_HOST_API}/su_ticket"
        headers = get_ixc_headers()
        
        data = {
            "qtype": "id_assunto",
            "query": str(id_assunto),
            "oper": "=",
            "page": "1",
            "rp": "100"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code != 200:
                continue
            
            try:
                dados = response.json()
            except:
                continue
            
            total = dados.get("total")
            if total is not None:
                if isinstance(total, str):
                    try:
                        total_int = int(total)
                    except ValueError:
                        total_int = 0
                else:
                    total_int = int(total) if total else 0
                
                if total_int > 0:
                    for atendimento in dados.get("registros", []):
                        # Verificar se o atendimento é do dia atual
                        data_criacao_str = atendimento.get("data_criacao", "")
                        if not data_criacao_str or data_criacao_str == "0000-00-00 00:00:00":
                            continue
                        
                        try:
                            data_criacao = datetime.strptime(data_criacao_str, '%Y-%m-%d %H:%M:%S')
                            if data_criacao.strftime('%Y-%m-%d') != hoje:
                                continue
                        except:
                            continue
                        
                        # Extrair telefone da mensagem
                        mensagem = atendimento.get("menssagem", "")
                        
                        # Padrões para extrair telefone
                        padroes = [
                            r'Telefone de contato:\s*(\d{10,11})',
                            r'telefone:\s*(\d{10,11})',
                            r'Contato realizado através do telefone:\s*(\d{10,11})'
                        ]
                        
                        for padrao in padroes:
                            match = re.search(padrao, mensagem, re.IGNORECASE)
                            if match:
                                telefone_atendimento = match.group(1)
                                telefone_atendimento_limpo = ''.join(filter(str.isdigit, str(telefone_atendimento)))
                                
                                if telefone_atendimento_limpo.startswith('0'):
                                    telefone_atendimento_limpo = telefone_atendimento_limpo[1:]
                                
                                # Comparar telefones
                                if telefone_atendimento_limpo == telefone_limpo:
                                    id_cliente = atendimento.get("id_cliente")
                                    if id_cliente and id_cliente != "0":
                                        # Buscar informações completas do cliente
                                        cliente_completo = obter_cliente_por_id(id_cliente)
                                        if cliente_completo and cliente_completo.get("ativo") == "S":
                                            # Adicionar telefone formatado
                                            cliente_completo["telefone"] = formatar_telefone_para_ixc(telefone)
                                            cliente_completo["telefone_original"] = telefone
                                            
                                            if cliente_completo not in clientes_encontrados:
                                                clientes_encontrados.append(cliente_completo)
                                        elif cliente_completo:
                                            logging.info(f"        Cliente {id_cliente} encontrado mas está INATIVO (ativo: {cliente_completo.get('ativo')})")
        except Exception as e:
            logging.error(f"Erro ao buscar atendimento automático ID {id_assunto}: {e}")
            continue
    
    # Remover duplicados por ID
    clientes_unicos = []
    ids_vistos = set()
    
    for cliente in clientes_encontrados:
        if cliente["id"] not in ids_vistos:
            ids_vistos.add(cliente["id"])
            clientes_unicos.append(cliente)
    
    return clientes_unicos

def obter_cliente_por_id(id_cliente):
    """Obtém informações do cliente pelo ID"""
    url = f"{IXC_HOST_API}/cliente"
    headers = get_ixc_headers()
    
    data = {
        "qtype": "id",
        "query": str(id_cliente),
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            return None
        
        try:
            dados = response.json()
        except:
            return None
        
        total = dados.get("total")
        if total is not None:
            if isinstance(total, str):
                try:
                    total_int = int(total)
                except ValueError:
                    total_int = 0
            else:
                total_int = int(total) if total else 0
            
            if total_int > 0:
                cliente = dados.get("registros", [])[0]
                return {
                    "id": cliente.get("id", ""),
                    "nome": cliente.get("razao") or cliente.get("fantasia") or "Nome não disponível",
                    "ativo": cliente.get("ativo", "N")
                }
    except Exception:
        pass
    
    return None

def buscar_cliente_ixc(telefone):
    """Busca cliente no IXC pelo telefone (segunda opção) - APENAS ATIVOS"""
    telefone_formatado = formatar_telefone_para_ixc(telefone)
    
    campos = ["whatsapp", "telefone_celular", "fone", "telefone_comercial"]
    clientes_encontrados = []
    
    for campo in campos:
        url = f"{IXC_HOST_API}/cliente"
        headers = get_ixc_headers()
        
        data = {
            "qtype": campo,
            "query": telefone_formatado,
            "oper": "=",
            "page": "1",
            "rp": "50"
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code != 200:
                continue
            
            try:
                dados = response.json()
            except:
                continue
            
            total = dados.get("total")
            if total is not None:
                if isinstance(total, str):
                    try:
                        total_int = int(total)
                    except ValueError:
                        total_int = 0
                else:
                    total_int = int(total) if total else 0
                
                if total_int > 0:
                    for cliente in dados.get("registros", []):
                        # VERIFICAÇÃO: Apenas clientes ATIVOS
                        if cliente.get("ativo") != "S":
                            continue
                        
                        cliente_info = {
                            "id": cliente.get("id", ""),
                            "nome": cliente.get("razao") or cliente.get("fantasia") or "Nome não disponível",
                            "telefone": telefone_formatado,
                            "telefone_original": telefone,
                            "ativo": cliente.get("ativo", "N")
                        }
                        if cliente_info["id"] and cliente_info not in clientes_encontrados:
                            clientes_encontrados.append(cliente_info)
        except Exception:
            continue
    
    # Remove duplicados por ID
    clientes_unicos = []
    ids_vistos = set()
    
    for cliente in clientes_encontrados:
        if cliente["id"] not in ids_vistos:
            ids_vistos.add(cliente["id"])
            clientes_unicos.append(cliente)
    
    return clientes_unicos

def buscar_cliente_por_telefone(telefone):
    """Busca cliente usando as duas estratégias: primeiro atendimentos automáticos, depois busca direta"""
    # VALIDAÇÃO: Verificar se o telefone é válido
    if not validar_telefone(telefone):
        logging.info(f"  ⚠ Telefone inválido para busca: '{telefone}'")
        return []
    
    logging.info(f"  Buscando cliente para telefone: {telefone}")
    
    # PRIMEIRA OPÇÃO: Buscar pelos atendimentos automáticos do dia
    clientes = buscar_cliente_por_atendimentos_automaticos(telefone)
    
    if clientes:
        logging.info(f"  ✓ Cliente encontrado via atendimentos automáticos: {len(clientes)}")
        return clientes
    
    # SEGUNDA OPÇÃO: Buscar pelo telefone diretamente (apenas ativos)
    logging.info(f"  Nenhum cliente encontrado via atendimentos automáticos, buscando direto...")
    clientes = buscar_cliente_ixc(telefone)
    
    return clientes

def verificar_atendimento_existente(id_cliente, data_ligacao, id_responsavel):
    """Verifica se existe algum atendimento para o cliente criado no dia atual"""
    try:
        data_ligacao_dt = datetime.strptime(data_ligacao, '%Y-%m-%d %H:%M:%S')
        data_hoje = data_ligacao_dt.strftime('%Y-%m-%d')
        
        # Definir intervalo do dia: 00:00:00 até 23:59:59
        inicio_dia = f"{data_hoje} 00:00:00"
        fim_dia = f"{data_hoje} 23:59:59"
        
        url = f"{IXC_HOST_API}/su_ticket"
        headers = get_ixc_headers()
        
        # Buscar atendimentos do dia para o cliente
        data = {
            "qtype": "id_cliente",
            "query": id_cliente,
            "oper": "=",
            "page": "1",
            "rp": "100"
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code != 200:
            logging.error(f"        Erro na resposta da API: {response.status_code}")
            return False
        
        try:
            dados = response.json()
        except:
            logging.error(f"        Erro ao decodificar JSON")
            return False
        
        total = dados.get("total")
        if total is not None:
            if isinstance(total, str):
                try:
                    total_int = int(total)
                except ValueError:
                    total_int = 0
            else:
                total_int = int(total) if total else 0
            
            if total_int > 0:
                logging.info(f"        Encontrados {total_int} atendimentos para o cliente")
                
                for atendimento in dados.get("registros", []):
                    data_criacao_str = atendimento.get("data_criacao", "")
                    
                    # Pular se a data de criação for inválida
                    if not data_criacao_str or data_criacao_str == "0000-00-00 00:00:00":
                        continue
                    
                    try:
                        # Verificar se o atendimento foi criado no dia atual
                        data_criacao = datetime.strptime(data_criacao_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Criar datas de início e fim do dia para comparação
                        inicio_dia_dt = datetime.strptime(inicio_dia, '%Y-%m-%d %H:%M:%S')
                        fim_dia_dt = datetime.strptime(fim_dia, '%Y-%m-%d %H:%M:%S')
                        
                        # Verificar se o atendimento foi criado no dia atual
                        if inicio_dia_dt <= data_criacao <= fim_dia_dt:
                            id_resp_tec = str(atendimento.get("id_responsavel_tecnico", ""))
                            
                            # Registrar informação do atendimento encontrado
                            logging.info(f"        Atendimento ID {atendimento.get('id')} criado em {data_criacao_str} por ID {id_resp_tec}")
                            
                            # Verificar se foi criado pelo mesmo responsável
                            if id_resp_tec == id_responsavel:
                                logging.info(f"        ✓ Atendimento do mesmo responsável encontrado para hoje!")
                                return True
                            else:
                                logging.info(f"        ⚠ Atendimento encontrado, mas de outro responsável (ID: {id_resp_tec})")
                        else:
                            logging.debug(f"        Atendimento fora do dia atual: {data_criacao_str}")
                    except Exception as e:
                        logging.error(f"        Erro ao processar data {data_criacao_str}: {e}")
                        continue
        
        logging.info(f"        Nenhum atendimento encontrado para hoje")
        return False
        
    except Exception as e:
        logging.error(f"      Erro ao verificar atendimento: {e}")
        return False

def criar_mensagem_alerta(atendente, clientes, data_hora_ligacao, telefone):
    """Cria a mensagem de alerta no formato padrão"""
    if len(clientes) == 1:
        return f"""🔴 FALTA DE REGISTRO 🔴

Atendente: {atendente}

- Cliente: {clientes[0]['id']} - {clientes[0]['nome']}
- Horário Ligação: {data_hora_ligacao}
- Telefone: {telefone}"""
    else:
        clientes_lista = "\n".join([f"   {c['id']} - {c['nome']}" for c in clientes])
        return f"""🔴 FALTA DE REGISTRO 🔴

Atendente: {atendente}

- Clientes: 
{clientes_lista}

- Horário Ligação: {data_hora_ligacao}
- Telefone: {telefone}"""

def enviar_alerta_telegram(atendente, clientes, data_hora_ligacao, telefone):
    """Envia alerta para o Telegram no formato especificado"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Token ou Chat ID do Telegram não configurado")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    mensagem = criar_mensagem_alerta(atendente, clientes, data_hora_ligacao, telefone)
    
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()
        logging.info(f"  ✅ Telegram: Alerta enviado")
        return True
    except Exception as e:
        logging.error(f"  ❌ Erro ao enviar alerta para o Telegram: {e}")
        return False

def enviar_alerta_whatsapp(atendente, clientes, data_hora_ligacao, telefone, ramal):
    """Envia alerta para o grupo correto do WhatsApp baseado no ramal"""
    
    # Definir quais ramais são do Comercial e quais são do Suporte/Demandas
    RAMAIS_COMERCIAL = ["1204", "1210", "1208", "1205", "1201"]
    RAMAIS_SUPORTE = ["4002", "4004", "4006", "4008", "4009", "4021", 
                      "4025", "4027", "4028", "4029", "4030", "4031", 
                      "4032", "4033"]
    
    # Determinar para qual grupo enviar baseado no ramal
    grupo_id = None
    
    if ramal in RAMAIS_COMERCIAL:
        grupo_id = WHATSAPP_GROUP_COMERCIAL
        grupo_nome = "Comercial"
    elif ramal in RAMAIS_SUPORTE:
        grupo_id = WHATSAPP_GROUP_DEMANDAS
        grupo_nome = "Suporte/Demandas"
    else:
        logging.warning(f"  ⚠️ Ramal {ramal} não está mapeado para nenhum grupo do WhatsApp")
        return False
    
    # Verificar se o grupo está configurado
    if not grupo_id:
        logging.warning(f"  ⚠️ Grupo do WhatsApp para {grupo_nome} não configurado")
        return False
    
    mensagem = criar_mensagem_alerta(atendente, clientes, data_hora_ligacao, telefone)
    
    logging.info(f"  📤 Tentando enviar para WhatsApp - Grupo {grupo_nome}")
    
    # Testar se o serviço está rodando
    try:
        health_response = requests.get(f"{WHATSAPP_SERVICE_URL}/health", timeout=5)
        if health_response.status_code != 200:
            logging.error(f"  ❌ Serviço WhatsApp não está saudável")
            return False
            
        health_data = health_response.json()
        if not health_data.get('whatsapp_ready', False):
            logging.error(f"  ❌ WhatsApp não está pronto (status: {health_data.get('status')})")
            return False
    except requests.exceptions.ConnectionError:
        logging.error(f"  ❌ Serviço WhatsApp não está rodando em {WHATSAPP_SERVICE_URL}")
        logging.error(f"  💡 Execute: pm2 start whatsapp_service.js --name whatsapp-falta-registro")
        return False
    except Exception as e:
        logging.error(f"  ❌ Erro ao verificar saúde do serviço: {e}")
        return False
    
    # Enviar mensagem
    try:
        response = requests.post(
            f"{WHATSAPP_SERVICE_URL}/send",
            json={
                "groupId": grupo_id,
                "message": mensagem
            },
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logging.info(f"  ✅ WhatsApp: Mensagem enviada para grupo {grupo_nome}")
                return True
            else:
                logging.error(f"  ❌ WhatsApp: Erro no envio: {result.get('error', 'Desconhecido')}")
                return False
        else:
            logging.error(f"  ❌ WhatsApp: HTTP {response.status_code}")
            logging.error(f"     Resposta: {response.text[:200]}")
            return False
            
    except requests.exceptions.Timeout:
        logging.error(f"  ❌ Timeout ao enviar para WhatsApp")
        return False
    except Exception as e:
        logging.error(f"  ❌ Erro ao enviar para WhatsApp: {e}")
        return False

def testar_autenticacao_ixc():
    """Testa a autenticação com a API do IXC"""
    url = f"{IXC_HOST_API}/cliente"
    headers = get_ixc_headers()
    
    data = {
        "qtype": "id",
        "query": "1",
        "oper": "=",
        "page": "1",
        "rp": "1"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            try:
                dados = response.json()
                logging.info(f"✓ Autenticação IXC OK - Total de registros: {dados.get('total', 0)}")
                return True
            except json.JSONDecodeError:
                logging.error("✗ Autenticação IXC: Resposta não é JSON válido")
                return False
        elif response.status_code == 401:
            logging.error("✗ Autenticação IXC: FALHA (401 Unauthorized)")
            return False
        else:
            logging.error(f"✗ Autenticação IXC: Código de status {response.status_code}")
            return False
    except Exception as e:
        logging.error(f"✗ Erro ao testar autenticação IXC: {e}")
        return False

def processar_ligacoes():
    """Processa todas as ligações desde a última execução"""
    logging.info("=" * 60)
    logging.info(f"EXECUÇÃO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)
    
    # Testa autenticação primeiro
    if not testar_autenticacao_ixc():
        logging.error("Não é possível continuar devido a falha na autenticação.")
        return
    
    # Obtém ligações desde a última execução
    dados_ligacoes = obter_ligacoes_desde_ultima_execucao()
    
    if not dados_ligacoes or dados_ligacoes.get("code") != 200:
        logging.error("Não foi possível obter ligações do Escallo")
        return
    
    registros = dados_ligacoes.get("data", {}).get("registros", [])
    logging.info(f"Novas ligações encontradas: {len(registros)}")
    
    if len(registros) == 0:
        logging.info("Nenhuma nova ligação desde a última execução.")
        # Salva o horário atual mesmo sem novas ligações
        salvar_ultima_data_hora()
        return
    
    # Filtra ligações dos atendentes específicos, ignorando a fila "Suporte - Técnicos"
    ligacoes_filtradas = []
    
    for ligacao in registros:
        status = ligacao.get("filaAtendimentoLigacao.statusFormatado", "")
        destino = ligacao.get("filaAtendimentoLigacao.destino", "")
        fila_nome = ligacao.get("telefoniaFilaAtendimento.nome", "")
        
        # Ignorar ligações da fila "Suporte - Técnicos"
        if fila_nome == "Suporte - Técnicos":
            logging.debug(f"Ignorando ligação da fila: {fila_nome}")
            continue

        # Ignorar ligações da fila "Comercial - Técnicos"
        if fila_nome == "Comercial - Técnicos":
            logging.debug(f"Ignorando ligação da fila: {fila_nome}")
            continue
        
        if status != "Atendida":
            continue
        
        ramal = extrair_ramal(destino)
        
        if ramal and ramal in ATENDENTES_FILTRO:
            # Usando dataHoraFinal
            data_hora_final = ligacao.get("filaAtendimentoLigacao.dataHoraFinal")
            
            if not data_hora_final:
                continue
            
            ligacoes_filtradas.append({
                "id": ligacao.get("filaAtendimentoLigacao.id"),
                "ramal": ramal,
                "nome_atendente": RAMAL_NOME_MAP.get(ramal, "Desconhecido"),
                "origem": ligacao.get("filaAtendimentoLigacao.origem"),
                "data_hora_final": data_hora_final,
                "destino": destino,
                "fila_nome": fila_nome
            })
    
    logging.info(f"Ligações filtradas dos atendentes: {len(ligacoes_filtradas)}")
    
    # Processa cada ligação filtrada
    for ligacao in ligacoes_filtradas:
        logging.info(f"\nProcessando ligação ID: {ligacao['id']}")
        logging.info(f"Atendente: {ligacao['nome_atendente']}")
        logging.info(f"Número: {ligacao['origem']}")
        logging.info(f"Data/hora final da ligação: {ligacao['data_hora_final']}")
        logging.info(f"Fila: {ligacao['fila_nome']}")
        
        # Busca cliente no IXC (usando as duas estratégias)
        clientes = buscar_cliente_por_telefone(ligacao['origem'])
        
        if not clientes:
            logging.info(f"  ✗ Nenhum cliente ATIVO encontrado no IXC para este telefone")
            continue
        
        logging.info(f"  ✓ Clientes ATIVOS encontrados: {len(clientes)}")
        
        # Obtém o ID do responsável a partir do ramal
        id_responsavel = RAMAL_RESPONSAVEL_MAP.get(ligacao['ramal'])
        
        if not id_responsavel:
            logging.warning(f"  ID do responsável não encontrado para o ramal {ligacao['ramal']}")
            continue
        
        logging.info(f"  ID do responsável mapeado: {id_responsavel}")
        
        # Verifica se já existe atendimento para algum dos clientes
        algum_atendimento_registrado = False
        
        for cliente in clientes:
            logging.info(f"    Verificando cliente: {cliente['nome']} (ID: {cliente['id']})")
            
            if verificar_atendimento_existente(cliente['id'], ligacao['data_hora_final'], id_responsavel):
                logging.info(f"    ✓ Atendimento registrado encontrado para este cliente")
                algum_atendimento_registrado = True
                break
        
        if not algum_atendimento_registrado:
            # Envia alerta para o Telegram
            sucesso_telegram = enviar_alerta_telegram(
                ligacao['nome_atendente'],
                clientes,
                ligacao['data_hora_final'],
                clientes[0]['telefone']
            )
            
            # Envia alerta para o WhatsApp
            sucesso_whatsapp = enviar_alerta_whatsapp(
                ligacao['nome_atendente'],
                clientes,
                ligacao['data_hora_final'],
                clientes[0]['telefone'],
                ligacao['ramal']
            )
            
            if sucesso_telegram or sucesso_whatsapp:
                logging.info(f"  ✓ Alerta(s) enviado(s) com sucesso")
            else:
                logging.error(f"  ✗ Falha ao enviar alertas")
        else:
            logging.info(f"  ✓ Atendimento encontrado - Sem alerta")
    
    # Salva o horário atual como última execução
    salvar_ultima_data_hora()
    
    logging.info("\n" + "=" * 60)
    logging.info("Execução concluída!")
    logging.info("=" * 60)

def limpar_arquivos_antigos():
    """Remove arquivos antigos se existirem"""
    arquivos_para_remover = ["cache_monitoramento.json", "log_monitoramento.txt"]
    
    for arquivo in arquivos_para_remover:
        if os.path.exists(arquivo):
            try:
                os.remove(arquivo)
                logging.info(f"Arquivo antigo removido: {arquivo}")
            except Exception as e:
                logging.error(f"Erro ao remover arquivo {arquivo}: {e}")

def main():
    """Função principal para execução contínua"""
    required_vars = [
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", 
        "IXC_TOKEN_API", "IXC_HOST_API",
        "ESCALLO_HOST", "ESCALLO_TOKEN"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        """ print(f"Variáveis de ambiente faltando: {', '.join(missing_vars)}")
        # print("Configure-as no arquivo .env") """
        return
    
    # Remove espaços em branco dos tokens
    global IXC_TOKEN_API, ESCALLO_TOKEN
    IXC_TOKEN_API = IXC_TOKEN_API.strip()
    ESCALLO_TOKEN = ESCALLO_TOKEN.strip()
    
    # Limpa arquivos antigos se existirem
    limpar_arquivos_antigos()
    
    # Verifica configuração do WhatsApp
    whatsapp_configurado = WHATSAPP_GROUP_COMERCIAL or WHATSAPP_GROUP_DEMANDAS
    if whatsapp_configurado:
        logging.info("✓ WhatsApp configurado - Alertas serão enviados")
    else:
        logging.info("⚠ WhatsApp não configurado - Apenas Telegram será usado")
    
    logging.info("=" * 60)
    logging.info("SISTEMA DE MONITORAMENTO DE ATENDIMENTOS")
    logging.info("Configurado para executar a cada 40 minutos")
    logging.info("=" * 60)
    
    # Loop principal (executa a cada 40 minutos)
    while True:
        try:
            processar_ligacoes()
            logging.info(f"Próxima execução em 40 minutos...")
            time.sleep(2400)  # 40 minutos em segundos (40 * 60 = 2400)
        except KeyboardInterrupt:
            logging.info("Sistema interrompido pelo usuário")
            break
        except Exception as e:
            logging.error(f"Erro inesperado: {e}")
            logging.info("Reiniciando em 60 segundos...")
            time.sleep(60)

if __name__ == "__main__":
    main()
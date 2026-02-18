import requests
import json
import time
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple
import os
from dotenv import load_dotenv

# ========== CARREGAR VARIÁVEIS DO .env ==========
load_dotenv()

# ========== CONFIGURAÇÕES ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
API_BASE_URL = "https://assinante.nmultifibra.com.br/webservice/v1"

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not AUTH_TOKEN:
    """ print("ERRO: Variáveis de ambiente não carregadas corretamente!") """
    exit(1)

# ========== HEADERS DAS REQUISIÇÕES ==========
HEADERS = {
    "Authorization": f"Basic {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "ixcsoft": "listar"
}

# ========== LISTA DE CLIENTES ==========
CLIENTES = [
    {"id": "125634", "razao": "ASSOCIACAO DE PAIS E MESTRES DA EE WILMAR SOARES DA SILVA"},
    {"id": "125549", "razao": "APM DA EE DOLORES GARCIA PASCHOALIN"},
    {"id": "125731", "razao": "Associacao de Pais e Mestres da Ee Prof Maria Soares Santos"},
    {"id": "125814", "razao": "Associacao de Pais e Mestres da Ee Profa Celina de Barros Bairao"},
    {"id": "125813", "razao": "Apm da E E Profa Ignes Amelia Oliveira Machado"},
    {"id": "125990", "razao": "Apm da Ee Prof Lenio Vieira de Moraes"},
    {"id": "125980", "razao": "Apm da E E Paulo de Abreu"},
    {"id": "125986", "razao": "Apm da Ee Padre Giuseppe Angelo Bertolli"},
    {"id": "126029", "razao": "Associacao de Pais e Mestres da e e Professora Terezinha Palone da Silva Domingues"},
    {"id": "126063", "razao": "Apm da Ee Prof Alayde Domingues Couto Macedo"},
    {"id": "104171", "razao": "APM DA EE JOAO BATISTA SOLDE"},
    {"id": "126487", "razao": "Apm da Ee Professor Jose Theotonio dos Santos"},
    {"id": "125362", "razao": "DIMARAES ANTONIO SANDEI PROFESSOR"},
    {"id": "98547", "razao": "Keneth Alves dos Santos"}
]

# ========== CONFIGURAÇÃO DE LOG ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_clientes.log'),
        logging.StreamHandler()
    ]
)

class ClienteMonitor:
    def __init__(self):
        self.sessao = requests.Session()
        self.sessao.headers.update(HEADERS)
        
        # Controles de estado
        self.estado_clientes = {}  # Armazena estado atual de cada cliente
        self.ultimo_alerta_offline = {}  # Último horário de alerta offline
        self.ultimo_alerta_online = {}  # Último horário de alerta online
        self.primeira_verificacao = True  # Flag para primeira execução
    
    def fazer_requisicao(self, endpoint: str, filtro: Dict) -> Optional[Dict]:
        """Faz uma requisição à API"""
        try:
            url = f"{API_BASE_URL}/{endpoint}"
            response = self.sessao.post(url, json=filtro, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Erro na requisição {endpoint}: {e}")
            return None
    
    def buscar_todos_logins_cliente(self, id_cliente: str) -> List[Dict]:
        """Busca TODOS os logins de um cliente"""
        filtro = {
            "qtype": "id_cliente",
            "query": id_cliente,
            "oper": "=",
            "page": "1",
            "rp": "100"
        }
        
        dados = self.fazer_requisicao("radusuarios", filtro)
        if dados and "registros" in dados and len(dados["registros"]) > 0:
            return dados["registros"]
        return []
    
    def verificar_status_cliente(self, logins: List[Dict]) -> Tuple[bool, Optional[Dict]]:
        """Verifica se algum login do cliente está offline
        Retorna: (cliente_offline, dados_login_offline)"""
        for login in logins:
            ativo = login.get("ativo", "N")
            online = login.get("online", "N")
            
            # Verifica se o login está ativo e offline
            if ativo == "S" and online == "N":
                return True, login
        
        # Se nenhum login ativo estiver offline, cliente está online
        return False, None
    
    def buscar_detalhes_fibra(self, id_login: str) -> Optional[Dict]:
        """Busca detalhes da fibra do cliente"""
        filtro = {
            "qtype": "id_login",
            "query": id_login,
            "oper": "=",
            "page": "1",
            "rp": "2"
        }
        dados = self.fazer_requisicao("radpop_radio_cliente_fibra", filtro)
        if dados and "registros" in dados and len(dados["registros"]) > 0:
            return dados["registros"][0]
        return None
    
    def buscar_nome_transmissor(self, id_transmissor: str) -> Optional[str]:
        """Busca o nome do transmissor"""
        if not id_transmissor or id_transmissor == "0":
            return None
        filtro = {
            "qtype": "id",
            "query": id_transmissor,
            "oper": "=",
            "page": "1",
            "rp": ""
        }
        dados = self.fazer_requisicao("radpop_radio", filtro)
        if dados and "registros" in dados and len(dados["registros"]) > 0:
            return dados["registros"][0].get("descricao", "")
        return None
    
    def formatar_motivo_desconexao(self, motivo: str) -> str:
        """Formata o motivo de desconexão com valor padrão se vazio"""
        if not motivo or motivo.strip() == "":
            return "Cliente sem Autenticação"
        return motivo.strip()
    
    def formatar_pon_info(self, nome_transmissor: Optional[str], ponid: str) -> str:
        """Formata a informação da PON com valor padrão se vazio"""
        if not ponid or ponid.strip() == "" or ponid == "0":
            ponid = ""
        if nome_transmissor and ponid:
            return f"{nome_transmissor} - {ponid}"
        elif nome_transmissor:
            return nome_transmissor
        elif ponid:
            return ponid
        else:
            return "SEM DESCRIÇÃO"
    
    def enviar_telegram(self, mensagem: str):
        """Envia mensagem para o Telegram"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": mensagem,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logging.info("Mensagem enviada ao Telegram com sucesso!")
                return True
            else:
                logging.error(f"Erro ao enviar Telegram: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Erro ao enviar mensagem Telegram: {e}")
            return False
    
    def deve_enviar_alerta_offline(self, cliente_id: str) -> bool:
        """Verifica se deve enviar alerta de offline"""
        agora = datetime.now()
        
        # Se é a primeira vez que o cliente fica offline
        if cliente_id not in self.ultimo_alerta_offline:
            return True
        
        ultimo = self.ultimo_alerta_offline[cliente_id]
        diferenca = agora - ultimo
        
        # Envia a cada 12 horas (43200 segundos)
        return diferenca.total_seconds() >= 43200
    
    def deve_enviar_alerta_online(self, cliente_id: str) -> bool:
        """Verifica se deve enviar alerta de online (quando cliente volta)"""
        agora = datetime.now()
        
        # Se é a primeira vez que o cliente fica online
        if cliente_id not in self.ultimo_alerta_online:
            return True
        
        ultimo = self.ultimo_alerta_online[cliente_id]
        diferenca = agora - ultimo
        
        # Envia imediatamente quando cliente volta
        return diferenca.total_seconds() >= 0  # Sempre verdadeiro se cliente voltou
    
    def processar_cliente(self, cliente: Dict):
        """Processa um cliente específico com nova lógica"""
        cliente_id = cliente["id"]
        razao = cliente["razao"]
        
        # Busca TODOS os logins do cliente
        todos_logins = self.buscar_todos_logins_cliente(cliente_id)
        if not todos_logins:
            logging.error(f"Cliente {cliente_id} não encontrado!")
            return
        
        logging.info(f"Cliente {cliente_id} possui {len(todos_logins)} logins")
        
        # Verifica se algum login ativo está offline
        cliente_offline, login_offline = self.verificar_status_cliente(todos_logins)
        
        # Estado anterior do cliente
        estado_anterior = self.estado_clientes.get(cliente_id, {"online": None, "ultima_verificacao": None})
        
        # Atualiza estado atual
        estado_atual = "N" if cliente_offline else "S"
        self.estado_clientes[cliente_id] = {
            "online": estado_atual,
            "ultima_verificacao": datetime.now()
        }
        
        # Se cliente tem algum login offline
        if cliente_offline and login_offline:
            logging.info(f"Cliente {cliente_id} está OFFLINE (login: {login_offline.get('login', 'N/A')})")
            
            # Extrai informações do login offline
            id_login = login_offline.get("id", "")
            motivo_desconexao = login_offline.get("motivo_desconexao", "")
            ultima_conexao = login_offline.get("ultima_conexao_inicial", "")
            
            # Formata o motivo de desconexão
            motivo_desconexao_formatado = self.formatar_motivo_desconexao(motivo_desconexao)
            
            # Verifica se deve enviar alerta
            if self.deve_enviar_alerta_offline(cliente_id):
                # Busca detalhes da fibra apenas se for enviar alerta
                detalhes_fibra = self.buscar_detalhes_fibra(id_login)
                
                if detalhes_fibra:
                    id_transmissor = detalhes_fibra.get("id_transmissor", "")
                    ponid = detalhes_fibra.get("ponid", "")
                    nome_transmissor = self.buscar_nome_transmissor(id_transmissor)
                    pon_formatada = self.formatar_pon_info(nome_transmissor, ponid)
                else:
                    pon_formatada = "SEM DESCRIÇÃO"
                
                # Monta e envia mensagem
                mensagem = (
                    f"❌ Problema: {motivo_desconexao_formatado}\n"
                    f"Horario: {ultima_conexao}\n"
                    f"PON: {pon_formatada}\n"
                    f"Login: {login_offline.get('login', 'N/A')}\n\n"
                    f"Cliente: {cliente_id} - {razao}"
                )
                
                if self.enviar_telegram(mensagem):
                    self.ultimo_alerta_offline[cliente_id] = datetime.now()
                    logging.info(f"Alerta OFFLINE enviado para cliente {cliente_id}")
            else:
                # Verifica se o cliente ainda está offline (para logs apenas)
                tempo_desde_ultimo_alerta = datetime.now() - self.ultimo_alerta_offline.get(cliente_id, datetime.now())
                horas = tempo_desde_ultimo_alerta.total_seconds() / 3600
                logging.info(f"Cliente {cliente_id} ainda OFFLINE. Último alerta há {horas:.1f} horas. Próximo em {12 - horas:.1f} horas.")
        
        # Cliente ONLINE (nenhum login ativo offline)
        elif not cliente_offline:
            logging.info(f"Cliente {cliente_id} está ONLINE (todos logins online)")
            
            # Verifica se o cliente estava offline anteriormente
            if estado_anterior["online"] == "N":
                # Cliente voltou a ficar ONLINE
                logging.info(f"Cliente {cliente_id} voltou a ficar ONLINE!")
                
                # Pega o primeiro login ativo para obter informações da PON
                login_ativo = None
                for login in todos_logins:
                    if login.get("ativo", "N") == "S":
                        login_ativo = login
                        break
                
                if login_ativo:
                    id_login = login_ativo.get("id", "")
                    
                    # Busca detalhes da fibra
                    detalhes_fibra = self.buscar_detalhes_fibra(id_login)
                    
                    if detalhes_fibra:
                        id_transmissor = detalhes_fibra.get("id_transmissor", "")
                        ponid = detalhes_fibra.get("ponid", "")
                        nome_transmissor = self.buscar_nome_transmissor(id_transmissor)
                        pon_formatada = self.formatar_pon_info(nome_transmissor, ponid)
                    else:
                        pon_formatada = "SEM DESCRIÇÃO"
                    
                    # Monta e envia mensagem de retorno
                    mensagem = (
                        f"✅ Cliente voltou a ficar ONLINE\n"
                        f"PON: {pon_formatada}\n\n"
                        f"Cliente: {cliente_id} - {razao}"
                    )
                    
                    if self.enviar_telegram(mensagem):
                        self.ultimo_alerta_online[cliente_id] = datetime.now()
                        self.ultimo_alerta_offline.pop(cliente_id, None)  # Remove alerta offline
                        logging.info(f"Alerta de RETORNO ONLINE enviado para cliente {cliente_id}")
            else:
                # Cliente já estava online, apenas registra no log
                logging.info(f"Cliente {cliente_id} continua ONLINE")
    
    def monitorar_clientes(self):
        """Monitora todos os clientes"""
        logging.info("=" * 60)
        logging.info("INICIANDO CICLO DE MONITORAMENTO")
        logging.info("=" * 60)
        
        for cliente in CLIENTES:
            try:
                logging.info(f"Processando cliente: {cliente['id']} - {cliente['razao']}")
                self.processar_cliente(cliente)
                time.sleep(1)  # Pausa curta entre requisições
            except Exception as e:
                logging.error(f"Erro ao processar cliente {cliente['id']}: {e}")
        
        # Primeira verificação concluída
        if self.primeira_verificacao:
            self.primeira_verificacao = False
            logging.info("Primeira verificação concluída. Estado inicial dos clientes registrado.")
        
        logging.info("=" * 60)
        logging.info("CICLO DE MONITORAMENTO CONCLUÍDO")
        logging.info(f"Próxima verificação em 10 minutos")
        logging.info("=" * 60)
    
    def iniciar_monitoramento(self):
        """Inicia o monitoramento em loop"""
        logging.info("INICIANDO SISTEMA DE MONITORAMENTO")
        logging.info(f"Total de clientes: {len(CLIENTES)}")
        logging.info(f"Verificação a cada: 10 minutos")
        logging.info(f"Alertas offline: A cada 12 horas se continuar offline")
        logging.info(f"Alertas online: Imediato quando cliente voltar")
        
        while True:
            try:
                self.monitorar_clientes()
                # Aguarda 10 minutos para próxima verificação
                logging.info("Aguardando 10 minutos para próxima verificação...")
                time.sleep(600)  # 600 segundos = 10 minutos
            except KeyboardInterrupt:
                logging.info("Monitoramento interrompido pelo usuário.")
                break
            except Exception as e:
                logging.error(f"Erro no loop principal: {e}")
                time.sleep(60)  # Espera 1 minuto em caso de erro

def main():
    """Função principal"""
    """ print("=" * 60)
    # print("SISTEMA DE MONITORAMENTO DE CLIENTES")
    # print("=" * 60)
    # print(f"Total de clientes: {len(CLIENTES)}")
    # print(f"Verificação a cada: 10 minutos")
    # print(f"Alertas offline: A cada 12 horas se continuar offline")
    # print(f"Alertas online: Imediato quando cliente voltar")
    # print("=" * 60) """
    
    if not TELEGRAM_BOT_TOKEN:
        """ print("ERRO: Configure o token do bot do Telegram!") """
        return
    
    if not TELEGRAM_CHAT_ID:
        """ print("ERRO: Configure o Chat ID do Telegram!") """
        return
    
    if not AUTH_TOKEN:
        """ print("ERRO: Configure o token de autenticação da API!") """
        return
    
    monitor = ClienteMonitor()
    monitor.iniciar_monitoramento()

if __name__ == "__main__":
    main()
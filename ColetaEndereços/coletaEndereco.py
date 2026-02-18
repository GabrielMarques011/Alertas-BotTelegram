import asyncio
import logging
import re
import os
import json
from typing import Dict, List, Optional, Tuple
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import requests
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurações da API IXC
IXC_BASE_URL = "https://assinante.nmultifibra.com.br/webservice/v1"
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")

# Configuração do Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Estados da conversa
REQUEST_PON = 1

# Headers para requisições IXC
HEADERS = {
    "Authorization": f"Basic {AUTH_TOKEN}",
    "Content-Type": "application/json",
    "ixcsoft": "listar"
}

class IXCClient:
    """Cliente para interagir com a API do IXC"""
    
    @staticmethod
    def get_transmissores() -> List[Dict]:
        url = f"{IXC_BASE_URL}/radpop_radio"
        payload = {
            "qtype": "",
            "query": "",
            "oper": "=",
            "page": "1",
            "rp": "999"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("registros", [])
        except Exception as e:
            logger.error(f"Erro ao buscar transmissores: {e}")
            return []
    
    @staticmethod
    def get_clientes_pon(id_transmissor: str, pon: str) -> List[Dict]:
        url = f"{IXC_BASE_URL}/radpop_radio_cliente_fibra"
        payload = {
            "qtype": "ponid",
            "query": pon,
            "oper": "=",
            "page": "1",
            "rp": "9999"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            clientes = data.get("registros", [])
            return [c for c in clientes if str(c.get("id_transmissor")) == str(id_transmissor)]
        except Exception as e:
            logger.error(f"Erro ao buscar clientes da PON {pon}: {e}")
            return []
    
    @staticmethod
    def get_contrato(id_contrato: str) -> Optional[Dict]:
        url = f"{IXC_BASE_URL}/cliente_contrato"
        payload = {
            "qtype": "id",
            "query": id_contrato,
            "oper": "=",
            "page": "1",
            "rp": "1"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            registros = data.get("registros", [])
            return registros[0] if registros else None
        except Exception as e:
            logger.error(f"Erro ao buscar contrato {id_contrato}: {e}")
            return None
    
    @staticmethod
    def get_cliente(id_cliente: str) -> Optional[Dict]:
        url = f"{IXC_BASE_URL}/cliente"
        payload = {
            "qtype": "id",
            "query": id_cliente,
            "oper": "=",
            "page": "1",
            "rp": "1"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            registros = data.get("registros", [])
            return registros[0] if registros else None
        except Exception as e:
            logger.error(f"Erro ao buscar cliente {id_cliente}: {e}")
            return None
    
    @staticmethod
    def get_cidade(id_cidade: str) -> Optional[str]:
        url = f"{IXC_BASE_URL}/cidade"
        payload = {
            "qtype": "id",
            "query": id_cidade,
            "oper": "=",
            "page": "1",
            "rp": "1"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            registros = data.get("registros", [])
            return registros[0].get("nome") if registros else None
        except Exception as e:
            logger.error(f"Erro ao buscar cidade {id_cidade}: {e}")
            return None
    
    @staticmethod
    def get_status_login(id_login: str) -> Optional[str]:
        """Retorna o status online ('S', 'N', 'SS') de um login"""
        url = f"{IXC_BASE_URL}/radusuarios"
        payload = {
            "qtype": "id",
            "query": id_login,
            "oper": "=",
            "page": "1",
            "rp": "1"
        }
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=30)
            response.raise_for_status()
            data = response.json()
            registros = data.get("registros", [])
            if registros:
                return registros[0].get("online")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar status do login {id_login}: {e}")
            return None


class EnderecoCollector:
    """Coletor de endereços"""
    
    def __init__(self):
        self.ixc = IXCClient()
        self.transmissores_cache = None
        self.transmissores_map = {}
    
    def load_transmissores(self):
        if self.transmissores_cache is None:
            logger.info("Carregando transmissores...")
            self.transmissores_cache = self.ixc.get_transmissores()
            if not self.transmissores_cache:
                logger.warning("Nenhum transmissor encontrado!")
                return False
            for t in self.transmissores_cache:
                descricao = t.get("descricao", "").strip()
                if descricao:
                    self.transmissores_map[descricao] = str(t.get("id"))
                    self.transmissores_map[descricao.upper()] = str(t.get("id"))
            logger.info(f"Transmissores carregados: {len(self.transmissores_cache)} encontrados")
        return True
    
    def parse_input(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        try:
            separators = ['-', ':', '–']
            for sep in separators:
                if sep in text:
                    parts = text.split(sep, 1)
                    break
            else:
                parts = text.rsplit(' ', 1)
            if len(parts) < 2:
                return None, None
            transmissor = parts[0].strip()
            pon = parts[1].strip()
            if not re.match(r'^\d+/\d+/\d+(/\d+)?$', pon):
                return None, None
            return transmissor, pon
        except Exception as e:
            logger.error(f"Erro ao parsear entrada '{text}': {e}")
            return None, None
    
    def get_endereco_completo(self, contrato: Dict) -> Tuple[str, str, str, str]:
        endereco_contrato = contrato.get("endereco", "").strip()
        numero_contrato = contrato.get("numero", "").strip()
        bairro_contrato = contrato.get("bairro", "").strip()
        cidade_id_contrato = str(contrato.get("cidade", "")).strip()
        
        cliente_id = contrato.get("id_cliente")
        cliente_data = None
        if cliente_id:
            cliente_data = self.ixc.get_cliente(str(cliente_id))
        
        endereco = ""
        numero = ""
        bairro = ""
        cidade_id = ""
        
        if cliente_data:
            endereco = cliente_data.get("endereco", "").strip()
            numero = cliente_data.get("numero", "").strip()
            bairro = cliente_data.get("bairro", "").strip()
            cidade_id = str(cliente_data.get("cidade", "")).strip()
            
            if not endereco and endereco_contrato:
                endereco = endereco_contrato
            if not numero and numero_contrato:
                numero = numero_contrato
            if not bairro and bairro_contrato:
                bairro = bairro_contrato
            if not cidade_id or cidade_id == "0":
                cidade_id = cidade_id_contrato if cidade_id_contrato != "0" else ""
        else:
            endereco = endereco_contrato
            numero = numero_contrato
            bairro = bairro_contrato
            cidade_id = cidade_id_contrato
        
        cidade_nome = ""
        if cidade_id and cidade_id != "0":
            cidade_nome = self.ixc.get_cidade(cidade_id) or ""
        
        return endereco, numero, bairro, cidade_nome
    
    def format_endereco(self, id_cliente: str, endereco: str, 
                        numero: str, bairro: str, cidade: str = "") -> str:
        parts = []
        if not endereco and not numero:
            if bairro:
                return f"{id_cliente} - {bairro}"
            elif cidade:
                return f"{id_cliente} - {cidade}"
            else:
                return f"{id_cliente} - Endereço não encontrado"
        if endereco:
            parts.append(endereco)
        if numero:
            parts.append(f", {numero}")
        linha = f"{id_cliente} - {''.join(parts)}" if parts else str(id_cliente)
        if bairro:
            linha += f" - {bairro}"
        if cidade:
            linha += f" - {cidade}"
        return linha
    
    async def coletar_enderecos(self, transmissor_desc: str, pon: str, filter_offline: bool = False) -> List[str]:
        logger.info(f"Iniciando coleta para {transmissor_desc} - {pon} (offline={filter_offline})")
        
        if not self.load_transmissores():
            return ["❌ Erro ao carregar transmissores. Verifique a conexão com a API."]
        
        transmissor_id = self.transmissores_map.get(transmissor_desc)
        if not transmissor_id:
            transmissor_id = self.transmissores_map.get(transmissor_desc.upper())
        if not transmissor_id:
            for key in self.transmissores_map.keys():
                if transmissor_desc.upper() in key.upper():
                    transmissor_id = self.transmissores_map[key]
                    break
        if not transmissor_id:
            return [f"❌ Transmissor '{transmissor_desc}' não encontrado!"]
        
        clientes = self.ixc.get_clientes_pon(transmissor_id, pon)
        if not clientes:
            return [f"❌ Nenhum cliente encontrado para PON {pon} no transmissor {transmissor_desc}"]
        
        logger.info(f"Encontrados {len(clientes)} clientes na PON {pon}")
        
        # Filtro offline (se ativado)
        if filter_offline:
            ids_login = [c.get("id_login") for c in clientes if c.get("id_login")]
            if not ids_login:
                return ["ℹ️ Nenhum cliente com id_login encontrado."]
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(None, self.ixc.get_status_login, str(id_log)) for id_log in ids_login]
            status_list = await asyncio.gather(*tasks)
            cliente_status = {ids_login[i]: status_list[i] for i in range(len(ids_login))}
            clientes_filtrados = [c for c in clientes if c.get("id_login") and cliente_status.get(c["id_login"]) in ("N", "SS")]
            clientes = clientes_filtrados
            if not clientes:
                return ["ℹ️ Nenhum cliente offline encontrado nesta PON."]
        
        # Processamento dos endereços com filtro de status
        enderecos = []
        ignorados_status = 0
        for cliente in clientes:
            id_contrato = cliente.get("id_contrato")
            if not id_contrato:
                continue
            contrato = self.ixc.get_contrato(str(id_contrato))
            if not contrato:
                continue
            # Verifica se o contrato está ativo
            if contrato.get("status") != "A":
                ignorados_status += 1
                continue
            id_cliente = contrato.get("id_cliente")
            if not id_cliente:
                continue
            endereco, numero, bairro, cidade = self.get_endereco_completo(contrato)
            linha = self.format_endereco(str(id_cliente), endereco, numero, bairro, cidade)
            enderecos.append(linha)
        
        if not enderecos:
            if ignorados_status > 0:
                return [f"ℹ️ Nenhum cliente ativo encontrado. {ignorados_status} clientes ignorados por status não ativo."]
            else:
                return ["ℹ️ Nenhum endereço encontrado para os clientes desta PON."]
        
        logger.info(f"Coleta concluída: {len(enderecos)} endereços, {ignorados_status} ignorados por status.")
        return enderecos


# Instância global do coletor
collector = EnderecoCollector()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bem-vindo ao coletor de endereços!\n"
        "Digite /enderecos para todos os endereços ou /offline para apenas offlines."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Comandos disponíveis:\n"
        "/start - Inicia o bot\n"
        "/enderecos - Coleta todos os endereços de uma PON\n"
        "/offline - Coleta apenas endereços de clientes offline\n"
        "/help - Mostra esta mensagem\n"
        "/cancel - Cancela operação em andamento\n\n"
        "📝 Formato para busca:\n"
        "`OLT_TRMS_01 - 0/15/12`\n"
        "(Transmissor - PON)\n\n"
        "📍 A PON deve estar no formato: 0/15/12 ou 0/15/12/0"
    )


async def enderecos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia coleta de todos os endereços"""
    context.user_data['filter_offline'] = False
    await update.message.reply_text(
        "📋 Me informe o Transmissor e a PON (todos os endereços):\n\n"
        "📝 Formato: `OLT_TRMS_01 - 0/15/12`"
    )
    return REQUEST_PON


async def offline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia coleta apenas de clientes offline"""
    context.user_data['filter_offline'] = True
    await update.message.reply_text(
        "📋 Me informe o Transmissor e a PON (apenas offlines):\n\n"
        "📝 Formato: `OLT_TRMS_01 - 0/15/12`"
    )
    return REQUEST_PON


async def receive_pon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    transmissor, pon = collector.parse_input(user_input)
    
    if not transmissor or not pon:
        await update.message.reply_text(
            "❌ Formato inválido!\n"
            "Use: TRANSMISSOR - PON (ex: OLT_TRMS_01 - 0/15/12)\n\n"
            "Tente novamente:"
        )
        return REQUEST_PON
    
    filter_offline = context.user_data.get('filter_offline', False)
    
    processing_msg = await update.message.reply_text(
        f"🔍 Buscando endereços{' (offlines)' if filter_offline else ''} para {transmissor} - {pon}...\n"
        "⏳ Isso pode levar alguns segundos..."
    )
    
    try:
        enderecos = await collector.coletar_enderecos(transmissor, pon, filter_offline)
        
        if len(enderecos) == 1 and (enderecos[0].startswith("❌") or enderecos[0].startswith("ℹ️")):
            await processing_msg.edit_text(enderecos[0])
            return ConversationHandler.END
        
        total = len(enderecos)
        if filter_offline:
            cabecalho = f"📍 Endereços de clientes offline ({total}):\n\n"
        else:
            cabecalho = f"📍 Endereços encontrados ({total}):\n\n"
        
        resposta_completa = cabecalho + "\n".join(enderecos)
        
        # Divisão por limite de caracteres
        if len(resposta_completa) <= 4000:
            await processing_msg.edit_text(resposta_completa)
            await update.message.reply_text(f"✅ Busca concluída! Total: {total} endereços.")
        else:
            partes = []
            parte_atual = cabecalho
            for endereco in enderecos:
                if len(parte_atual) + len(endereco) + 1 > 4000:
                    partes.append(parte_atual)
                    parte_atual = ""
                parte_atual += endereco + "\n"
            if parte_atual:
                partes.append(parte_atual)
            
            await processing_msg.edit_text(partes[0])
            for i in range(1, len(partes)):
                await asyncio.sleep(0.3)
                await update.message.reply_text(partes[i].strip())
            await update.message.reply_text(f"✅ Busca concluída! Total: {total} endereços.")
        
        # Log opcional
        if TELEGRAM_CHAT_ID:
            try:
                app = context.application
                tipo = "offlines" if filter_offline else "todos"
                await app.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"📊 Relatório de coleta ({tipo}):\n"
                         f"Usuário: {update.effective_user.username or update.effective_user.id}\n"
                         f"Transmissor: {transmissor}\n"
                         f"PON: {pon}\n"
                         f"Endereços encontrados: {total}"
                )
            except Exception as e:
                logger.error(f"Erro ao enviar log para chat_id: {e}")
        
    except Exception as e:
        logger.error(f"Erro na coleta: {e}")
        await processing_msg.edit_text(f"❌ Ocorreu um erro durante a coleta:\n{str(e)}")
    
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operação cancelada.")
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Erro não tratado: {context.error}")
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado.\n"
            "Por favor, tente novamente mais tarde."
        )


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN não configurado no arquivo .env")
        return
    if not AUTH_TOKEN:
        logger.error("❌ AUTH_TOKEN não configurado no arquivo .env")
        return
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_error_handler(error_handler)
    
    # ConversationHandler para os dois comandos (ambos levam ao mesmo estado REQUEST_PON)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('enderecos', enderecos_command),
            CommandHandler('offline', offline_command)
        ],
        states={
            REQUEST_PON: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pon)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    
    # Handler para mensagens não reconhecidas
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                          lambda update, context: update.message.reply_text(
                                              "Digite /help para ver os comandos disponíveis.")))
    
    logger.info("🤖 Bot iniciado! Aguardando comandos...")
    """ print("=" * 50)
    # print("🤖 BOT DE COLETA DE ENDEREÇOS INICIADO")
    # print(f"📱 Token do Telegram: {'✓' if TELEGRAM_BOT_TOKEN else '✗'}")
    # print(f"🔑 Token da API IXC: {'✓' if AUTH_TOKEN else '✗'}")
    # print(f"📊 Chat ID para logs: {TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else 'Não configurado'}")
    # print("=" * 50) """
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
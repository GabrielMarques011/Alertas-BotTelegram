import requests
import os
from dotenv import load_dotenv

load_dotenv()

def testar_envio():
    WHATSAPP_SERVICE_URL = os.getenv('WHATSAPP_SERVICE_URL', 'http://localhost:7575')
    WHATSAPP_GROUP_DEMANDAS = os.getenv('WHATSAPP_GROUP_ID_DEMANDAS')
    
    """ print("🧪 Testando envio de alerta...") """
    
    if not WHATSAPP_GROUP_DEMANDAS:
        """ print("❌ Grupo WhatsApp não configurado no .env") """
        return
    
    # Mensagem de teste
    mensagem = """🔴 FALTA DE REGISTRO 🔴

Atendente: João Silva (Teste)

- Cliente: 12345 - Cliente de Teste Ltda
- Horário Ligação: 2024-01-31 14:30:00
- Telefone: (11) 99999-9999

⚠️ Esta é uma mensagem de teste do sistema."""
    
    try:
        """ print(f"📤 Enviando para grupo Demandas: {WHATSAPP_GROUP_DEMANDAS}")
        print(f"📡 Serviço: {WHATSAPP_SERVICE_URL}") """
        
        # Primeiro, verificar saúde do serviço
        """ print("\n🔍 Verificando saúde do serviço...") """
        health_response = requests.get(f"{WHATSAPP_SERVICE_URL}/health", timeout=5)
        """ print(f"✅ Health check: {health_response.status_code}")
        print(f"📊 Dados: {health_response.json()}") """
        
        # Agora enviar a mensagem
        """ print("\n📤 Enviando mensagem...") """
        response = requests.post(
            f"{WHATSAPP_SERVICE_URL}/send",
            json={
                "groupId": WHATSAPP_GROUP_DEMANDAS,
                "message": mensagem
            },
            timeout=10
        )
        
        """ print(f"✅ Status: {response.status_code}")
        print(f"📊 Resposta: {response.json()}") """
        
        if response.status_code == 200 and response.json().get('success'):
            """ print("\n🎉 Teste concluído com SUCESSO! A mensagem foi enviada para o WhatsApp.") """
        else:
            """ print("\n❌ Houve um problema no envio.") """
        
    except requests.exceptions.ConnectionError:
        """ print("\n❌ Não foi possível conectar ao WhatsApp Service.")
        print(f"💡 Certifique-se de que o serviço está rodando em: {WHATSAPP_SERVICE_URL}")
        print("💡 Execute: node whatsapp_service.js") """
    except Exception as e:
        """ print(f"\n❌ Erro: {e}") """

if __name__ == "__main__":
    testar_envio()
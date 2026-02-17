# 🤖 Alertas-BotTelegram

> Sistema de automação em Python para monitorar métricas e dados coletados via API, enviando alertas inteligentes para grupos no Telegram.

---

## 📋 Sobre o Projeto

O **Alertas-BotTelegram** é um conjunto de automações desenvolvidas em **Python** que integra uma API de sistema de suporte ao **Bot API do Telegram**. Diferente de uma solução monolítica, o projeto é organizado em **módulos independentes**, cada um responsável por um tipo específico de monitoramento ou coleta de dados.

O sistema foi construído para equipes de suporte técnico e atendimento, automatizando notificações que antes dependiam de verificação manual, reduzindo o tempo de resposta e centralizando alertas diretamente nos grupos de trabalho no Telegram.

---

## 🗂️ Estrutura do Projeto

```
Alertas-BotTelegram/
│
├── AgendamentosAbertos/               # Monitora e alerta sobre agendamentos em aberto
│
├── AlertaAlteraçãoOS/                 # Detecta e notifica alterações em Ordens de Serviço (OS)
│
├── ColetaEndereços/                   # Coleta e processa dados de endereços via API
│
├── MonitoramentoClientes/             # Monitora status e métricas relacionadas a clientes
│
├── MonitoramentoRegistroAtendimento/  # Acompanha registros e histórico de atendimentos
│
└── README.md                          # Documentação do projeto
```

Cada pasta representa um **módulo autônomo** com seu próprio script Python, podendo ser executado de forma independente ou em conjunto, agendado via `cron` ou similar.

---

## 🧩 Módulos

### 📅 AgendamentosAbertos
Consulta a API do sistema de suporte em busca de agendamentos que ainda estão em aberto (sem data de conclusão ou pendentes de execução). Envia uma mensagem formatada ao grupo do Telegram com a listagem atual, permitindo que a equipe visualize rapidamente a fila de trabalho.

### 🔄 AlertaAlteraçãoOS
Monitora Ordens de Serviço (OS) e detecta quando há alterações de status, responsável, prioridade ou qualquer outro campo relevante. Ao identificar uma mudança, dispara imediatamente um alerta no Telegram com os detalhes da OS alterada, garantindo que a equipe seja notificada em tempo real.

### 📍 ColetaEndereços
Realiza a coleta e o processamento de dados de endereços retornados pela API. Pode ser utilizado para enriquecer informações de chamados, validar localizações ou gerar relatórios geográficos de atendimentos.

### 👥 MonitoramentoClientes
Acompanha métricas e o status de clientes cadastrados no sistema de suporte. Identifica situações de risco ou de atenção (como clientes com múltiplos chamados abertos, SLA em risco, etc.) e envia alertas proativos ao grupo responsável.

### 📝 MonitoramentoRegistroAtendimento
Monitora os registros de atendimento realizados pela equipe, verificando se os técnicos estão registrando suas atividades corretamente dentro dos prazos estabelecidos. Gera notificações sobre pendências de registro ou inconsistências no histórico de atendimento.

---

## 🚀 Como Rodar o Projeto

### Pré-requisitos

- Python **3.8** ou superior
- `pip` para instalação de dependências
- Um **Bot do Telegram** criado via [@BotFather](https://t.me/BotFather)
- O bot adicionado como **administrador** nos grupos de destino
- Acesso à **API do sistema de suporte** com as credenciais necessárias

### Criando o Bot no Telegram

1. Abra o Telegram e acesse [@BotFather](https://t.me/BotFather)
2. Envie o comando `/newbot` e siga as instruções
3. Ao final, você receberá o **Token do Bot** — guarde-o com segurança
4. Adicione o bot ao grupo desejado e promova-o a administrador
5. Para obter o **Chat ID** do grupo, use a URL abaixo substituindo `SEU_TOKEN`:

```
https://api.telegram.org/botSEU_TOKEN/getUpdates
```

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/GabrielMarques011/Alertas-BotTelegram.git

# 2. Entre na pasta do projeto
cd Alertas-BotTelegram

# 3. (Recomendado) Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 4. Instale as dependências de cada módulo
pip install -r requirements.txt
```

> Caso não haja um `requirements.txt` global, instale as dependências dentro de cada pasta de módulo individualmente.

### Configuração

Em cada módulo, configure as variáveis de ambiente ou o arquivo de configuração com:

```python
TELEGRAM_BOT_TOKEN = "SEU_TOKEN_AQUI"
TELEGRAM_CHAT_ID   = "-100XXXXXXXXXX"   # ID do grupo (negativo para grupos)
API_BASE_URL       = "https://sua-api.exemplo.com"
API_TOKEN          = "SEU_TOKEN_DA_API"
```

### Execução

```bash
# Executar um módulo específico
python AgendamentosAbertos/main.py

# Executar o monitoramento de OS
python "AlertaAlteraçãoOS/main.py"

# Executar o monitoramento de clientes
python MonitoramentoClientes/main.py
```

---

## ⏰ Agendamento Automático

Para que os módulos rodem automaticamente em intervalos regulares, utilize o `cron` (Linux/macOS) ou o **Agendador de Tarefas** (Windows).

### Exemplo com cron (Linux/macOS)

```bash
# Abrir o editor do cron
crontab -e

# Exemplos de agendamento:
# Verificar agendamentos abertos a cada 30 minutos
*/30 * * * * /usr/bin/python3 /caminho/AgendamentosAbertos/main.py

# Monitorar alterações de OS a cada 5 minutos
*/5 * * * * /usr/bin/python3 /caminho/AlertaAlteraçãoOS/main.py

# Monitorar clientes diariamente às 8h
0 8 * * * /usr/bin/python3 /caminho/MonitoramentoClientes/main.py
```

### Execução contínua com PM2 (Node.js)

```bash
npm install -g pm2

pm2 start AgendamentosAbertos/main.py --interpreter python3 --name "agendamentos"
pm2 start MonitoramentoClientes/main.py --interpreter python3 --name "clientes"
pm2 startup && pm2 save
```

---

## 📦 Dependências Principais

| Pacote | Descrição |
|--------|-----------|
| `python-telegram-bot` | Biblioteca oficial para interagir com a Telegram Bot API |
| `requests` | Realiza as requisições HTTP para a API do sistema de suporte |
| `python-dotenv` | Carrega variáveis de ambiente a partir de um arquivo `.env` |
| `schedule` *(provável)* | Agendamento de tarefas em Python sem necessidade de cron |

> Verifique os arquivos `requirements.txt` em cada módulo para a lista completa e versões exatas.

---

## 🔒 Boas Práticas de Segurança

- **Nunca** commite tokens ou credenciais no repositório
- Utilize um arquivo `.env` na raiz de cada módulo e adicione-o ao `.gitignore`:

```env
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_CHAT_ID=-100xxxxxxxxxx
API_TOKEN=sua_chave_api
API_BASE_URL=https://sua-api.com
```

```bash
# .gitignore
.env
__pycache__/
*.pyc
venv/
```

---

## 🌐 Linguagens Utilizadas

| Linguagem | Proporção |
|-----------|-----------|
| Python | 97.1% |
| JavaScript | 2.8% |
| Outros | 0.1% |

O núcleo do sistema é inteiramente em Python. Os arquivos JavaScript presentes provavelmente são scripts auxiliares ou de configuração.

---

## 👤 Autor

**Gabriel Marques**
- GitHub: [@GabrielMarques011](https://github.com/GabrielMarques011)

---

## 📄 Licença

Este projeto não possui uma licença definida. Entre em contato com o autor para mais informações sobre uso e distribuição.
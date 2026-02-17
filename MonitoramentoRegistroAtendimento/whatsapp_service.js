const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');

const app = express();
const PORT = 7575;

app.use(express.json());

// Configuração do cliente WhatsApp
const client = new Client({
    authStrategy: new LocalAuth({
        clientId: "falta-registro-monitor",
        dataPath: "./whatsapp_session_falta_registro"
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    },
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html'
    }
});

let isReady = false;

client.on('qr', qr => {
    console.log('\n🔵 QR CODE para o sistema de falta de registro:');
    qrcode.generate(qr, { small: true });
    console.log('\n⚠️  Escaneie este QR Code com seu WhatsApp.');
});

client.on('ready', () => {
    isReady = true;
    console.log('✅ WhatsApp está pronto para enviar alertas de falta de registro!');
    console.log(`📱 Nome: ${client.info.pushname}`);
    console.log(`🔢 Número: ${client.info.wid.user}`);
});

client.on('authenticated', () => {
    console.log('✅ Autenticado com sucesso! Sessão salva.');
});

client.on('auth_failure', msg => {
    console.error('❌ Falha na autenticação:', msg);
});

client.on('disconnected', reason => {
    isReady = false;
    console.log('❌ WhatsApp foi desconectado:', reason);
    console.log('🔄 Tentando reconectar em 10 segundos...');
    setTimeout(() => {
        client.initialize();
    }, 10000);
});

// Inicializar o cliente
client.initialize();

// Endpoint para enviar mensagem
app.post('/send', async (req, res) => {
    try {
        const { groupId, message } = req.body;

        if (!isReady) {
            return res.status(503).json({ success: false, error: 'WhatsApp não está pronto' });
        }

        console.log(`📤 Enviando alerta para grupo: ${groupId}`);
        
        // Método direto que funciona
        await client.sendMessage(groupId, message);

        res.json({ success: true, message: 'Alerta enviado' });
    } catch (error) {
        console.error('❌ Erro ao enviar:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Endpoint de saúde
app.get('/health', (req, res) => {
    res.json({
        ready: isReady,
        pushname: client.info?.pushname || null
    });
});

app.listen(PORT, () => {
    console.log(`🚀 Serviço WhatsApp rodando na porta ${PORT}`);
    console.log(`📤 Endpoint: POST http://localhost:${PORT}/send`);
    console.log(`📊 Health: GET http://localhost:${PORT}/health`);
});
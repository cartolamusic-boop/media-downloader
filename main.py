import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

# Banco de dados em memória para as licenças
LICENCAS_DB = {}

def enviar_email_chave(email_destino: str, chave: str, plano: str = "Ativada"):
    remetente = "cartolamusic@gmail.com"
    senha_app = "usjj jbag mbmg hdlc"

    mensagem = MIMEMultipart()
    mensagem['From'] = remetente
    mensagem['To'] = email_destino
    mensagem['Subject'] = f"Sua Chave de Licença ({plano}) - Media Downloader Studio Pro"

    corpo = f"""
    Olá!

    Sua compra foi aprovada com sucesso!
    Sua chave de licença ({plano}) para ativar o Media Downloader Studio Pro é:

    CHAVE: {chave}

    Cole esta chave no programa e clique em 'Ativar Chave'.
    """
    mensagem.attach(MIMEText(corpo, 'plain', 'utf-8'))

    try:
        # Tenta conexão segura via SSL (porta 465) para evitar instabilidades na porta 587 no Render
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15)
        server.login(remetente, senha_app)
        server.sendmail(remetente, email_destino, mensagem.as_string())
        server.quit()
        print(f"✅ E-mail enviado com sucesso para {email_destino}!")
    except Exception as e:
        # Fallback para TLS na porta 587 se a 465 não conectar
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
            server.starttls()
            server.login(remetente, senha_app)
            server.sendmail(remetente, email_destino, mensagem.as_string())
            server.quit()
            print(f"✅ E-mail enviado via fallback para {email_destino}!")
        except Exception as err:
            print(f"❌ Erro ao enviar e-mail: {err}")

@app.get("/")
def home():
    return {"status": "Servidor de Licenças Online (Gmail)"}

@app.get("/validar")
def validar_chave(chave: str):
    chave = chave.strip()
    if chave in LICENCAS_DB:
        info = LICENCAS_DB[chave]
        return {"valido": True, "tipo": info.get("tipo", "Ativada")}
    return {"valido": False, "motivo": "Chave não encontrada ou inválida."}

@app.post("/webhook")
async def webhook_hotmart(request: Request, background_tasks: BackgroundTasks):
    dados = await request.json()
    
    event = dados.get("event") or dados.get("status")
    
    email_comprador = None
    if "data" in dados and "buyer" in dados["data"]:
        email_comprador = dados["data"]["buyer"].get("email")
    elif "buyer_email" in dados:
        email_comprador = dados["buyer_email"]

    # Identifica a oferta (Plano Mensal x Vitalício)
    offer_code = None
    if "data" in dados and "purchase" in dados["data"] and "offer" in dados["data"]["purchase"]:
        offer_code = dados["data"]["purchase"]["offer"].get("code")
    elif "offer" in dados:
        offer_code = dados.get("offer")

    # Mapeamento estrito das ofertas
    if offer_code == "v50pkoyk":
        tipo_plano = "Mensal"
    elif offer_code == "12nhtlsk":
        tipo_plano = "Vitalício"
    else:
        # Se for uma oferta de teste de R$ 1,00 ou desconhecida
        tipo_plano = "Mensal" if offer_code and "mensal" in str(offer_code).lower() else "Vitalício"

    if event in ["PURCHASE_APPROVED", "Compra aprovada", "Compra completa", "APPROVED"]:
        nova_chave = f"MDPRO-{uuid.uuid4().hex[:8].upper()}"
        
        LICENCAS_DB[nova_chave] = {
            "email": email_comprador,
            "tipo": tipo_plano,
            "status": "ativa"
        }
        
        print(f"Nova licença gerada [{tipo_plano}]: {nova_chave} para {email_comprador}")

        if email_comprador:
            background_tasks.add_task(enviar_email_chave, email_comprador, nova_chave, tipo_plano)

    return {"status": "sucesso"}

@app.get("/obrigado", response_class=HTMLResponse)
def pagina_obrigado(email: str = None, transaction: str = None):
    chave_encontrada = None
    
    if email:
        for chave, info in LICENCAS_DB.items():
            if info.get("email") == email.strip():
                chave_encontrada = chave

    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Sua Licença - Media Downloader Studio Pro</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; text-align: center; padding: 50px 20px; }}
            .card {{ background-color: #1E293B; border-radius: 12px; padding: 30px; max-width: 500px; margin: 0 auto; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
            h1 {{ color: #10B981; margin-bottom: 10px; }}
            .chave {{ font-size: 24px; font-weight: bold; background: #334155; padding: 15px; border-radius: 8px; color: #38BDF8; letter-spacing: 2px; margin: 25px 0; word-break: break-all; }}
            p {{ color: #94A3B8; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🎉 Compra Aprovada!</h1>
            <p>Sua chave de licença do <strong>Media Downloader Studio Pro</strong>:</p>
            <div class="chave">{chave_encontrada if chave_encontrada else 'Enviada para o seu e-mail!'}</div>
            <p>Abra o aplicativo, cole o código acima no campo de ativação e clique em <strong>"Ativar Chave"</strong>.</p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

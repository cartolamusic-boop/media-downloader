import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, BackgroundTasks

app = FastAPI()

# Banco de dados em memória para as licenças
LICENCAS_DB = {}

def enviar_email_chave(email_destino, chave):
    remetente = "cartolamusic@gmail.com"
    # COLE AQUI A SUA SENHA DE APLICAÇÃO DE 16 LETRAS DO GOOGLE
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
    mensagem.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha_app)
        server.sendmail(remetente, email_destino, mensagem.as_string())
        server.quit()
        print(f"E-mail enviado com sucesso para {email_destino}!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

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

    # Define o tipo de plano baseado na oferta da Hotmart
    if offer_code == "v50pkoyk":
        tipo_plano = "Mensal"
    else:
        tipo_plano = "Vitalício"

    if event in ["PURCHASE_APPROVED", "Compra aprovada", "Compra completa"]:
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

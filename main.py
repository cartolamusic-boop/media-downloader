import uuid
import requests
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse

app = FastAPI()

LICENCAS_DB = {}

# Cole aqui a sua API Key do Resend (começa com re_...)
RESEND_API_KEY = "re_HBvC9YRH_HkxX76FbjHWJP2G9MWuYgp5H"

def enviar_email_chave(email_destino: str, chave: str, plano: str = "Ativada"):
    if not RESEND_API_KEY or "SUA_CHAVE_AQUI" in RESEND_API_KEY:
        print("⚠️ RESEND_API_KEY não configurada.")
        return

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": "Media Downloader Studio Pro <onboarding@resend.dev>",
        "to": [email_destino],
        "subject": f"Sua Chave de Licença ({plano}) - Media Downloader Studio Pro",
        "html": f"""
        <div style="font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; padding: 30px; border-radius: 10px;">
            <h2 style="color: #10B981;">🎉 Compra Aprovada!</h2>
            <p>Sua chave de licença do <strong>Media Downloader Studio Pro</strong> ({plano}):</p>
            <div style="font-size: 22px; font-weight: bold; background: #334155; padding: 15px; border-radius: 8px; color: #38BDF8; letter-spacing: 2px; text-align: center; margin: 20px 0;">
                {chave}
            </div>
            <p>Abra o aplicativo, cole o código acima no campo de ativação e clique em <strong>"Ativar Chave"</strong>.</p>
        </div>
        """
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            print(f"✅ E-mail enviado com sucesso via Resend para {email_destino}!")
        else:
            print(f"❌ Erro ao enviar e-mail via Resend: {response.text}")
    except Exception as e:
        print(f"❌ Erro na requisição do Resend: {e}")

@app.get("/")
def home():
    return {"status": "Servidor de Licenças Online"}

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

    offer_code = None
    if "data" in dados and "purchase" in dados["data"] and "offer" in dados["data"]["purchase"]:
        offer_code = dados["data"]["purchase"]["offer"].get("code")
    elif "offer" in dados:
        offer_code = dados.get("offer")

    print(f"📌 Oferta recebida no Webhook: {offer_code}")

    if offer_code == "12nhtlsk":
        tipo_plano = "Mensal"
    elif offer_code == "v50pkoyk":
        tipo_plano = "Vitalício"
    else:
        tipo_plano = "Mensal"

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

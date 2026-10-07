import os
import json
import uuid
import requests
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

# Arquivo para salvar o banco de dados de licenças em disco
DB_FILE = "licencas_db.json"

def carregar_db():
    """Lê as licenças salvas no arquivo JSON ao iniciar o servidor."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
                # Converte strings ISO de data de volta para datetime com timezone
                for chave, info in dados.items():
                    if "data_criacao" in info and isinstance(info["data_criacao"], str):
                        info["data_criacao"] = datetime.fromisoformat(info["data_criacao"])
                print(f"💾 Base de licenças carregada! Total: {len(dados)} licença(s).")
                return dados
        except Exception as e:
            print(f"⚠️ Erro ao carregar banco local: {e}")
            return {}
    return {}

def salvar_db():
    """Salva o dicionário de licenças no arquivo JSON sempre que houver alteração."""
    try:
        dados_para_salvar = {}
        for chave, info in LICENCAS_DB.items():
            info_copy = info.copy()
            # Converte datetime para string ISO para poder salvar no JSON
            if isinstance(info_copy.get("data_criacao"), datetime):
                info_copy["data_criacao"] = info_copy["data_criacao"].isoformat()
            dados_para_salvar[chave] = info_copy

        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(dados_para_salvar, f, ensure_ascii=False, indent=2)
        print("✅ Licenças salvas em arquivo local com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao salvar banco local: {e}")

# Inicializa a base de dados com o que já estiver salvo em disco
LICENCAS_DB = carregar_db()

def enviar_email_chave(email_destino: str, chave: str, plano: str = "Ativada"):
    resend_key = os.getenv("RESEND_API_KEY", "").strip()

    if not resend_key:
        print("❌ ERRO CRÍTICO: RESEND_API_KEY não encontrada nas variáveis do Render!")
        return

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {resend_key}",
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
        print(f"📧 Enviando e-mail via Resend para {email_destino}...")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            print(f"✅ E-mail entregue com sucesso para {email_destino}!")
        else:
            print(f"❌ Erro da API Resend ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ Erro na requisição do Resend: {e}")

@app.get("/")
def home():
    return {"status": "Servidor de Licenças Online", "total_licencas": len(LICENCAS_DB)}

# ----------------------------------------------------
# ROTA DE VALIDAÇÃO (HWID + STATUS + DIAS MENSAL)
# ----------------------------------------------------
@app.get("/validar")
def validar_chave(chave: str, hwid: str = None):
    chave = chave.strip()
    
    if chave in LICENCAS_DB:
        info = LICENCAS_DB[chave]
        
        # 1. Checa se foi reembolsada ou cancelada
        if info.get("status") != "ativa":
            return {
                "valido": False,
                "status_code": "BLOQUEADO",
                "motivo": "Licença Bloqueada / Cancelada"
            }

        # 2. Trava de Hardware (1 PC por Licença)
        if hwid:
            hwid_registrado = info.get("hwid")
            if hwid_registrado is None:
                # Primeiro PC a ativar esta chave -> Registra o ID e salva no arquivo
                info["hwid"] = hwid
                salvar_db()
            elif hwid_registrado != hwid:
                # Tentativa de uso em outro PC
                return {
                    "valido": False,
                    "status_code": "BLOQUEADO_OUTRO_PC",
                    "motivo": "Esta chave já está ativada em outro computador!"
                }

        tipo = info.get("tipo", "Ativada")
        
        # 3. Contagem regressiva para Plano Mensal (30 dias)
        if tipo == "Mensal":
            data_criacao = info.get("data_criacao")
            if data_criacao:
                hoje = datetime.now(timezone.utc)
                dias_passados = (hoje - data_criacao).days
                dias_restantes = max(0, 30 - dias_passados)
                
                if dias_restantes <= 0:
                    info["status"] = "expirada"
                    salvar_db()
                    return {
                        "valido": False,
                        "status_code": "EXPIRADO",
                        "motivo": "Licença Mensal Expirada"
                    }
                
                return {
                    "valido": True,
                    "tipo": "Mensal",
                    "dias_restantes": dias_restantes,
                    "mensagem": f"Licença Mensal Ativa ({dias_restantes} dias restantes)"
                }

        return {
            "valido": True,
            "tipo": tipo,
            "dias_restantes": None,
            "mensagem": f"Licença {tipo} Ativa"
        }
        
    return {
        "valido": False,
        "status_code": "INVALIDO",
        "motivo": "Chave não encontrada ou inválida."
    }

# ----------------------------------------------------
# WEBHOOK HOTMART
# ----------------------------------------------------
@app.post("/webhook")
async def webhook_hotmart(request: Request):
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

    print(f"📌 Evento: {event} | Oferta: {offer_code} | E-mail: {email_comprador}")

    # 1. COMPRA APROVADA
    if event in ["PURCHASE_APPROVED", "Compra aprovada", "Compra completa", "APPROVED"]:
        if offer_code == "12nhtlsk":
            tipo_plano = "Mensal"
        elif offer_code == "v50pkoyk":
            tipo_plano = "Vitalício"
        else:
            tipo_plano = "Mensal"

        nova_chave = f"MDPRO-{uuid.uuid4().hex[:8].upper()}"
        
        LICENCAS_DB[nova_chave] = {
            "email": email_comprador,
            "tipo": tipo_plano,
            "status": "ativa",
            "hwid": None,
            "data_criacao": datetime.now(timezone.utc)
        }
        
        # Salva imediatamente no arquivo de disco
        salvar_db()
        
        print(f"✅ Nova licença gerada [{tipo_plano}]: {nova_chave} para {email_comprador}")

        if email_comprador:
            enviar_email_chave(email_comprador, nova_chave, tipo_plano)

    # 2. REEMBOLSO / CANCELAMENTO / CHARGEBACK
    elif event in ["PURCHASE_REFUNDED", "PURCHASE_CANCELED", "PURCHASE_CHARGEBACK", "REFUNDED", "CANCELED"]:
        if email_comprador:
            chaves_bloqueadas = 0
            for chave, info in LICENCAS_DB.items():
                if info.get("email") == email_comprador:
                    info["status"] = "cancelada"
                    chaves_bloqueadas += 1
            
            if chaves_bloqueadas > 0:
                salvar_db()
                
            print(f"🚫 Reembolso efetuado: {chaves_bloqueadas} chave(s) bloqueada(s) para {email_comprador}")

    return {"status": "sucesso"}

@app.get("/obrigado", response_class=HTMLResponse)
def pagina_obrigado(email: str = None, transaction: str = None):
    chave_encontrada = None
    
    if email:
        for chave, info in LICENCAS_DB.items():
            if info.get("email") == email.strip() and info.get("status") == "ativa":
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

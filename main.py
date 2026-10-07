import os
import uuid
import requests
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

# Credenciais do Supabase obtidas nas Variáveis de Ambiente do Render
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def carregar_db_nuvem():
    """Busca todas as licenças diretamente do banco gratuito no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ SUPABASE_URL ou SUPABASE_KEY não configurados!")
        return {}
    
    try:
        url = f"{SUPABASE_URL}/rest/v1/licencas?select=*"
        resp = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if resp.status_code == 200:
            registros = resp.json()
            db = {}
            for reg in registros:
                chave = reg.get("chave")
                data_criacao = reg.get("data_criacao")
                if data_criacao:
                    try:
                        data_criacao = datetime.fromisoformat(data_criacao)
                    except Exception:
                        pass
                
                db[chave] = {
                    "email": reg.get("email"),
                    "tipo": reg.get("tipo"),
                    "status": reg.get("status"),
                    "hwid": reg.get("hwid"),
                    "data_criacao": data_criacao
                }
            print(f"☁️ Banco carregado da nuvem com sucesso! Total: {len(db)} licença(s).")
            return db
    except Exception as e:
        print(f"❌ Erro ao carregar do Supabase: {e}")
    return {}

def salvar_ou_atualizar_nuvem(chave, info):
    """Salva ou atualiza uma licença instantaneamente no Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    try:
        url = f"{SUPABASE_URL}/rest/v1/licencas"
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates" # Faz UPSERT (insere ou atualiza se já existir)

        data_criacao = info.get("data_criacao")
        if isinstance(data_criacao, datetime):
            data_criacao = data_criacao.isoformat()

        payload = {
            "chave": chave,
            "email": info.get("email"),
            "tipo": info.get("tipo"),
            "status": info.get("status"),
            "hwid": info.get("hwid"),
            "data_criacao": data_criacao
        }

        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Erro ao salvar no Supabase: {e}")

# Versão e link para atualizações automáticas
VERSAO_LATEST = "1.0.1"
URL_DIRECT_DOWNLOAD = "https://drive.google.com/uc?export=download&id=12FKnuvwMMzLKMWz-CcnRXzsatnoIsL5v"

def enviar_email_chave(email_destino: str, chave: str, plano: str = "Ativada"):
    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if not resend_key:
        print("❌ RESEND_API_KEY não encontrada!")
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
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Erro no Resend: {e}")

@app.get("/")
def home():
    db_atual = carregar_db_nuvem()
    return {"status": "Servidor de Licenças Online (Nuven Supabase)", "total_licencas": len(db_atual), "versao_atual": VERSAO_LATEST}

@app.get("/checar_atualizacao")
def checar_atualizacao(versao_cliente: str = "1.0.0"):
    if versao_cliente != VERSAO_LATEST:
        return {
            "tem_atualizacao": True,
            "versao": VERSAO_LATEST,
            "url": URL_DIRECT_DOWNLOAD
        }
    return {"tem_atualizacao": False}

@app.get("/validar")
def validar_chave(chave: str, hwid: str = None):
    chave = chave.strip()
    db = carregar_db_nuvem()
    
    if chave in db:
        info = db[chave]
        
        if info.get("status") != "ativa":
            return {
                "valido": False,
                "status_code": "BLOQUEADO",
                "motivo": "Licença Bloqueada / Cancelada"
            }

        if hwid:
            hwid_registrado = info.get("hwid")
            if hwid_registrado is None:
                info["hwid"] = hwid
                salvar_ou_atualizar_nuvem(chave, info)
            elif hwid_registrado != hwid:
                return {
                    "valido": False,
                    "status_code": "BLOQUEADO_OUTRO_PC",
                    "motivo": "Esta chave já está ativada em outro computador!"
                }

        tipo = info.get("tipo", "Ativada")
        
        if tipo == "Mensal":
            data_criacao = info.get("data_criacao")
            if data_criacao:
                hoje = datetime.now(timezone.utc)
                if isinstance(data_criacao, str):
                    data_criacao = datetime.fromisoformat(data_criacao)
                dias_passados = (hoje - data_criacao).days
                dias_restantes = max(0, 30 - dias_passados)
                
                if dias_restantes <= 0:
                    info["status"] = "expirada"
                    salvar_ou_atualizar_nuvem(chave, info)
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

    if event in ["PURCHASE_APPROVED", "Compra aprovada", "Compra completa", "APPROVED"]:
        if offer_code == "12nhtlsk":
            tipo_plano = "Mensal"
        elif offer_code == "v50pkoyk":
            tipo_plano = "Vitalício"
        else:
            tipo_plano = "Mensal"

        nova_chave = f"MDPRO-{uuid.uuid4().hex[:8].upper()}"
        
        info_nova = {
            "email": email_comprador,
            "tipo": tipo_plano,
            "status": "ativa",
            "hwid": None,
            "data_criacao": datetime.now(timezone.utc)
        }
        
        salvar_ou_atualizar_nuvem(nova_chave, info_nova)
        print(f"✅ Nova licença gerada e salva na nuvem [{tipo_plano}]: {nova_chave} para {email_comprador}")

        if email_comprador:
            enviar_email_chave(email_comprador, nova_chave, tipo_plano)

    elif event in ["PURCHASE_REFUNDED", "PURCHASE_CANCELED", "PURCHASE_CHARGEBACK", "REFUNDED", "CANCELED"]:
        if email_comprador:
            db = carregar_db_nuvem()
            for chave, info in db.items():
                if info.get("email") == email_comprador:
                    info["status"] = "cancelada"
                    salvar_ou_atualizar_nuvem(chave, info)
            print(f"🚫 Reembolso efetuado: chaves bloqueadas para {email_comprador}")

    return {"status": "sucesso"}

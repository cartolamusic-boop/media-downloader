from fastapi import FastAPI, Request, HTTPException
import sqlite3
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

app = FastAPI()

DB_NAME = "licencas.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            chave TEXT UNIQUE NOT NULL,
            tipo TEXT NOT NULL,
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_expiracao DATETIME,
            status TEXT DEFAULT 'ativa'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def gerar_chave(prefixo="KEY"):
    g1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    g2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefixo}-{g1}-{g2}"

def enviar_email(destinatario, chave, tipo):
    remetente = os.getenv("EMAIL_REMETENTE")
    senha = os.getenv("EMAIL_SENHA")

    if not remetente or not senha:
        print("Erro: EMAIL_REMETENTE ou EMAIL_SENHA não configurados no Render.")
        return

    assunto = "Sua Chave de Acesso ao Sistema"
    
    corpo = f"""
    Olá!

    Obrigado pela sua compra! Aqui está a sua chave de acesso:

    Chave: {chave}
    Tipo de Licença: {tipo.title()}

    Para ativar, basta inserir essa chave no aplicativo.

    Atenciosamente,
    Equipe Suporte
    """

    msg = MIMEMultipart()
    msg['From'] = remetente
    msg['To'] = destinatario
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, destinatario, msg.as_string())
        server.quit()
        print(f"E-mail enviado com sucesso para {destinatario}")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

@app.get("/")
def home():
    return {"status": "Servidor rodando com sucesso!"}

@app.post("/webhook")
async def hotmart_webhook(request: Request):
    dados = await request.json()
    
    # Verifica status da compra no Webhook da Hotmart
    evento_status = dados.get("event")
    if evento_status not in ["PURCHASE_APPROVED", "PURCHASE_COMPLETE"]:
        return {"status": "sucesso", "mensagem": "Evento ignorado"}

    data = dados.get("data", {})
    buyer = data.get("buyer", {})
    product = data.get("product", {})

    buyer_email = buyer.get("email")
    product_id = str(product.get("id"))

    if not buyer_email:
        raise HTTPException(status_code=400, detail="E-mail do comprador não encontrado")

    # Altere aqui para o ID do seu produto mensal na Hotmart (se houver)
    ID_MENSAL = "123456"

    if product_id == ID_MENSAL:
        tipo = "mensal"
        data_expiracao = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        chave = gerar_chave("MENSAL")
    else:
        tipo = "vitalicio"
        data_expiracao = None
        chave = gerar_chave("VITA")

    # Salva a chave gerada no banco de dados
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chaves (email, chave, tipo, data_expiracao)
        VALUES (?, ?, ?, ?)
    ''', (buyer_email, chave, tipo, data_expiracao))
    conn.commit()
    conn.close()

    # Envia a chave por e-mail para o cliente
    enviar_email(buyer_email, chave, tipo)

    return {"status": "sucesso", "chave": chave, "email": buyer_email}

@app.get("/validar")
def validar_chave(chave: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT status, data_expiracao, tipo FROM chaves WHERE chave = ?", (chave,))
    resultado = cursor.fetchone()
    conn.close()

    if not resultado:
        return {"valido": False, "motivo": "Chave não encontrada"}

    status, data_expiracao, tipo = resultado

    if status != 'ativa':
        return {"valido": False, "motivo": "Chave desativada"}

    if data_expiracao:
        exp_dt = datetime.strptime(data_expiracao, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > exp_dt:
            return {"valido": False, "motivo": "Chave expirada"}

    return {"valido": True, "tipo": tipo}
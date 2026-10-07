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

    # 1. COMPRA APROVADA: Gera nova licença
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
            "status": "ativa"
        }
        
        print(f"✅ Nova licença gerada [{tipo_plano}]: {nova_chave} para {email_comprador}")

        if email_comprador:
            enviar_email_chave(email_comprador, nova_chave, tipo_plano)

    # 2. REEMBOLSO / CANCELAMENTO: Bloqueia todas as chaves do comprador
    elif event in ["PURCHASE_REFUNDED", "PURCHASE_CANCELED", "PURCHASE_CHARGEBACK", "REFUNDED", "CANCELED"]:
        if email_comprador:
            chaves_bloqueadas = 0
            for chave, info in LICENCAS_DB.items():
                if info.get("email") == email_comprador:
                    info["status"] = "cancelada"
                    chaves_bloqueadas += 1
            print(f"🚫 Reembolso processado: {chaves_bloqueadas} chave(s) bloqueada(s) para {email_comprador}")

    return {"status": "sucesso"}

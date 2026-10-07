import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def enviar_email_chave(email_destino, chave):
    remetente = "mediadownloadstudio@gmail.com"  # Seu e-mail
    senha_app = "trader12345"    # Senha de Aplicativo do Google (16 letras)

    mensagem = MIMEMultipart()
    mensagem['From'] = remetente
    mensagem['To'] = email_destino
    mensagem['Subject'] = "Sua Chave de Licença - Media Downloader Studio Pro"

    corpo = f"""
    Olá!
    
    Sua compra foi aprovada com sucesso!
    Sua chave de licença para ativar o Media Downloader Studio Pro é:
    
    CHAVE: {chave}
    
    Cole esta chave no programa e clique em 'Ativar Chave'.
    """
    mensagem.attach(MIMEText(corpo, 'plain'))

    try:
        # CONEXÃO VIA PORTA 587 (Aprovada pelo Render)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Ativa criptografia TLS
        server.login(remetente, senha_app)
        server.sendmail(remetente, email_destino, mensagem.as_string())
        server.quit()
        print(f"E-mail enviado com sucesso para {email_destino}!")
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")

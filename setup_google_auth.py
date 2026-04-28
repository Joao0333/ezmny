import os.path
import base64
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Se mudares os privilégios do bot no futuro, tens de apagar o token gerado e correr isto de novo
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    # O ficheiro credentials.json é o que baixaste da Google Cloud
    if not os.path.exists('credentials.json'):
        print("ERRO: Ficheiro credentials.json não encontrado na pasta!")
        return

    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Converte as credenciais para JSON string
    creds_json = creds.to_json()
    
    # Transforma em Base64 para podermos meter no Render com segurança
    creds_b64 = base64.b64encode(creds_json.encode('utf-8')).decode('utf-8')

    print("\n" + "="*50)
    print("CÓDIGO PARA O RENDER (GOOGLE_TOKEN_JSON):")
    print("="*50)
    print(creds_b64)
    print("="*50 + "\n")
    print("Copia o código acima e cola-o na variável GOOGLE_TOKEN_JSON no Render.")

if __name__ == '__main__':
    main()
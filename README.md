# TOTVS Cert Uploader (NFe / NFCe)

Aplicativo Desktop em Python (`CustomTkinter` + `Playwright` + `cryptography`) para leitura, validação local e upload automatizado de certificados digitais A1 (`.pfx` / `.p12`) na plataforma **TOTVS Emissão e Custódia** (`https://tec.totvshospitalidade.com/`).

---

## Funcionalidades

1. **Leitura e Validação Local (PKCS#12 / ICP-Brasil)**:
   - Valida a senha do arquivo `.pfx` ou `.p12` antes de iniciar a automação.
   - Extrai automaticamente **Razão Social**, **CNPJ** (com máscara `00.000.000/0000-00`, permitindo edição manual caso seja filial) e **Data de Validade** (alertando certificados expirados ou próximos do vencimento).
2. **Automação Completa no Portal TOTVS Hospitalidade**:
   - Autentica no `<iframe>` do TOTVS Identity (`acesso.totvshospitalidade.com`).
   - Fecha automaticamente avisos de senhas salvas e o modal de alerta de segurança da conta (**Entendi** / **Fechar**).
   - Pesquisa a empresa pelo CNPJ no painel de clientes e clica em **Acessar**.
   - Navega pelo menu lateral esquerdo em **Geral > Empresa** e aciona **Enviar Certificado**.
   - Preenche a senha do certificado, anexa o arquivo `.pfx`/`.p12` e clica em **Salvar**.
   - Monitora o retorno da plataforma e exibe o resultado (Sucesso ou Erro) diretamente no painel do aplicativo.

---

## Como Usar (Versão Executável `.exe`)

1. Baixe o arquivo **`TOTVS-Cert-Uploader.exe`** na aba [**Releases**](../../releases) deste repositório.
2. Certifique-se de que o computador possui o **Google Chrome** ou **Microsoft Edge** instalado (não é necessário instalar Python).
3. Abra o `TOTVS-Cert-Uploader.exe`, informe seu Login/Senha da plataforma TOTVS (salvos localmente em `config.json`), selecione o certificado `.pfx`/`.p12`, digite a senha do certificado e clique em **Enviar Certificado para a Plataforma TOTVS**.

---

## Como Executar a partir do Código-Fonte

### Pré-requisitos
- Windows 10/11
- Python 3.11 ou 3.12
- Google Chrome ou Microsoft Edge

### Instalação
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### Execução
Dê dois cliques em `iniciar.bat` ou execute:
```powershell
.\.venv\Scripts\python.exe app.py
```

### Gerar um novo Executável (`.exe`)
Dê dois cliques em `gerar_exe.bat` ou execute:
```powershell
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed --name "TOTVS-Cert-Uploader" --collect-all customtkinter --collect-all playwright app.py
```
O executável será gerado em `dist\TOTVS-Cert-Uploader.exe`.

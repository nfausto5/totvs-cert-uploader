# TOTVS Cert Uploader (NFe / NFCe)

Aplicativo Desktop em Python (`CustomTkinter` + `Playwright` + `cryptography`) voltado para o **cliente final** realizar a leitura, validação local e envio automatizado do seu certificado digital A1 (`.pfx` / `.p12`) em segundo plano.

---

## Principais Características

1. **Interface Simplificada para o Cliente Final**:
   - O cliente apenas seleciona o arquivo `.pfx`/`.p12`, informa a senha do certificado e clica em **Enviar Certificado Digital**.
   - **Sem exposição de credenciais**: Nenhuma tela de login/configuração da plataforma é exibida ao cliente e nenhum arquivo `config.json` é gravado no computador dele.
2. **Validação Local Instantânea (PKCS#12 / ICP-Brasil)**:
   - Valida a senha do certificado localmente antes do envio.
   - Exibe **Razão Social**, **CNPJ** (bloqueado por padrão para evitar erros de digitação, com opção *"Usar em filial"* caso necessário) e **Data de Validade**.
3. **Execução 100% Oculta e Anônima em Segundo Plano**:
   - O navegador roda totalmente invisível (`headless=True` + `CREATE_NO_WINDOW`) e em **sessão anônima temporária na memória RAM** (`--incognito` / `new_context()`), encerrando e limpando todos os dados ao concluir o envio.
   - O cliente acompanha o progresso por uma barra de progresso e mensagens amigáveis no próprio painel do aplicativo.

---

## Como Usar (Versão Executável `.exe` para o Cliente)

1. Baixe o arquivo **`TOTVS-Cert-Uploader.exe`** na aba [**Releases**](../../releases) deste repositório.
2. Envie o `TOTVS-Cert-Uploader.exe` para o cliente (o computador do cliente só precisa ter o **Google Chrome** ou **Microsoft Edge** instalado).
3. O cliente abre o executável, seleciona o `.pfx`/`.p12`, digita a senha do certificado e clica em **Enviar Certificado Digital**.

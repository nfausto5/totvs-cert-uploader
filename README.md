# TOTVS Cert Uploader (NFe / NFCe)

Aplicativo Desktop em Python (`CustomTkinter` + `Playwright` + `cryptography`) para leitura, validação local e envio automatizado de certificado digital A1 (`.pfx` / `.p12`) no portal TEC da TOTVS Hospitalidade.

---

## Versões Disponíveis

As duas versões estão disponíveis (código-fonte e executável `.exe`) na aba [**Releases**](https://github.com/nfausto5/totvs-cert-uploader/releases):

| Versão | Executável (`.exe`) | Código-Fonte | Descrição |
| :--- | :--- | :--- | :--- |
| **`v1.0.0`** | `TOTVS-Cert-Uploader-v1.0.0.exe` | [Tag `v1.0.0`](https://github.com/nfausto5/totvs-cert-uploader/tree/v1.0.0) | **Com Login e Senha no Portal TEC**: Aparece na interface o painel com os campos de usuário, senha e URL do portal TEC (além da opção de mostrar/ocultar o navegador). Ideal para uso técnico ou troca manual de credenciais. |
| **`v2.0.0`** | `TOTVS-Cert-Uploader-v2.0.0.exe` | [Tag `v2.0.0`](https://github.com/nfausto5/totvs-cert-uploader/tree/v2.0.0) | **Sem Login e Senha no Portal TEC (Cliente Final)**: Não aparece nenhum campo de login ou senha do portal TEC na interface. As credenciais vão embutidas internamente e a execução ocorre 100% oculta em segundo plano. |

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

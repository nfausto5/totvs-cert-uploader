import re
import time
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import BrowserContext, FrameLocator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import AppConfig, BASE_DIR

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class TotvsAutomationError(Exception):
    pass


def format_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj or "")
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    return (cnpj or "").strip()


class TotvsCertUploader:
    def __init__(self, config: AppConfig, log_callback: Optional[Callable[[str], None]] = None):
        self.config = config
        self.log_cb = log_callback or (lambda msg: None)
        self.user_data_dir = BASE_DIR / ".browser_profile"

    def log(self, message: str) -> None:
        self.log_cb(message)

    def _get_auth_frame(self, page: Page) -> FrameLocator:
        return page.frame_locator("iframe[src*='acesso.totvshospitalidade.com']")

    def _dismiss_popups(self, page: Page) -> None:
        """Fecha alertas de senhas salvas ou alerta de segurança da conta ('Fechar' / 'Entendi')."""
        auth_frame = self._get_auth_frame(page)
        frame_selectors = [
            "identity-mfa-warning-modal button:has-text('Entendi')",
            "identity-mfa-warning-modal button",
            "button:has-text('Entendi')",
            "button:has-text('Fechar')",
            ".po-modal button:has-text('Entendi')",
            ".po-modal button:has-text('Fechar')",
        ]
        for sel in frame_selectors:
            try:
                loc = auth_frame.locator(sel).first
                if loc.is_visible(timeout=250):
                    txt = (loc.inner_text() or "Entendi/Fechar").strip()
                    loc.click(timeout=1500)
                    self.log(f"Alerta fechado automaticamente ({txt}).")
                    page.wait_for_timeout(500)
            except Exception:
                pass

        page_selectors = [
            "button:has-text('Entendi')",
            "button:has-text('Fechar')",
            "po-modal button:has-text('Entendi')",
            "po-modal button:has-text('Fechar')",
        ]
        for sel in page_selectors:
            try:
                loc = page.locator(sel).first
                if loc.is_visible(timeout=200):
                    txt = (loc.inner_text() or "Entendi/Fechar").strip()
                    loc.click(timeout=1500)
                    self.log(f"Aviso fechado automaticamente ({txt}).")
                    page.wait_for_timeout(400)
            except Exception:
                pass

    def _ensure_logged_in_and_on_tenant_screen(self, page: Page) -> None:
        # Navega pela raiz https://tec.totvshospitalidade.com/ (que redireciona para /auth/login sem erro S3/CloudFront)
        base_url = "https://tec.totvshospitalidade.com/"
        self.log(f"Acessando plataforma TOTVS ({base_url})...")
        page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
        page.wait_for_timeout(4000)
        self._dismiss_popups(page)

        auth_frame = self._get_auth_frame(page)

        # Caso uma sessão persistente caia direto no /home de uma empresa anterior, volta para /auth/tenant via roteador SPA
        if "/home" in page.url or "/general" in page.url:
            self.log("Voltando para a seleção de empresas (/auth/tenant)...")
            page.evaluate(
                "window.history.pushState({}, '', '/auth/tenant'); window.dispatchEvent(new PopStateEvent('popstate'));"
            )
            page.wait_for_timeout(2500)
            self._dismiss_popups(page)

        # Verifica se já está na tela de seleção de empresa (input.po-search-input dentro do iframe)
        search_input = auth_frame.locator("input.po-search-input").first
        if search_input.is_visible(timeout=2000):
            self.log("Sessão já autenticada na tela de seleção de empresas.")
            self._dismiss_popups(page)
            return

        # Preenche login dentro do iframe acesso.totvshospitalidade.com
        self.log(f"Realizando login com '{self.config.username}'...")
        user_input = auth_frame.locator("input[type='text'], input[type='email']").first
        pwd_input = auth_frame.locator("input[type='password']").first

        try:
            user_input.wait_for(state="visible", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Não foi possível carregar o formulário de login da TOTVS.") from exc

        self._dismiss_popups(page)
        user_input.fill(self.config.username)
        pwd_input.fill(self.config.password)

        entrar_btn = auth_frame.get_by_role("button", name="Entrar", exact=True)
        entrar_btn.click()

        # Aguarda carregar a tela de seleção de empresas (input.po-search-input) e fecha o alerta "Entendi"
        self.log("Aguardando painel de empresas e verificando alertas de segurança...")
        deadline = time.time() + (self.config.timeout_ms / 1000.0)
        while time.time() < deadline:
            self._dismiss_popups(page)
            if search_input.is_visible(timeout=500):
                break
            err = auth_frame.locator(".po-toaster, .po-field-container-bottom-text-error, [role='alert']").first
            if err.is_visible(timeout=200):
                err_txt = (err.inner_text() or "").strip()
                if err_txt and any(w in err_txt.lower() for w in ("inválid", "incorret", "erro", "usuário", "senha")):
                    raise TotvsAutomationError(f"Falha no login TOTVS: {err_txt}")
            page.wait_for_timeout(500)
        else:
            raise TotvsAutomationError("Tempo esgotado aguardando a lista de empresas após o login.")

        page.wait_for_timeout(1200)
        self._dismiss_popups(page)

    def _search_and_access_company(self, page: Page, cnpj: str) -> None:
        cnpj_formatted = format_cnpj(cnpj)
        self.log(f"Pesquisando empresa pelo CNPJ: {cnpj_formatted} ...")

        self._dismiss_popups(page)
        auth_frame = self._get_auth_frame(page)
        search_input = auth_frame.locator("input.po-search-input").first

        try:
            search_input.wait_for(state="visible", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Campo 'Pesquisar' não encontrado na tela de empresas.") from exc

        self._dismiss_popups(page)
        search_input.click()
        search_input.fill("")
        search_input.fill(cnpj_formatted)
        search_input.press("Enter")

        page.wait_for_timeout(2000)
        self._dismiss_popups(page)

        frame_text = ""
        try:
            frame_text = auth_frame.locator("body").inner_text(timeout=3000)
        except Exception:
            pass

        acessar_btns = auth_frame.locator("button:has-text('Acessar')")
        count = acessar_btns.count()
        if count == 0 or (cnpj_formatted not in frame_text and count > 1):
            raise TotvsAutomationError(
                f"Nenhuma empresa encontrada no painel para o CNPJ {cnpj_formatted}."
            )

        self.log("Empresa localizada no painel! Clicando em 'Acessar'...")
        acessar_btns.first.click()

        # Aguarda carregar o menu lateral da empresa no frame principal
        try:
            page.wait_for_selector(".po-menu-item", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Tempo esgotado aguardando abertura do painel da empresa.") from exc

        page.wait_for_timeout(1500)
        self._dismiss_popups(page)

    def _navigate_geral_empresa(self, page: Page) -> None:
        self.log("Navegando no menu lateral esquerdo: Geral > Empresa ...")
        self._dismiss_popups(page)

        geral_menu = page.locator(".po-menu-item:has-text('Geral')").first
        try:
            geral_menu.wait_for(state="visible", timeout=self.config.timeout_ms)
            geral_menu.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Menu lateral 'Geral' não encontrado.") from exc

        page.wait_for_timeout(800)

        empresa_menu = page.locator(
            ".po-menu-item-level-two:has-text('Empresa'), .po-menu-item:has-text('Empresa')"
        ).first
        try:
            empresa_menu.wait_for(state="visible", timeout=self.config.timeout_ms)
            empresa_menu.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Submenu 'Empresa' (dentro de Geral) não encontrado.") from exc

        page.wait_for_timeout(2000)
        self._dismiss_popups(page)

    def _upload_certificate(self, page: Page, cert_path: str, cert_password: str) -> str:
        self.log("Procurando e clicando no botão 'Enviar Certificado'...")
        enviar_btn = page.locator(
            "button:has-text('Enviar Certificado'), button:has-text('Enviar certificado')"
        ).first
        try:
            enviar_btn.wait_for(state="visible", timeout=self.config.timeout_ms)
            enviar_btn.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Botão 'Enviar Certificado' não encontrado no painel da Empresa.") from exc

        page.wait_for_timeout(1500)

        # Preenche a senha do certificado na tela de upload (/general/company/certificate)
        self.log("Digitando a senha do certificado digital...")
        pwd_input = page.locator(
            "input[type='password'][name='password'], input[id^='po-password'], input[type='password']"
        ).first
        try:
            pwd_input.wait_for(state="visible", timeout=10000)
            pwd_input.click()
            pwd_input.fill(cert_password)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Campo de senha do certificado não encontrado.") from exc

        # Seleciona o arquivo clicando em 'Selecionar arquivo' (ou definindo no input[type='file'][name='upload'])
        self.log(f"Selecionando o arquivo '{Path(cert_path).name}'...")
        file_attached = False
        select_file_btn = page.locator("button:has-text('Selecionar arquivo')").first

        if select_file_btn.count() > 0 and select_file_btn.is_visible(timeout=2000):
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    select_file_btn.click()
                fc_info.value.set_files(cert_path)
                file_attached = True
            except Exception:
                pass

        if not file_attached:
            file_input = page.locator("input.po-upload-input, input[type='file'][name='upload'], input[type='file']").first
            if file_input.count() > 0:
                file_input.set_input_files(cert_path)
                file_attached = True

        if not file_attached:
            raise TotvsAutomationError("Não foi possível anexar o arquivo do certificado.")

        page.wait_for_timeout(1000)

        # Clica em Salvar
        self.log("Clicando em 'Salvar'...")
        salvar_btn = page.get_by_role("button", name="Salvar", exact=True)
        try:
            salvar_btn.wait_for(state="visible", timeout=5000)
            salvar_btn.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Botão 'Salvar' não encontrado na tela de certificado.") from exc

        # Aguarda o aviso de sucesso ou falha emitido pelo site (po-toaster / notificação)
        self.log("Aguardando aviso de confirmação da plataforma TOTVS...")
        toast_selectors = (
            ".po-toaster, po-toaster, .po-notification, .toast-message, "
            "[role='alert'], .po-field-container-bottom-text-error"
        )
        deadline = time.time() + 20.0
        while time.time() < deadline:
            toasts = page.locator(toast_selectors)
            count = toasts.count()
            for i in range(count):
                el = toasts.nth(i)
                try:
                    if el.is_visible(timeout=200):
                        txt = (el.inner_text() or "").strip()
                        cls = (el.get_attribute("class") or "").lower()
                        if not txt:
                            continue
                        if any(w in txt.lower() for w in ("sucesso", "salvo", "atualizado", "enviado", "cadastrado")):
                            return txt
                        if any(w in txt.lower() for w in ("erro", "inválid", "incorret", "falha", "expirad", "não corresponde", "divergente")) or "error" in cls or "danger" in cls:
                            raise TotvsAutomationError(f"Aviso da plataforma: {txt}")
                except TotvsAutomationError:
                    raise
                except Exception:
                    pass

            # Se redirecionou de volta para /general/company (saiu de /certificate/), salvou com sucesso!
            if "/general/company" in page.url and "/certificate" not in page.url:
                return "Certificado salvo com sucesso na plataforma!"

            page.wait_for_timeout(400)

        raise TotvsAutomationError("O site não confirmou o salvamento do certificado (verifique se a senha ou o CNPJ correspondem à empresa).")

    def run_upload(self, cnpj: str, cert_path: str, cert_password: str) -> str:
        with sync_playwright() as p:
            launch_args = ["--disable-blink-features=AutomationControlled"]
            context: Optional[BrowserContext] = None
            browser = None
            try:
                if self.config.persist_session:
                    self.user_data_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        context = p.chromium.launch_persistent_context(
                            user_data_dir=str(self.user_data_dir),
                            channel="chrome",
                            headless=self.config.headless,
                            user_agent=USER_AGENT,
                            args=launch_args,
                            viewport={"width": 1366, "height": 768},
                        )
                    except Exception:
                        context = p.chromium.launch_persistent_context(
                            user_data_dir=str(self.user_data_dir),
                            channel="msedge",
                            headless=self.config.headless,
                            user_agent=USER_AGENT,
                            args=launch_args,
                            viewport={"width": 1366, "height": 768},
                        )
                    page = context.pages[0] if context.pages else context.new_page()
                else:
                    try:
                        browser = p.chromium.launch(
                            channel="chrome",
                            headless=self.config.headless,
                            args=launch_args,
                        )
                    except Exception:
                        browser = p.chromium.launch(
                            channel="msedge",
                            headless=self.config.headless,
                            args=launch_args,
                        )
                    context = browser.new_context(
                        user_agent=USER_AGENT,
                        viewport={"width": 1366, "height": 768},
                    )
                    page = context.new_page()

                self._ensure_logged_in_and_on_tenant_screen(page)
                self._search_and_access_company(page, cnpj)
                self._navigate_geral_empresa(page)
                result_msg = self._upload_certificate(page, cert_path, cert_password)
                self.log(f"Aviso do site: {result_msg}")
                return result_msg
            finally:
                try:
                    if context:
                        context.close()
                    if browser:
                        browser.close()
                except Exception:
                    pass

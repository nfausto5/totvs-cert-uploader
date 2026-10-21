import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import BrowserContext, FrameLocator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from config import AppConfig

# Evita que o processo node.exe do driver do Playwright pisque janela de console no Windows
if sys.platform == "win32":
    _orig_popen = subprocess.Popen

    class _NoWindowPopen(_orig_popen):
        def __init__(self, *args, **kwargs):
            if "creationflags" not in kwargs:
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoWindowPopen  # type: ignore[misc]

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

    def log(self, message: str) -> None:
        self.log_cb(message)

    def _get_auth_frame(self, page: Page) -> FrameLocator:
        return page.frame_locator("iframe[src*='acesso.totvshospitalidade.com']")

    def _dismiss_popups(self, page: Page) -> None:
        """Fecha silenciosamente alertas de senhas salvas ou alerta de segurança ('Fechar' / 'Entendi')."""
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
                    loc.click(timeout=1500)
                    page.wait_for_timeout(400)
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
                    loc.click(timeout=1500)
                    page.wait_for_timeout(350)
            except Exception:
                pass

    def _ensure_logged_in_and_on_tenant_screen(self, page: Page) -> None:
        base_url = "https://tec.totvshospitalidade.com/"
        self.log("Conectando ao servidor centralizador em segundo plano...")
        page.goto(base_url, wait_until="domcontentloaded", timeout=self.config.timeout_ms)
        page.wait_for_timeout(4000)
        self._dismiss_popups(page)

        auth_frame = self._get_auth_frame(page)

        search_input = auth_frame.locator("input.po-search-input").first
        if search_input.is_visible(timeout=1500):
            self._dismiss_popups(page)
            return

        self.log("Autenticando sessão segura...")
        user_input = auth_frame.locator("input[type='text'], input[type='email']").first
        pwd_input = auth_frame.locator("input[type='password']").first

        try:
            user_input.wait_for(state="visible", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Não foi possível conectar ao serviço de autenticação.") from exc

        self._dismiss_popups(page)
        user_input.fill(self.config.username)
        pwd_input.fill(self.config.password)

        entrar_btn = auth_frame.get_by_role("button", name="Entrar", exact=True)
        entrar_btn.click()

        deadline = time.time() + (self.config.timeout_ms / 1000.0)
        while time.time() < deadline:
            self._dismiss_popups(page)
            if search_input.is_visible(timeout=500):
                break
            err = auth_frame.locator(".po-toaster, .po-field-container-bottom-text-error, [role='alert']").first
            if err.is_visible(timeout=200):
                err_txt = (err.inner_text() or "").strip()
                if err_txt and any(w in err_txt.lower() for w in ("inválid", "incorret", "erro", "usuário", "senha")):
                    raise TotvsAutomationError(f"Falha na autenticação do servidor: {err_txt}")
            page.wait_for_timeout(500)
        else:
            raise TotvsAutomationError("Tempo esgotado aguardando resposta do painel de empresas.")

        page.wait_for_timeout(1200)
        self._dismiss_popups(page)

    def _search_and_access_company(self, page: Page, cnpj: str) -> None:
        cnpj_formatted = format_cnpj(cnpj)
        self.log(f"Localizando cadastro da empresa ({cnpj_formatted})...")

        self._dismiss_popups(page)
        auth_frame = self._get_auth_frame(page)
        search_input = auth_frame.locator("input.po-search-input").first

        try:
            search_input.wait_for(state="visible", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Campo de pesquisa de empresa não disponível.") from exc

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
                f"Empresa com CNPJ {cnpj_formatted} não localizada na plataforma."
            )

        self.log("Empresa localizada! Acessando painel da empresa...")
        acessar_btns.first.click()

        try:
            page.wait_for_selector(".po-menu-item", timeout=self.config.timeout_ms)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Tempo esgotado ao carregar os dados da empresa.") from exc

        page.wait_for_timeout(1500)
        self._dismiss_popups(page)

    def _navigate_geral_empresa(self, page: Page) -> None:
        self.log("Acessando configurações fiscais da empresa (Geral > Empresa)...")
        self._dismiss_popups(page)

        geral_menu = page.locator(".po-menu-item:has-text('Geral')").first
        try:
            geral_menu.wait_for(state="visible", timeout=self.config.timeout_ms)
            geral_menu.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Menu 'Geral' não encontrado no painel da empresa.") from exc

        page.wait_for_timeout(800)

        empresa_menu = page.locator(
            ".po-menu-item-level-two:has-text('Empresa'), .po-menu-item:has-text('Empresa')"
        ).first
        try:
            empresa_menu.wait_for(state="visible", timeout=self.config.timeout_ms)
            empresa_menu.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Submenu 'Empresa' não encontrado.") from exc

        page.wait_for_timeout(2000)
        self._dismiss_popups(page)

    def _upload_certificate(self, page: Page, cert_path: str, cert_password: str) -> str:
        self.log("Iniciando envio do certificado digital...")
        enviar_btn = page.locator(
            "button:has-text('Enviar Certificado'), button:has-text('Enviar certificado')"
        ).first
        try:
            enviar_btn.wait_for(state="visible", timeout=self.config.timeout_ms)
            enviar_btn.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Opção 'Enviar Certificado' não encontrada.") from exc

        page.wait_for_timeout(1500)

        pwd_input = page.locator(
            "input[type='password'][name='password'], input[id^='po-password'], input[type='password']"
        ).first
        try:
            pwd_input.wait_for(state="visible", timeout=10000)
            pwd_input.click()
            pwd_input.fill(cert_password)
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Campo de senha do certificado não disponível.") from exc

        self.log(f"Anexando arquivo '{Path(cert_path).name}' e salvando...")
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

        salvar_btn = page.get_by_role("button", name="Salvar", exact=True)
        try:
            salvar_btn.wait_for(state="visible", timeout=5000)
            salvar_btn.click()
        except PlaywrightTimeoutError as exc:
            raise TotvsAutomationError("Botão 'Salvar' não encontrado.") from exc

        self.log("Aguardando confirmação de salvamento da plataforma...")
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

            if "/general/company" in page.url and "/certificate" not in page.url:
                return "Certificado salvo com sucesso!"

            page.wait_for_timeout(400)

        raise TotvsAutomationError("A plataforma não confirmou o salvamento (verifique se o certificado pertence a esta empresa).")

    def run_upload(self, cnpj: str, cert_path: str, cert_password: str) -> str:
        with sync_playwright() as p:
            # Sempre abre em sessão anônima na memória (new_context) e oculta em segundo plano (headless=True)
            launch_args = [
                "--incognito",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
            ]
            context: Optional[BrowserContext] = None
            browser = None
            try:
                try:
                    browser = p.chromium.launch(
                        channel="chrome",
                        headless=True,
                        args=launch_args,
                    )
                except Exception:
                    browser = p.chromium.launch(
                        channel="msedge",
                        headless=True,
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
                self.log("Concluído! Sessão anônima encerrada com segurança.")
                return result_msg
            finally:
                try:
                    if context:
                        context.close()
                    if browser:
                        browser.close()
                except Exception:
                    pass

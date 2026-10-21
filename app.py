import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from cert_reader import CertificateInfo, format_cnpj, read_pfx_certificate
from config import AppConfig, load_config, save_config
from totvs_automation import TotvsAutomationError, TotvsCertUploader

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CertUploaderApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Centralizador de Certificados Digitais — TOTVS Hospitalidade (NFe / NFCe)")
        self.geometry("860x760")
        self.minsize(780, 700)

        self.config_data: AppConfig = load_config()
        self.cert_info: Optional[CertificateInfo] = None
        self.is_running: bool = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_header()
        self._build_cert_card()
        self._build_details_card()
        self._build_settings_card()
        self._build_status_and_actions()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(16, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Upload de Certificado Digital (NFe / NFCe)",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Lê o certificado .pfx/.p12 localmente, localiza a empresa pelo CNPJ no painel TOTVS Hospitalidade e envia automaticamente.",
            font=ctk.CTkFont(size=13),
            text_color="#A0AEC0",
            anchor="w",
        )
        subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def _build_cert_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=1, column=0, padx=20, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        section_lbl = ctk.CTkLabel(
            card,
            text="1. Arquivo e Senha do Certificado Digital",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        section_lbl.grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

        # File row
        ctk.CTkLabel(card, text="Arquivo (.pfx/.p12):").grid(row=1, column=0, padx=(16, 8), pady=6, sticky="w")
        self.file_entry = ctk.CTkEntry(card, placeholder_text="Selecione o arquivo .pfx ou .p12 do cliente...")
        self.file_entry.grid(row=1, column=1, columnspan=2, padx=4, pady=6, sticky="ew")

        self.browse_btn = ctk.CTkButton(card, text="Selecionar Arquivo...", width=160, command=self._on_browse_file)
        self.browse_btn.grid(row=1, column=3, padx=(8, 16), pady=6)

        # Password row
        ctk.CTkLabel(card, text="Senha do Certificado:").grid(row=2, column=0, padx=(16, 8), pady=(6, 14), sticky="w")
        self.cert_pwd_entry = ctk.CTkEntry(card, placeholder_text="Digite a senha do certificado digital...", show="•")
        self.cert_pwd_entry.grid(row=2, column=1, padx=4, pady=(6, 14), sticky="ew")
        self.cert_pwd_entry.bind("<Return>", lambda _e: self._validate_certificate())
        self.cert_pwd_entry.bind("<FocusOut>", lambda _e: self._auto_validate_if_ready())

        self.show_pwd_var = ctk.BooleanVar(value=False)
        self.show_pwd_cb = ctk.CTkCheckBox(
            card,
            text="Mostrar senha",
            variable=self.show_pwd_var,
            command=self._toggle_cert_password,
            width=110,
        )
        self.show_pwd_cb.grid(row=2, column=2, padx=8, pady=(6, 14))

        self.validate_btn = ctk.CTkButton(
            card,
            text="Ler / Validar Certificado",
            width=160,
            fg_color="#2B6CB0",
            hover_color="#2C5282",
            command=self._validate_certificate,
        )
        self.validate_btn.grid(row=2, column=3, padx=(8, 16), pady=(6, 14))

    def _build_details_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=2, column=0, padx=20, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        section_lbl = ctk.CTkLabel(
            card,
            text="2. Dados Identificados no Certificado",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        section_lbl.grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 8), sticky="w")

        ctk.CTkLabel(card, text="Razão Social:").grid(row=1, column=0, padx=(16, 8), pady=4, sticky="w")
        self.razao_lbl = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.razao_lbl.grid(row=1, column=1, columnspan=3, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(card, text="CNPJ (busca no site):").grid(row=2, column=0, padx=(16, 8), pady=(4, 12), sticky="w")
        self.cnpj_entry = ctk.CTkEntry(card, placeholder_text="00.000.000/0000-00")
        self.cnpj_entry.grid(row=2, column=1, padx=4, pady=(4, 12), sticky="ew")

        ctk.CTkLabel(card, text="Validade:").grid(row=2, column=2, padx=(16, 8), pady=(4, 12), sticky="w")
        self.validade_lbl = ctk.CTkLabel(card, text="—", anchor="w")
        self.validade_lbl.grid(row=2, column=3, padx=(4, 16), pady=(4, 12), sticky="ew")

    def _build_settings_card(self) -> None:
        card = ctk.CTkFrame(self, corner_radius=10)
        card.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(3, weight=1)

        section_lbl = ctk.CTkLabel(
            card,
            text="3. Credenciais e Opções da Plataforma (tec.totvshospitalidade.com)",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        section_lbl.grid(row=0, column=0, columnspan=5, padx=16, pady=(12, 8), sticky="w")

        ctk.CTkLabel(card, text="Login TOTVS:").grid(row=1, column=0, padx=(16, 8), pady=4, sticky="w")
        self.site_user_entry = ctk.CTkEntry(card)
        self.site_user_entry.insert(0, self.config_data.username)
        self.site_user_entry.grid(row=1, column=1, padx=4, pady=4, sticky="ew")

        ctk.CTkLabel(card, text="Senha TOTVS:").grid(row=1, column=2, padx=(16, 8), pady=4, sticky="w")
        self.site_pwd_entry = ctk.CTkEntry(card, show="•")
        self.site_pwd_entry.insert(0, self.config_data.password)
        self.site_pwd_entry.grid(row=1, column=3, padx=4, pady=4, sticky="ew")

        self.visible_browser_var = ctk.BooleanVar(value=not self.config_data.headless)
        self.visible_browser_cb = ctk.CTkCheckBox(
            card,
            text="Exibir navegador durante o envio",
            variable=self.visible_browser_var,
        )
        self.visible_browser_cb.grid(row=2, column=0, columnspan=2, padx=16, pady=(6, 12), sticky="w")

        self.persist_session_var = ctk.BooleanVar(value=self.config_data.persist_session)
        self.persist_session_cb = ctk.CTkCheckBox(
            card,
            text="Manter sessão logada entre envios",
            variable=self.persist_session_var,
        )
        self.persist_session_cb.grid(row=2, column=2, columnspan=2, padx=16, pady=(6, 12), sticky="w")

    def _build_status_and_actions(self) -> None:
        container = ctk.CTkFrame(self, corner_radius=10)
        container.grid(row=4, column=0, padx=20, pady=(8, 16), sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(2, weight=1)

        # Banner de Aviso de Sucesso / Erro no painel
        self.status_banner = ctk.CTkFrame(container, corner_radius=8, fg_color="#2D3748")
        self.status_banner.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        self.status_banner.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.status_banner,
            text="Status: Aguardando seleção e validação do certificado digital.",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0",
            wraplength=760,
            justify="left",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, padx=14, pady=10, sticky="ew")

        # Botão principal de Envio
        self.upload_btn = ctk.CTkButton(
            container,
            text="ENVIAR CERTIFICADO PARA A PLATAFORMA TOTVS",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2F855A",
            hover_color="#276749",
            command=self._on_start_upload,
        )
        self.upload_btn.grid(row=1, column=0, padx=16, pady=6, sticky="ew")

        # Caixa de Log detalhado
        self.log_box = ctk.CTkTextbox(container, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.grid(row=2, column=0, padx=16, pady=(6, 14), sticky="nsew")
        self.log_box.configure(state="disabled")
        self._append_log("Aplicativo pronto. Selecione um arquivo .pfx/.p12 e informe a senha.")

    def _toggle_cert_password(self) -> None:
        self.cert_pwd_entry.configure(show="" if self.show_pwd_var.get() else "•")

    def _append_log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"

        def _update() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _update)

    def _set_banner(self, text: str, level: str = "info") -> None:
        colors = {
            "info": ("#2D3748", "#E2E8F0"),
            "working": ("#2B6CB0", "#FFFFFF"),
            "success": ("#22543D", "#C6F6D5"),
            "warning": ("#744210", "#FEFCBF"),
            "error": ("#742A2A", "#FED7D7"),
        }
        bg, fg = colors.get(level, colors["info"])

        def _update() -> None:
            self.status_banner.configure(fg_color=bg)
            self.status_label.configure(text=text, text_color=fg)

        self.after(0, _update)

    def _on_browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Selecionar Certificado Digital",
            filetypes=[("Certificado Digital PKCS#12", "*.pfx *.p12"), ("Todos os arquivos", "*.*")],
        )
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
            self._append_log(f"Arquivo selecionado: {file_path}")
            self._auto_validate_if_ready()

    def _auto_validate_if_ready(self) -> None:
        if self.file_entry.get().strip() and self.cert_pwd_entry.get():
            self._validate_certificate()

    def _validate_certificate(self) -> bool:
        file_path = self.file_entry.get().strip()
        cert_pwd = self.cert_pwd_entry.get()

        if not file_path:
            self._set_banner("Atenção: Selecione o arquivo .pfx ou .p12 do certificado.", "warning")
            return False
        if not cert_pwd:
            self._set_banner("Atenção: Digite a senha do certificado digital.", "warning")
            return False

        try:
            info = read_pfx_certificate(file_path, cert_pwd)
            self.cert_info = info
            self.razao_lbl.configure(text=info.razao_social)

            if info.cnpj_formatado:
                self.cnpj_entry.delete(0, "end")
                self.cnpj_entry.insert(0, info.cnpj_formatado)

            val_str = f"{info.valido_ate.strftime('%d/%m/%Y')} ({info.dias_restantes} dias restantes)"
            if info.expirado:
                self.validade_lbl.configure(text=f"EXPIRADO em {info.valido_ate.strftime('%d/%m/%Y')}", text_color="#FC8181")
                self._set_banner(
                    f"Atenção: O certificado de '{info.razao_social}' está EXPIRADO ({info.valido_ate.strftime('%d/%m/%Y')})!",
                    "error",
                )
            else:
                color = "#68D391" if info.dias_restantes > 30 else "#F6E05E"
                self.validade_lbl.configure(text=val_str, text_color=color)
                self._set_banner(
                    f"Certificado válido! Empresa: {info.razao_social} | CNPJ: {info.cnpj_formatado or 'Não identificado'}",
                    "success",
                )

            self._append_log(
                f"Certificado validado com sucesso: {info.razao_social} | CNPJ: {info.cnpj_formatado} | Validade: {info.valido_ate.strftime('%d/%m/%Y')}"
            )
            return True
        except Exception as exc:
            self.cert_info = None
            self.razao_lbl.configure(text="—")
            self.validade_lbl.configure(text="—", text_color="#E2E8F0")
            self._set_banner(f"Erro na validação do certificado: {exc}", "error")
            self._append_log(f"ERRO ao ler certificado: {exc}")
            return False

    def _save_current_config(self) -> None:
        self.config_data.username = self.site_user_entry.get().strip()
        self.config_data.password = self.site_pwd_entry.get()
        self.config_data.headless = not self.visible_browser_var.get()
        self.config_data.persist_session = self.persist_session_var.get()
        save_config(self.config_data)

    def _on_start_upload(self) -> None:
        if self.is_running:
            return

        if not self._validate_certificate():
            return

        if not self.site_user_entry.get().strip() or not self.site_pwd_entry.get():
            self._set_banner("Atenção: Preencha o Login e a Senha da plataforma TOTVS na seção 3.", "warning")
            return

        cnpj = format_cnpj(self.cnpj_entry.get().strip())
        if not cnpj:
            self._set_banner("Erro: O CNPJ para pesquisa na plataforma não foi preenchido.", "error")
            return

        self.cnpj_entry.delete(0, "end")
        self.cnpj_entry.insert(0, cnpj)

        cert_path = str(Path(self.file_entry.get().strip()).resolve())
        cert_pwd = self.cert_pwd_entry.get()

        self._save_current_config()

        self.is_running = True
        self.upload_btn.configure(state="disabled", text="ENVIANDO CERTIFICADO... AGUARDE")
        self._set_banner(f"Executando automação na plataforma TOTVS para o CNPJ {cnpj}...", "working")
        self._append_log(f"Iniciando envio para a plataforma TOTVS (CNPJ: {cnpj})...")

        thread = threading.Thread(
            target=self._worker_upload,
            args=(cnpj, cert_path, cert_pwd),
            daemon=True,
        )
        thread.start()

    def _worker_upload(self, cnpj: str, cert_path: str, cert_pwd: str) -> None:
        uploader = TotvsCertUploader(self.config_data, log_callback=self._append_log)
        try:
            msg = uploader.run_upload(cnpj=cnpj, cert_path=cert_path, cert_password=cert_pwd)
            self._set_banner(f"SUCESSO: {msg} (CNPJ: {cnpj})", "success")
            self._append_log(f"FINALIZADO COM SUCESSO: {msg}")
        except TotvsAutomationError as exc:
            self._set_banner(f"FALHA NO ENVIO: {exc}", "error")
            self._append_log(f"ERRO NA AUTOMAÇÃO: {exc}")
        except Exception as exc:
            self._set_banner(f"ERRO INESPERADO: {exc}", "error")
            self._append_log(f"ERRO INESPERADO: {exc}")
        finally:
            self.is_running = False
            self.after(
                0,
                lambda: self.upload_btn.configure(
                    state="normal", text="ENVIAR CERTIFICADO PARA A PLATAFORMA TOTVS"
                ),
            )


if __name__ == "__main__":
    app = CertUploaderApp()
    app.mainloop()

import asyncio
import aiomysql
import time
import threading
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinter import filedialog, messagebox
import textwrap
import os
import statistics

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class StressTestApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MySQL Optimization Comparator - Fix Edition")
        self.geometry("1400x900")

        # Listas de dados protegidas
        self.data_sessao_1 = []
        self.data_sessao_2 = []
        self.sessao_atual = 1

        self.is_running = False
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=360, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.sidebar, text="🚀 COMPARADOR", font=("Roboto", 20, "bold")).pack(pady=15)

        # Segmented control
        self.seg_control = ctk.CTkSegmentedButton(
            self.sidebar,
            values=["Execução 1", "Execução 2"],
            command=self.trocar_sessao
        )
        self.seg_control.set("Execução 1")
        self.seg_control.pack(pady=10, padx=20, fill="x")

        # Frame que fica imediatamente abaixo do segmented control e contém as caixas de query
        self.frame_queries_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_queries_container.pack(pady=(0, 10), padx=20, fill="x")

        # Frame para query da execução 1
        self.frame_query1 = ctk.CTkFrame(self.frame_queries_container, fg_color="transparent")
        ctk.CTkLabel(self.frame_query1, text="Query Execução 1:").pack(anchor="w", padx=0)
        self.entry_query1 = ctk.CTkTextbox(self.frame_query1, height=80, width=300)
        self.entry_query1.insert("0.0", "SELECT 1")
        self.entry_query1.pack(pady=5, padx=0)

        # Frame para query da execução 2
        self.frame_query2 = ctk.CTkFrame(self.frame_queries_container, fg_color="transparent")
        ctk.CTkLabel(self.frame_query2, text="Query Execução 2:").pack(anchor="w", padx=0)
        self.entry_query2 = ctk.CTkTextbox(self.frame_query2, height=80, width=300)
        self.entry_query2.insert("0.0", "SELECT 1")
        self.entry_query2.pack(pady=5, padx=0)

        # Inicialmente mostra apenas a query da sessão 1
        self.frame_query1.pack(fill="x")

        # Restante dos inputs
        self.entry_total = self.create_input("Total Requisições:", "100")
        self.entry_concur = self.create_input("Simultâneas:", "10")
        self.entry_host = self.create_input("Host:", "127.0.0.1")
        self.entry_user = self.create_input("Usuário:", "root")
        self.entry_pass = ctk.CTkEntry(self.sidebar, width=300, placeholder_text="Senha", show="*")
        self.entry_pass.pack(pady=5, padx=20)
        self.entry_db = self.create_input("Banco:", "mysql")

        self.btn_start = ctk.CTkButton(self.sidebar, text="🔥 INICIAR", command=self.start_test_thread, fg_color="green")
        self.btn_start.pack(pady=10, padx=20)

        self.btn_stop = ctk.CTkButton(self.sidebar, text="🛑 PARAR", command=self.stop_test, fg_color="red", state="disabled")
        self.btn_stop.pack(pady=5, padx=20)

        self.btn_save = ctk.CTkButton(self.sidebar, text="💾 EXPORTAR 3 GRÁFICOS", command=self.save_all_graphs, fg_color="#444444")
        self.btn_save.pack(pady=5, padx=20)

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Pronto", text_color="gray")
        self.lbl_status.pack(pady=10)

        self.main_content = ctk.CTkFrame(self)
        self.main_content.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.tabview = ctk.CTkTabview(self.main_content)
        self.tabview.pack(fill="both", expand=True)
        self.tabview.add("Sessão 1")
        self.tabview.add("Sessão 2")
        self.tabview.add("COMPARATIVO")

        self.setup_plots()

    def setup_plots(self):
        self.figs = {}; self.canvas = {}; self.axs = {}
        for tab in ["Sessão 1", "Sessão 2", "COMPARATIVO"]:
            fig = Figure(figsize=(8, 6), dpi=100)
            fig.patch.set_facecolor('#1e1e1e')
            ax = fig.add_subplot(111)
            ax.set_facecolor('#1e1e1e')
            ax.tick_params(colors='white')
            for spine in ax.spines.values(): spine.set_color('white')

            canv = FigureCanvasTkAgg(fig, master=self.tabview.tab(tab))
            canv.get_tk_widget().pack(fill="both", expand=True)

            self.figs[tab] = fig; self.axs[tab] = ax; self.canvas[tab] = canv

    def create_input(self, label, default):
        ctk.CTkLabel(self.sidebar, text=label).pack(anchor="w", padx=20)
        el = ctk.CTkEntry(self.sidebar, width=300)
        el.insert(0, default)
        el.pack(pady=5, padx=20)
        return el

    def trocar_sessao(self, value):
        # Atualiza sessão atual e mostra/oculta frames de query dentro do container
        self.sessao_atual = 1 if value == "Execução 1" else 2

        # Remove ambos e mostra apenas o correspondente
        try:
            self.frame_query1.pack_forget()
            self.frame_query2.pack_forget()
        except Exception:
            pass

        if self.sessao_atual == 1:
            self.frame_query1.pack(fill="x")
        else:
            self.frame_query2.pack(fill="x")

        # Atualiza renderizações imediatas para refletir a mudança
        self.render_active_tab()

    def update_ui_loop(self):
        """Loop central de atualização da interface."""
        if not self.is_running and not self.data_sessao_1 and not self.data_sessao_2:
            return

        self.render_active_tab()
        self.render_comparativo()

        if self.is_running:
            # Mantém o loop de 1 em 1 segundo
            self.after(1000, self.update_ui_loop)

    def _compute_stats(self, data):
        """Retorna (min, max, mean) em ms ignorando zeros e valores inválidos."""
        valid = [v for v in data if isinstance(v, (int, float)) and v > 0]
        if not valid:
            return None, None, None
        mn = min(valid)
        mx = max(valid)
        mean = statistics.mean(valid)
        return mn, mx, mean

    def _format_stats_text(self, mn, mx, mean):
        return f"Min: {mn:.1f} ms\nMax: {mx:.1f} ms\nMédia: {mean:.1f} ms"

    def render_active_tab(self):
        tab_name = f"Sessão {self.sessao_atual}"
        data = self.data_sessao_1 if self.sessao_atual == 1 else self.data_sessao_2
        color = "#e74c3c" if self.sessao_atual == 1 else "#2ecc71"

        ax = self.axs[tab_name]
        ax.clear()
        ax.set_title(f"Monitoramento: {tab_name}", color="white")
        ax.set_ylabel("Tempo (ms)", color="white")
        ax.tick_params(colors='white')

        if data:
            ax.plot(data, color=color, linewidth=1)
            mn, mx, mean = self._compute_stats(data)
            if mn is not None:
                stats_txt = self._format_stats_text(mn, mx, mean)
                ax.text(0.98, 0.98, stats_txt, transform=ax.transAxes, ha='right', va='top',
                        color='white', bbox=dict(facecolor='black', alpha=0.6), fontsize=9)

        # Query como legenda na parte inferior (com quebra de linha) — mostra a query da sessão atual
        query = self.entry_query1.get("0.0", "end").strip() if self.sessao_atual == 1 else self.entry_query2.get("0.0", "end").strip()
        if query:
            wrapped = textwrap.fill(query, width=120)
            ax.text(0.5, -0.12, wrapped, transform=ax.transAxes, ha='center', va='top',
                    color='white', fontsize=9, bbox=dict(facecolor='black', alpha=0.4))

        self.canvas[tab_name].draw_idle()

    def render_comparativo(self):
        ax = self.axs["COMPARATIVO"]
        ax.clear()
        ax.set_title("Comparativo: Antes vs Depois", color="white")
        ax.set_ylabel("Tempo (ms)", color="white")
        ax.tick_params(colors='white')

        if self.data_sessao_1:
            ax.plot(self.data_sessao_1, color="#e74c3c", alpha=0.5, label="Antes")
        if self.data_sessao_2:
            ax.plot(self.data_sessao_2, color="#2ecc71", alpha=0.8, label="Depois")

        # Estatísticas separadas
        mn1, mx1, mean1 = self._compute_stats(self.data_sessao_1)
        mn2, mx2, mean2 = self._compute_stats(self.data_sessao_2)

        stats_lines = []
        if mn1 is not None:
            stats_lines.append(f"Antes — Min: {mn1:.1f} ms; Max: {mx1:.1f} ms; Média: {mean1:.1f} ms")
        else:
            stats_lines.append("Antes — sem dados válidos")
        if mn2 is not None:
            stats_lines.append(f"Depois — Min: {mn2:.1f} ms; Max: {mx2:.1f} ms; Média: {mean2:.1f} ms")
        else:
            stats_lines.append("Depois — sem dados válidos")

        stats_txt = "\n".join(stats_lines)
        ax.text(0.02, 0.98, stats_txt, transform=ax.transAxes, ha='left', va='top',
                color='white', bbox=dict(facecolor='black', alpha=0.6), fontsize=9)

        # Ganho/perda percentual baseado nas médias (se existirem)
        if mean1 is not None and mean2 is not None and mean1 > 0:
            ganho = ((mean1 - mean2) / mean1) * 100
            txt = f"Ganho: {ganho:.1f}%" if ganho > 0 else f"Perda: {abs(ganho):.1f}%"
            ax.text(0.5, 0.9, txt, transform=ax.transAxes, ha='center', color='yellow',
                    bbox=dict(facecolor='black', alpha=0.6))

        ax.legend()

        # Mostrar as duas queries no comparativo (Antes / Depois) com quebra de linha e linha tracejada entre elas
        q1 = self.entry_query1.get("0.0", "end").strip() or "<vazia>"
        q2 = self.entry_query2.get("0.0", "end").strip() or "<vazia>"

        # Quebrar as queries em blocos para exibir separadamente acima e abaixo da linha tracejada
        wrapped_q1 = textwrap.fill("Antes (Execução 1): " + q1, width=100)
        wrapped_q2 = textwrap.fill("Depois (Execução 2): " + q2, width=100)

        # Posições relativas (em axes coords) para os textos e a linha tracejada
        y_top = -0.08   # posição do primeiro bloco de texto
        y_line = -0.145 # posição da linha tracejada
        y_bottom = -0.21 # posição do segundo bloco de texto

        # Primeiro bloco (Antes)
        ax.text(0.5, y_top, wrapped_q1, transform=ax.transAxes, ha='center', va='top',
                color='white', fontsize=9, bbox=dict(facecolor='black', alpha=0.4))

        # Linha tracejada entre as queries
        ax.plot([0.05, 0.95], [y_line, y_line], transform=ax.transAxes,
                color='white', linestyle='--', linewidth=0.8, alpha=0.8)

        # Segundo bloco (Depois)
        ax.text(0.5, y_bottom, wrapped_q2, transform=ax.transAxes, ha='center', va='top',
                color='white', fontsize=9, bbox=dict(facecolor='black', alpha=0.4))

        self.canvas["COMPARATIVO"].draw_idle()

    async def run_stress_test(self, query, total, concur, host, user, password, db):
        conf = {'host': host, 'user': user, 'password': password, 'db': db, 'port': 3306, 'connect_timeout': 10}
        try:
            pool = await aiomysql.create_pool(**conf, minsize=1, maxsize=int(concur))
            sem = asyncio.Semaphore(int(concur))
            target = self.data_sessao_1 if self.sessao_atual == 1 else self.data_sessao_2

            async def task():
                async with sem:
                    if self.stop_event.is_set(): return
                    start = time.perf_counter()
                    try:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cur:
                                await cur.execute(query); await cur.fetchone()
                        target.append((time.perf_counter() - start) * 1000)
                    except:
                        target.append(0)

            tasks = [task() for _ in range(int(total))]
            for f in asyncio.as_completed(tasks):
                if self.stop_event.is_set(): break
                await f
            pool.close(); await pool.wait_closed()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Erro", f"Conexão falhou: {e}"))

        self.is_running = False
        self.after(0, self.finalize_ui)

    def finalize_ui(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.lbl_status.configure(text="Sessão concluída!", text_color="green")
        self.render_comparativo()

    def start_test_thread(self):
        # limpa apenas a sessão atual
        if self.sessao_atual == 1:
            self.data_sessao_1 = []
        else:
            self.data_sessao_2 = []

        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.lbl_status.configure(text="🚀 Testando...", text_color="cyan")

        # escolhe a query da sessão atual
        query = self.entry_query1.get("0.0", "end").strip() if self.sessao_atual == 1 else self.entry_query2.get("0.0", "end").strip()
        args = (query, self.entry_total.get(), self.entry_concur.get(),
                self.entry_host.get(), self.entry_user.get(), self.entry_pass.get(), self.entry_db.get())

        self.update_ui_loop() # Inicia o loop de renderização

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.run_stress_test(*args))
            loop.close()

        threading.Thread(target=run_loop, daemon=True).start()

    def stop_test(self):
        self.stop_event.set()
        self.is_running = False

    def save_all_graphs(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".png")
        if not file_path: return

        d = os.path.dirname(file_path)
        b = os.path.basename(file_path).replace(".png", "")

        self.figs["Sessão 1"].savefig(f"{d}/{b}_antes.png", facecolor='#1e1e1e', dpi=150, bbox_inches='tight')
        self.figs["Sessão 2"].savefig(f"{d}/{b}_depois.png", facecolor='#1e1e1e', dpi=150, bbox_inches='tight')
        self.figs["COMPARATIVO"].savefig(f"{d}/{b}_comparativo.png", facecolor='#1e1e1e', dpi=150, bbox_inches='tight')
        messagebox.showinfo("Sucesso", "Gráficos exportados com sucesso!")

if __name__ == "__main__":
    app = StressTestApp()
    app.mainloop()
